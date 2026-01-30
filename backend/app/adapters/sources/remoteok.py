"""RemoteOK job source adapter.

REQ-007 §6.3: RemoteOK REST API adapter.

Rate limits: Generous (no specific limit documented)
Coverage: Remote-focused jobs worldwide
"""

from typing import Any

from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams


class RemoteOKAdapter(JobSourceAdapter):
    """Adapter for the RemoteOK job board API.

    WHY REMOTEOK:
    - Focus on remote positions aligns with modern job search
    - Simple API with generous rate limits
    - Good for tech/startup roles
    """

    @property
    def source_name(self) -> str:
        """Return 'RemoteOK' as the canonical source name."""
        return "RemoteOK"

    async def fetch_jobs(self, _params: SearchParams) -> list[RawJob]:
        """Fetch jobs from RemoteOK API.

        Args:
            _params: Search parameters for filtering jobs (unused until API integration).

        Returns:
            List of RawJob objects from RemoteOK.

        Note:
            Actual API integration is deferred to REQ-003 §13.1 (Discovery Flow).
        """
        # WHY: API integration deferred - see AdzunaAdapter for explanation.
        return []

    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert RemoteOK API response to RawJob format.

        Args:
            raw_response: Raw RemoteOK API response dict.
                Expected fields:
                - id: Job ID
                - position: Job title (note: different from 'title')
                - company: Company name
                - description: Job description
                - url: URL to job posting
                - location: Location (optional, often "Worldwide")
                - salary_min: Minimum salary (optional)
                - salary_max: Maximum salary (optional)

        Returns:
            Normalized RawJob object.
        """
        return RawJob(
            external_id=str(raw_response["id"]),
            title=raw_response["position"],  # RemoteOK uses 'position' not 'title'
            company=raw_response["company"],
            description=raw_response["description"],
            source_url=raw_response["url"],
            location=raw_response.get("location"),
            salary_min=raw_response.get("salary_min"),
            salary_max=raw_response.get("salary_max"),
            raw_data=raw_response,
        )
