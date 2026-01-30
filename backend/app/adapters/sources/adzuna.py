"""Adzuna job source adapter.

REQ-007 §6.3: Adzuna REST API adapter.

Rate limits: 250 requests/day (free tier)
Coverage: Good US/UK coverage
"""

from typing import Any

from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams


class AdzunaAdapter(JobSourceAdapter):
    """Adapter for the Adzuna job search API.

    WHY ADZUNA:
    - Good coverage for US and UK job markets
    - Structured API with salary data when available
    - Free tier sufficient for MVP
    """

    @property
    def source_name(self) -> str:
        """Return 'Adzuna' as the canonical source name."""
        return "Adzuna"

    async def fetch_jobs(self, _params: SearchParams) -> list[RawJob]:
        """Fetch jobs from Adzuna API.

        Args:
            _params: Search parameters for filtering jobs (unused until API integration).

        Returns:
            List of RawJob objects from Adzuna.

        Note:
            Actual API integration is deferred to REQ-003 §13.1 (Discovery Flow).
            This implementation returns an empty list until API keys are configured.
        """
        # WHY: API integration deferred - fetch_jobs will be implemented when
        # we integrate with real API endpoints in the Discovery Flow task.
        # For now, normalize() is the core logic being tested.
        return []

    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert Adzuna API response to RawJob format.

        Args:
            raw_response: Raw Adzuna API response dict.
                Expected fields:
                - id: Job ID
                - title: Job title
                - company.display_name: Company name
                - description: Job description
                - redirect_url: URL to job posting
                - location.display_name: Location (optional)
                - salary_min: Minimum salary (optional)
                - salary_max: Maximum salary (optional)
                - created: Posted date (optional)

        Returns:
            Normalized RawJob object.
        """
        # Extract company name from nested structure
        company_data = raw_response.get("company", {})
        company_name = (
            company_data.get("display_name", "")
            if isinstance(company_data, dict)
            else str(company_data)
        )

        # Extract location from nested structure
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
            source_url=raw_response["redirect_url"],
            location=location,
            salary_min=raw_response.get("salary_min"),
            salary_max=raw_response.get("salary_max"),
            posted_date=raw_response.get("created"),
            raw_data=raw_response,
        )
