"""Job source adapters.

REQ-007 §6.3: Source adapters for fetching jobs from external APIs.

This module provides:
- JobSourceAdapter base class
- Concrete adapters for Adzuna, RemoteOK, The Muse, USAJobs
- Factory function to get adapters by source name
"""

from app.adapters.sources.adzuna import AdzunaAdapter
from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams
from app.adapters.sources.remoteok import RemoteOKAdapter
from app.adapters.sources.themuse import TheMuseAdapter
from app.adapters.sources.usajobs import USAJobsAdapter

# WHY: Registry maps source names to adapter classes. Supports case-insensitive
# lookup since source names come from user input and database.
_ADAPTER_REGISTRY: dict[str, type[JobSourceAdapter]] = {
    "adzuna": AdzunaAdapter,
    "remoteok": RemoteOKAdapter,
    "the muse": TheMuseAdapter,
    "usajobs": USAJobsAdapter,
}


def get_source_adapter(source_name: str) -> JobSourceAdapter:
    """Get a source adapter instance by source name.

    Args:
        source_name: Name of the job source (e.g., "Adzuna", "RemoteOK").
            Case-insensitive matching.

    Returns:
        Instantiated adapter for the specified source.

    Raises:
        ValueError: If source_name is not a known source.
    """
    adapter_class = _ADAPTER_REGISTRY.get(source_name.lower())
    if adapter_class is None:
        known_sources = ", ".join(_ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown source: '{source_name}'. Known sources: {known_sources}"
        )
    return adapter_class()


__all__ = [
    "AdzunaAdapter",
    "get_source_adapter",
    "JobSourceAdapter",
    "RawJob",
    "RemoteOKAdapter",
    "SearchParams",
    "TheMuseAdapter",
    "USAJobsAdapter",
]
