"""Abstract base class and types for job source adapters.

REQ-007 §6.3: JobSourceAdapter interface with fetch_jobs() and normalize().

Coordinates with:
  - (standalone — no app-internal imports)

Called by:
  - adapters/sources/adzuna.py, adapters/sources/remoteok.py,
    adapters/sources/themuse.py, adapters/sources/usajobs.py
    (JobSourceAdapter subclasses, RawJob, SearchParams)
  - services/discovery/job_fetch_service.py (JobSourceAdapter,
    RawJob, SearchParams)
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Valid remoteok tag format: alphanumeric with dots, underscores, hyphens (max 64 chars).
_TAG_RE = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")
_MAX_REMOTEOK_TAGS = 10
_MAX_DAYS_OLD = 90


@dataclass
class SearchParams:
    """Search parameters for job queries.

    REQ-007 §6.3, REQ-034 §5.1: Parameters passed to source adapters for job search.

    Attributes:
        keywords: Search terms for job titles, skills, etc.
        location: Optional location filter (city, state, country).
        remote_only: If True, only return remote jobs.
        page: Page number for pagination (1-indexed).
        results_per_page: Number of results per page.
        max_days_old: Maximum job age in days. Used by Adzuna and USAJobs as a
            query parameter delta. Defaults to 7 on first poll (no prior poll).
            Must be between 1 and 90 inclusive.
        posted_after: Reference timestamp derived from max_days_old. Adapters
            translate this into their own delta parameter format. Must be
            timezone-aware to avoid silent UTC/local-time mismatches.
        remoteok_tags: Pass-through tags for the RemoteOK adapter's ``?tag=``
            query string. If None or empty, the adapter pulls all jobs. Each tag
            must match ``[a-zA-Z0-9._-]{1,64}``; list length ≤ 10.
            Callers must not mutate this list after construction — it is shared
            across concurrent adapter calls.
    """

    keywords: list[str]
    location: str | None = None
    remote_only: bool = False
    page: int = 1
    results_per_page: int = 25
    max_days_old: int | None = None
    posted_after: datetime | None = None
    remoteok_tags: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate field values at construction time.

        Raises:
            ValueError: If any field value violates its constraint.
        """
        if self.posted_after is not None and self.posted_after.tzinfo is None:
            raise ValueError("posted_after must be timezone-aware")
        if self.max_days_old is not None and not (
            1 <= self.max_days_old <= _MAX_DAYS_OLD
        ):
            raise ValueError(
                f"max_days_old must be between 1 and {_MAX_DAYS_OLD}, got {self.max_days_old}"
            )
        if self.remoteok_tags is not None:
            if len(self.remoteok_tags) > _MAX_REMOTEOK_TAGS:
                raise ValueError(
                    f"remoteok_tags must contain at most {_MAX_REMOTEOK_TAGS} tags,"
                    f" got {len(self.remoteok_tags)}"
                )
            for tag in self.remoteok_tags:
                if not _TAG_RE.match(tag):
                    raise ValueError(
                        f"Invalid remoteok tag {tag!r}: must match [a-zA-Z0-9._-]{{1,64}}"
                    )


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
