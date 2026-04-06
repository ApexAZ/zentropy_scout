"""USAJobs job source adapter.

REQ-034 §5.3: USAJobs REST API adapter implementation.

Rate limits: 200 requests/day
Coverage: US federal government jobs

Coordinates with:
  - adapters/sources/base.py (JobSourceAdapter, RawJob, SearchParams)
  - services/discovery/scouter_errors.py (SourceError, SourceErrorType, RateLimitInfo)
  - core/config.py (settings — usajobs_user_agent, usajobs_email)

Called by: services/discovery/job_fetch_service.py (USAJobsAdapter).
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

_USAJOBS_BASE_URL = "https://data.usajobs.gov/api/Search"
_USAJOBS_AUTH_TOKEN = (
    "USAJOBS-DEMO-TOKEN"  # Public demo token for free tier  # nosec B105
)
_REQUEST_TIMEOUT_SECONDS = 30.0
_MAX_RETRY_AFTER_SECONDS = 3600  # 1 hour ceiling on Retry-After to prevent DoS
_MAX_PAGES = 20  # Hard ceiling: 10k row cap (500 results × 20 pages)
_MAX_RESULTS_PER_PAGE = 500  # USAJobs API hard limit


def _validate_source_url(url: str) -> str:
    """Validate that a source URL uses an http or https scheme.

    This validation is scheme-only. The URL is STORED, not fetched by this
    adapter — callers that later perform server-side HTTP requests using stored
    job URLs must additionally validate that the host is not a private/internal
    address to prevent SSRF.

    Args:
        url: URL string to validate.

    Returns:
        The original URL if valid.

    Raises:
        ValueError: If the URL scheme is not http or https.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unexpected URL scheme in ApplyURI: {parsed.scheme!r}")
    return url


class USAJobsAdapter(JobSourceAdapter):
    """Adapter for the USAJobs federal job search API.

    REQ-034 §5.3: Implements fetch_jobs() with header-based auth, pagination
    (up to 20 pages), DatePosted delta filtering, and SourceError on API failure.

    WHY USAJOBS:
    - Official source for US federal government positions
    - Structured data with salary bands
    - Important for users seeking government employment
    """

    @property
    def source_name(self) -> str:
        """Return 'USAJobs' as the canonical source name."""
        return "USAJobs"

    async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
        """Fetch jobs from USAJobs API.

        REQ-034 §5.3: Header-based auth (Authorization: USAJOBS-DEMO-TOKEN,
        User-Agent, Email-Address, Host). Paginates using 1-indexed Page param
        until NumberOfPages is exhausted, hard-capped at _MAX_PAGES (20).
        ResultsPerPage capped at 500. Sends DatePosted when max_days_old is set.

        Args:
            params: Search parameters — keywords, location, remote_only,
                results_per_page, max_days_old.

        Returns:
            List of normalized RawJob objects from USAJobs. Returns [] if
            usajobs_user_agent or usajobs_email is not configured.

        Raises:
            SourceError: On 4xx/5xx (API_DOWN), 429 (RATE_LIMITED, with
                retry_after), timeout (TIMEOUT), or network error (NETWORK_ERROR).
        """
        if settings.usajobs_user_agent is None or settings.usajobs_email is None:
            logger.warning(
                "USAJobs credentials not configured (USAJOBS_USER_AGENT / USAJOBS_EMAIL);"
                " skipping USAJobs source"
            )
            return []

        headers = {
            "Authorization": _USAJOBS_AUTH_TOKEN,
            "User-Agent": settings.usajobs_user_agent,
            "Email-Address": settings.usajobs_email,
            "Host": "data.usajobs.gov",
        }

        jobs: list[RawJob] = []
        page = 1

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            while page <= _MAX_PAGES:
                query_params: dict[str, Any] = {
                    "Keyword": " ".join(params.keywords),
                    "ResultsPerPage": min(
                        params.results_per_page, _MAX_RESULTS_PER_PAGE
                    ),
                    "Page": page,
                }

                if params.remote_only:
                    query_params["RemoteIndicator"] = "True"
                elif params.location:
                    query_params["LocationName"] = params.location

                if params.max_days_old is not None:
                    query_params["DatePosted"] = params.max_days_old

                try:
                    response = await client.get(
                        _USAJOBS_BASE_URL,
                        params=query_params,
                        headers=headers,
                    )
                except httpx.TimeoutException as exc:
                    # Security: do not include exc in message — httpx exception
                    # repr can embed the full request URL including credentials.
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
                            clamped = max(
                                0,
                                min(int(retry_after_raw), _MAX_RETRY_AFTER_SECONDS),
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
                search_result = data.get("SearchResult", {})
                items: list[dict[str, Any]] = search_result.get("SearchResultItems", [])
                try:
                    number_of_pages = int(
                        search_result.get("UserArea", {}).get("NumberOfPages", 1)
                    )
                except (ValueError, TypeError):
                    number_of_pages = 1

                for item in items:
                    try:
                        jobs.append(self.normalize(item))
                    except (KeyError, ValueError) as exc:
                        logger.warning(
                            "Failed to normalize %s job (id=%s): %s; skipping",
                            self.source_name,
                            item.get("MatchedObjectId", "unknown"),
                            exc,
                        )

                # Stop when all pages exhausted or empty page
                if not items or page >= min(number_of_pages, _MAX_PAGES):
                    break

                page += 1

        return jobs

    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert USAJobs API response to RawJob format.

        Args:
            raw_response: Raw USAJobs API response dict.
                Expected structure (deeply nested):
                - MatchedObjectId: Job ID
                - MatchedObjectDescriptor.PositionTitle: Job title
                - MatchedObjectDescriptor.OrganizationName: Agency name
                - MatchedObjectDescriptor.UserArea.Details.JobSummary: Description
                - MatchedObjectDescriptor.PositionLocation[0].LocationName: Location
                - MatchedObjectDescriptor.PositionRemuneration[0]: Salary info
                - MatchedObjectDescriptor.ApplyURI[0]: Application URL
                    (must be http/https when present)

        Returns:
            Normalized RawJob object.

        Raises:
            KeyError: If MatchedObjectId is absent from raw_response.
            ValueError: If ApplyURI[0] uses a non-http/https scheme.
        """
        descriptor = raw_response.get("MatchedObjectDescriptor", {})

        # Extract description from nested UserArea.Details
        user_area = descriptor.get("UserArea", {})
        details = user_area.get("Details", {})
        description = details.get("JobSummary", "")

        # Extract first location
        locations = descriptor.get("PositionLocation", [])
        location = locations[0].get("LocationName") if locations else None

        # Extract salary from nested remuneration array
        remuneration = descriptor.get("PositionRemuneration", [])
        salary_min = None
        salary_max = None
        if remuneration:
            salary_data = remuneration[0]
            min_range = salary_data.get("MinimumRange")
            max_range = salary_data.get("MaximumRange")
            # USAJobs returns salary as strings, convert to int
            if min_range is not None:
                salary_min = int(float(min_range))
            if max_range is not None:
                salary_max = int(float(max_range))

        # Extract apply URL from array; validate scheme when present
        apply_uris = descriptor.get("ApplyURI", [])
        source_url = _validate_source_url(apply_uris[0]) if apply_uris else ""

        return RawJob(
            external_id=str(raw_response["MatchedObjectId"]),
            title=descriptor.get("PositionTitle", ""),
            company=descriptor.get("OrganizationName", ""),
            description=description,
            source_url=source_url,
            location=location,
            salary_min=salary_min,
            salary_max=salary_max,
            # WHY: USAJobs is exclusively for US federal positions, so USD is implicit.
            salary_currency="USD" if salary_min is not None else None,
            # WHY posted_date omitted: USAJobs uses PositionStartDate which is the
            # scheduled start date for the role, not the announcement date. The delta
            # filter uses max_days_old / DatePosted server-side, so this field is not
            # needed for dedup or ordering in this adapter.
            raw_data=raw_response,
        )
