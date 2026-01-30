"""USAJobs job source adapter.

REQ-007 §6.3: USAJobs REST API adapter.

Rate limits: 200 requests/day
Coverage: US federal government jobs
"""

from typing import Any

from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams


class USAJobsAdapter(JobSourceAdapter):
    """Adapter for the USAJobs federal job search API.

    WHY USAJOBS:
    - Official source for US federal government positions
    - Structured data with salary bands
    - Important for users seeking government employment
    """

    @property
    def source_name(self) -> str:
        """Return 'USAJobs' as the canonical source name."""
        return "USAJobs"

    async def fetch_jobs(self, _params: SearchParams) -> list[RawJob]:
        """Fetch jobs from USAJobs API.

        Args:
            _params: Search parameters for filtering jobs (unused until API integration).

        Returns:
            List of RawJob objects from USAJobs.

        Note:
            Actual API integration is deferred to REQ-003 §13.1 (Discovery Flow).
        """
        # WHY: API integration deferred - see AdzunaAdapter for explanation.
        return []

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

        Returns:
            Normalized RawJob object.
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

        # Extract apply URL from array
        apply_uris = descriptor.get("ApplyURI", [])
        source_url = apply_uris[0] if apply_uris else ""

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
            raw_data=raw_response,
        )
