"""Adzuna job source adapter.

REQ-034 §5.3: Adzuna REST API adapter implementation.

Rate limits: 25 req/min, 1,000/week (binding constraint mid-week).
Coverage: Good US/UK job market coverage.

Coordinates with:
  - adapters/sources/base.py (JobSourceAdapter, RawJob, SearchParams)
  - services/discovery/scouter_errors.py (SourceError, SourceErrorType, RateLimitInfo)
  - core/config.py (settings — adzuna_app_id, adzuna_app_key)

Called by: services/discovery/job_fetch_service.py (AdzunaAdapter).
"""

import asyncio
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

_ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search"
_RATE_LIMIT_SLEEP_SECONDS = 2.4  # 25 req/min cap → 1 request per 2.4s
_REQUEST_TIMEOUT_SECONDS = 30.0
_MAX_PAGES = (
    10  # Hard ceiling: 250 results max per poll (25 × 10) to protect weekly quota
)
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
        raise ValueError(f"Unexpected URL scheme in redirect_url: {parsed.scheme!r}")
    return url


class AdzunaAdapter(JobSourceAdapter):
    """Adapter for the Adzuna job search API.

    REQ-034 §5.3: Implements fetch_jobs() with pagination, delta params,
    rate limiting, and SourceError on API failure.

    WHY ADZUNA:
    - Good coverage for US and UK job markets
    - Structured API with salary data when available
    - Free tier sufficient at MVP scale
    """

    @property
    def source_name(self) -> str:
        """Return 'Adzuna' as the canonical source name."""
        return "Adzuna"

    async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
        """Fetch jobs from Adzuna API.

        REQ-034 §5.3: Paginates until 0 results or partial page, up to
        _MAX_PAGES pages. Rate-limits to 25 req/min via asyncio.sleep(2.4)
        between pages. Returns [] if credentials are not configured.

        Args:
            params: Search parameters — keywords, location, remote_only,
                results_per_page, max_days_old.

        Returns:
            List of normalized RawJob objects.

        Raises:
            SourceError: On 4xx/5xx (API_DOWN), 429 (RATE_LIMITED, with
                retry_after), timeout (TIMEOUT), or network error (NETWORK_ERROR).
        """
        if settings.adzuna_app_id is None or settings.adzuna_app_key is None:
            logger.warning(
                "Adzuna credentials not configured (ADZUNA_APP_ID / ADZUNA_APP_KEY);"
                " skipping Adzuna source"
            )
            return []

        app_id = settings.adzuna_app_id
        app_key = settings.adzuna_app_key.get_secret_value()

        jobs: list[RawJob] = []
        page = 1

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            while page <= _MAX_PAGES:
                query_params: dict[str, Any] = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": params.results_per_page,
                    "what": " ".join(params.keywords),
                }

                if params.remote_only:
                    query_params["where"] = "remote"
                elif params.location:
                    query_params["where"] = params.location

                if params.max_days_old is not None:
                    query_params["max_days_old"] = params.max_days_old

                try:
                    response = await client.get(
                        f"{_ADZUNA_BASE_URL}/{page}",
                        params=query_params,
                    )
                except httpx.TimeoutException as exc:
                    # Security: do not include exc in message — httpx exception
                    # repr can embed the full request URL including api_key.
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.TIMEOUT,
                        message=f"Adzuna request timed out on page {page}",
                    ) from exc
                except httpx.RequestError as exc:
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.NETWORK_ERROR,
                        message=f"Adzuna network error on page {page}",
                    ) from exc

                if response.status_code == 429:
                    retry_after_raw = response.headers.get("Retry-After")
                    rate_limit_info: RateLimitInfo | None = None
                    if retry_after_raw:
                        clamped = min(int(retry_after_raw), _MAX_RETRY_AFTER_SECONDS)
                        rate_limit_info = RateLimitInfo(retry_after_seconds=clamped)
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.RATE_LIMITED,
                        message="Adzuna rate limit exceeded",
                        rate_limit_info=rate_limit_info,
                    )

                if response.status_code >= 400:
                    raise SourceError(
                        source_name=self.source_name,
                        error_type=SourceErrorType.API_DOWN,
                        message=f"Adzuna API error: HTTP {response.status_code}",
                    )

                data = response.json()
                results: list[dict[str, Any]] = data.get("results", [])

                for item in results:
                    try:
                        jobs.append(self.normalize(item))
                    except (KeyError, ValueError) as exc:
                        logger.warning(
                            "Failed to normalize Adzuna job (id=%s): %s; skipping",
                            item.get("id", "unknown"),
                            exc,
                        )

                # Stop when empty page or partial page (fewer than requested)
                if len(results) == 0 or len(results) < params.results_per_page:
                    break

                page += 1
                await asyncio.sleep(_RATE_LIMIT_SLEEP_SECONDS)

        return jobs

    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert Adzuna API response to RawJob format.

        Args:
            raw_response: Raw Adzuna API response dict.
                Expected fields:
                - id: Job ID
                - title: Job title
                - company.display_name: Company name
                - description: Job description
                - redirect_url: URL to job posting (must be http/https)
                - location.display_name: Location (optional)
                - salary_min: Minimum salary (optional)
                - salary_max: Maximum salary (optional)
                - created: Posted date (optional)

        Returns:
            Normalized RawJob object.

        Raises:
            KeyError: If a required field (id, title, description, redirect_url)
                is absent from raw_response.
            ValueError: If redirect_url uses a non-http/https scheme.
        """
        company_data = raw_response.get("company", {})
        company_name = (
            company_data.get("display_name", "")
            if isinstance(company_data, dict)
            else str(company_data)
        )

        location_data = raw_response.get("location", {})
        location = (
            location_data.get("display_name")
            if isinstance(location_data, dict)
            else None
        )

        return RawJob(
            external_id=str(raw_response["id"]),
            title=raw_response["title"],
            company=company_name,
            description=raw_response["description"],
            source_url=_validate_source_url(raw_response["redirect_url"]),
            location=location,
            salary_min=raw_response.get("salary_min"),
            salary_max=raw_response.get("salary_max"),
            posted_date=raw_response.get("created"),
            raw_data=raw_response,
        )
