"""The Muse job source adapter.

REQ-034 §5.3: The Muse REST API adapter implementation.

Rate limits: 3,600 req/hr (authenticated), 500 req/hr (unauthenticated).
Coverage: Curated companies, often with culture info.

Coordinates with:
  - adapters/sources/base.py (JobSourceAdapter, RawJob, SearchParams)
  - services/discovery/scouter_errors.py (SourceError, SourceErrorType, RateLimitInfo)
  - core/config.py (settings — the_muse_api_key)

Called by: services/discovery/job_fetch_service.py (TheMuseAdapter).
"""

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams
from app.core.config import settings
from app.services.discovery.scouter_errors import (
    RateLimitInfo,
    SourceError,
    SourceErrorType,
)

logger = logging.getLogger(__name__)

_THEMUSE_BASE_URL = "https://www.themuse.com/api/public/jobs"
_REQUEST_TIMEOUT_SECONDS = 30.0
_MAX_RETRY_AFTER_SECONDS = 3600  # 1 hour ceiling on Retry-After to prevent DoS


def _validate_source_url(url: str) -> str:
    """Validate that a source URL uses an http or https scheme.

    Args:
        url: URL string to validate.

    Returns:
        The original URL if valid.

    Raises:
        ValueError: If the URL scheme is not http or https.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unexpected URL scheme in landing_page: {parsed.scheme!r}")
    return url


class TheMuseAdapter(JobSourceAdapter):
    """Adapter for The Muse job search API.

    REQ-034 §5.3: Implements fetch_jobs() with page_count pagination,
    client-side keyword filtering, and SourceError on API failure.

    WHY THE MUSE:
    - Curated company profiles with culture information
    - Good for culture-fit matching
    - Higher rate limit than other sources
    - No credentials required (unauthenticated 500/hr tier available)
    """

    @property
    def source_name(self) -> str:
        """Return 'The Muse' as the canonical source name."""
        return "The Muse"

    async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
        """Fetch jobs from The Muse API.

        REQ-034 §5.3: Paginates using zero-indexed page param until
        page >= page_count. Applies client-side keyword filter on title
        (case-insensitive). Omits api_key when not configured (falls back
        to 500/hr unauthenticated tier — not an error condition).

        Args:
            params: Search parameters — keywords used for client-side
                title filtering; results_per_page is ignored (The Muse
                returns fixed 20 per page).

        Returns:
            List of normalized RawJob objects whose titles match at least
            one keyword from params.keywords.

        Raises:
            SourceError: On 4xx/5xx (API_DOWN), 429 (RATE_LIMITED, with
                retry_after), timeout (TIMEOUT), or network error (NETWORK_ERROR).
        """
        jobs: list[RawJob] = []
        page = 0

        # Build base query params — api_key is optional (unauthenticated fallback)
        base_params: dict[str, Any] = {}
        if settings.the_muse_api_key is not None:
            base_params["api_key"] = settings.the_muse_api_key.get_secret_value()

        lowered_keywords = [kw.lower() for kw in params.keywords]

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            while True:
                request_params = {**base_params, "page": page}

                try:
                    response = await client.get(
                        _THEMUSE_BASE_URL,
                        params=request_params,
                    )
                except httpx.TimeoutException as exc:
                    # Security: do not include exc in message — httpx exception
                    # repr can embed the full request URL including api_key.
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.TIMEOUT,
                        message=f"{self.source_name} request timed out on page {page}",
                    ) from exc
                except httpx.RequestError as exc:
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.NETWORK_ERROR,
                        message=f"{self.source_name} network error on page {page}",
                    ) from exc

                if response.status_code == 429:
                    retry_after_raw = response.headers.get("Retry-After")
                    rate_limit_info: RateLimitInfo | None = None
                    if retry_after_raw:
                        try:
                            clamped = min(
                                int(retry_after_raw), _MAX_RETRY_AFTER_SECONDS
                            )
                            rate_limit_info = RateLimitInfo(retry_after_seconds=clamped)
                        except ValueError:
                            pass  # Non-integer Retry-After (e.g. HTTP-date) — skip
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.RATE_LIMITED,
                        message=f"{self.source_name} rate limit exceeded",
                        rate_limit_info=rate_limit_info,
                    )

                if response.status_code >= 400:
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.API_DOWN,
                        message=f"{self.source_name} API error: HTTP {response.status_code}",
                    )

                data = response.json()
                results: list[dict[str, Any]] = data.get("results", [])
                page_count: int = data.get("page_count", 0)

                for item in results:
                    try:
                        raw_job = self.normalize(item)
                    except (KeyError, ValueError) as exc:
                        logger.warning(
                            "Failed to normalize %s job (id=%s): %s; skipping",
                            self.source_name,
                            item.get("id", "unknown"),
                            exc,
                        )
                        continue

                    # Client-side keyword filter: keep only title-matching jobs.
                    # The Muse has no server-side keyword/text search parameter.
                    if any(kw in raw_job.title.lower() for kw in lowered_keywords):
                        jobs.append(raw_job)

                # Advance page and stop when all pages exhausted or no results
                page += 1
                if not results or page >= page_count:
                    break

        return jobs

    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert The Muse API response to RawJob format.

        Args:
            raw_response: Raw The Muse API response dict.
                Expected fields:
                - id: Job ID (integer)
                - name: Job title (note: 'name' not 'title')
                - company.name: Company name
                - contents: Job description (HTML)
                - refs.landing_page: URL to job posting
                - locations: List of location objects

        Returns:
            Normalized RawJob object.

        Raises:
            KeyError: If a required field (id, name, contents) is absent from
                raw_response.
            ValueError: If landing_page uses a non-http/https scheme.
        """
        # Extract company name from nested structure
        company_data = raw_response.get("company", {})
        company_name = (
            company_data.get("name", "")
            if isinstance(company_data, dict)
            else str(company_data)
        )

        # Extract first location from locations array
        locations = raw_response.get("locations", [])
        location = locations[0].get("name") if locations else None

        # Extract URL from refs structure; validate scheme to match adzuna.py pattern
        refs = raw_response.get("refs", {})
        source_url = _validate_source_url(refs.get("landing_page", ""))

        return RawJob(
            external_id=str(raw_response["id"]),
            title=raw_response["name"],  # The Muse uses 'name' not 'title'
            company=company_name,
            description=raw_response["contents"],  # 'contents' not 'description'
            source_url=source_url,
            location=location,
            raw_data=raw_response,
        )
