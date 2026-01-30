"""The Muse job source adapter.

REQ-007 §6.3: The Muse REST API adapter.

Rate limits: 3600 requests/hour
Coverage: Curated companies, often with culture info
"""

from typing import Any

from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams


class TheMuseAdapter(JobSourceAdapter):
    """Adapter for The Muse job search API.

    WHY THE MUSE:
    - Curated company profiles with culture information
    - Good for culture-fit matching
    - Higher rate limit than other sources
    """

    @property
    def source_name(self) -> str:
        """Return 'The Muse' as the canonical source name."""
        return "The Muse"

    async def fetch_jobs(self, _params: SearchParams) -> list[RawJob]:
        """Fetch jobs from The Muse API.

        Args:
            _params: Search parameters for filtering jobs (unused until API integration).

        Returns:
            List of RawJob objects from The Muse.

        Note:
            Actual API integration is deferred to REQ-003 §13.1 (Discovery Flow).
        """
        # WHY: API integration deferred - see AdzunaAdapter for explanation.
        return []

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

        # Extract URL from refs structure
        refs = raw_response.get("refs", {})
        source_url = refs.get("landing_page", "")

        return RawJob(
            external_id=str(raw_response["id"]),
            title=raw_response["name"],  # The Muse uses 'name' not 'title'
            company=company_name,
            description=raw_response["contents"],  # 'contents' not 'description'
            source_url=source_url,
            location=location,
            raw_data=raw_response,
        )
