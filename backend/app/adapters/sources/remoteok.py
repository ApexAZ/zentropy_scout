"""RemoteOK job source adapter.

REQ-034 §5.3: RemoteOK REST API adapter implementation.

Rate limits: No published limit; Cloudflare CDN caches responses for 1 hour.
Coverage: Remote-focused jobs worldwide.

Coordinates with:
  - adapters/sources/base.py (JobSourceAdapter, RawJob, SearchParams)
  - services/discovery/scouter_errors.py (SourceError, SourceErrorType, RateLimitInfo)

Called by: services/discovery/job_fetch_service.py (RemoteOKAdapter).
"""

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams
from app.services.discovery.scouter_errors import (
    RateLimitInfo,
    SourceError,
    SourceErrorType,
)

logger = logging.getLogger(__name__)

_REMOTEOK_BASE_URL = "https://remoteok.com/api"
_REQUEST_TIMEOUT_SECONDS = 30.0
_MAX_RETRY_AFTER_SECONDS = 3600  # 1 hour ceiling on Retry-After to prevent DoS
_MAX_RESPONSE_BYTES = (
    10 * 1024 * 1024
)  # 10 MB ceiling — guard against anomalous payloads


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
        raise ValueError(f"Unexpected URL scheme in url: {parsed.scheme!r}")
    return url


class RemoteOKAdapter(JobSourceAdapter):
    """Adapter for the RemoteOK job board API.

    REQ-034 §5.3: Implements fetch_jobs() with a single HTTP call (no pagination),
    metadata object skip, optional tag filtering, and SourceError on API failure.

    WHY REMOTEOK:
    - Focus on remote positions aligns with modern job search
    - Simple API with generous rate limits (1hr CDN cache)
    - Good for tech/startup roles
    - No credentials required
    """

    @property
    def source_name(self) -> str:
        """Return 'RemoteOK' as the canonical source name."""
        return "RemoteOK"

    async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
        """Fetch jobs from RemoteOK API.

        REQ-034 §5.3: Single GET call to remoteok.com/api. Response is a JSON
        array where index 0 is a metadata/legal object — skip it. If
        params.remoteok_tags is non-empty, passes the first tag as ?tag= query
        param. No credentials required.

        Args:
            params: Search parameters — remoteok_tags used for server-side tag
                filtering; other fields (keywords, location) are unused as
                RemoteOK does not support keyword search.

        Returns:
            List of normalized RawJob objects from RemoteOK.

        Raises:
            SourceError: On 4xx/5xx (API_DOWN), 429 (RATE_LIMITED, with
                retry_after), timeout (TIMEOUT), or network error (NETWORK_ERROR).
        """
        query_params: dict[str, Any] = {}
        if params.remoteok_tags:
            query_params["tag"] = params.remoteok_tags[0]

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.get(
                    _REMOTEOK_BASE_URL,
                    params=query_params,
                )
            except httpx.TimeoutException as exc:
                # Security: do not include exc in message — httpx exception
                # repr can embed the full request URL.
                raise SourceError(
                    source_name=self.source_name,
                    error_type=SourceErrorType.TIMEOUT,
                    message=f"{self.source_name} request timed out",
                ) from exc
            except httpx.RequestError as exc:
                raise SourceError(
                    source_name=self.source_name,
                    error_type=SourceErrorType.NETWORK_ERROR,
                    message=f"{self.source_name} network error",
                ) from exc

            if response.status_code == 429:
                retry_after_raw = response.headers.get("Retry-After")
                rate_limit_info: RateLimitInfo | None = None
                if retry_after_raw:
                    try:
                        clamped = min(int(retry_after_raw), _MAX_RETRY_AFTER_SECONDS)
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

            if len(response.content) > _MAX_RESPONSE_BYTES:
                raise SourceError(
                    source_name=self.source_name,
                    error_type=SourceErrorType.API_DOWN,
                    message=f"{self.source_name} response exceeded size limit",
                )

            # Index 0 is a metadata/legal notice object — skip it
            items: list[dict[str, Any]] = response.json()
            jobs: list[RawJob] = []
            for item in items[1:]:
                try:
                    jobs.append(self.normalize(item))
                except (KeyError, ValueError) as exc:
                    logger.warning(
                        "Failed to normalize %s job (id=%s): %s; skipping",
                        self.source_name,
                        item.get("id", "unknown"),
                        exc,
                    )

        return jobs

    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert RemoteOK API response to RawJob format.

        Args:
            raw_response: Raw RemoteOK API response dict.
                Expected fields:
                - id: Job ID
                - position: Job title (note: 'position' not 'title')
                - company: Company name
                - description: Job description
                - url: URL to job posting (must be http/https)
                - location: Location (optional, often "Worldwide")
                - salary_min: Minimum salary (optional)
                - salary_max: Maximum salary (optional)
                - tags: List of tag strings (optional; preserved in raw_data)

        Returns:
            Normalized RawJob object.

        Raises:
            KeyError: If a required field (id, position, company, description,
                url) is absent from raw_response.
            ValueError: If url uses a non-http/https scheme.
        """
        return RawJob(
            external_id=str(raw_response["id"]),
            title=raw_response["position"],  # RemoteOK uses 'position' not 'title'
            company=raw_response["company"],
            description=raw_response["description"],
            source_url=_validate_source_url(raw_response["url"]),
            location=raw_response.get("location"),
            salary_min=raw_response.get("salary_min"),
            salary_max=raw_response.get("salary_max"),
            raw_data=raw_response,
        )
