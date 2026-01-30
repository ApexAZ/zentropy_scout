"""Abstract base class and types for job source adapters.

REQ-007 §6.3: JobSourceAdapter interface with fetch_jobs() and normalize().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchParams:
    """Search parameters for job queries.

    REQ-007 §6.3: Parameters passed to source adapters for job search.

    Attributes:
        keywords: Search terms for job titles, skills, etc.
        location: Optional location filter (city, state, country).
        remote_only: If True, only return remote jobs.
        page: Page number for pagination (1-indexed).
        results_per_page: Number of results per page.
    """

    keywords: list[str]
    location: str | None = None
    remote_only: bool = False
    page: int = 1
    results_per_page: int = 25


@dataclass
class RawJob:
    """Raw job data from a source before normalization.

    REQ-007 §6.3: Source-agnostic job representation.

    WHY DATACLASS: Provides type safety and IDE support while remaining
    flexible enough to handle varying source responses. The raw_data field
    preserves the full source response for debugging and future extraction.

    Attributes:
        external_id: Unique ID from the source system.
        title: Job title.
        company: Company name.
        description: Job description text.
        source_url: URL to the job posting.
        location: Optional location string.
        salary_min: Optional minimum salary.
        salary_max: Optional maximum salary.
        salary_currency: Optional currency code (USD, EUR, etc.).
        posted_date: Optional date string when posted.
        raw_data: Full source response for debugging/future use.
    """

    external_id: str
    title: str
    company: str
    description: str
    source_url: str
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    posted_date: str | None = None
    # WHY: Store full API response for debugging and extracting additional
    # fields later without re-fetching from the source.
    raw_data: dict[str, Any] | None = field(default=None)


class JobSourceAdapter(ABC):
    """Abstract base class for job source adapters.

    REQ-007 §6.3: Each source adapter implements fetch_jobs() and normalize().

    WHY ABSTRACT CLASS:
    - Enforces consistent interface across sources
    - Enables type checking and IDE support
    - Makes testing via mock implementations straightforward
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the canonical name for this source.

        Returns:
            Source name as stored in the job_sources table (e.g., "Adzuna").
        """
        ...

    @abstractmethod
    async def fetch_jobs(self, params: SearchParams) -> list[RawJob]:
        """Fetch jobs from the external source.

        Args:
            params: Search parameters for filtering jobs.

        Returns:
            List of RawJob objects from the source.

        Raises:
            SourceError: On API failure (rate limit, network, etc.).
        """
        ...

    @abstractmethod
    # WHY: raw_response structure varies by source API - each adapter
    # knows its own schema and handles the conversion.
    def normalize(self, raw_response: dict[str, Any]) -> RawJob:
        """Convert source-specific response to RawJob format.

        Args:
            raw_response: Raw API response dict from the source.

        Returns:
            Normalized RawJob object.
        """
        ...
