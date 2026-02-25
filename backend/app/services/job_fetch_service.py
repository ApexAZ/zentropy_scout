"""Job fetch service for orchestrating the job discovery pipeline.

REQ-016 §6.2: Fetches jobs from enabled sources, merges results,
partitions new vs existing via pool check, enriches new jobs,
saves/links to pool, and calculates poll state timestamps.

Orchestrates the fetch/merge/pool-check/enrich/save pipeline
for the job discovery workflow.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# WHY Any: Job data flows as dict[str, Any] through the fetch/merge/enrich
# pipeline. Each source adapter returns different raw schemas that are
# normalized to a common dict shape. Strict typing is enforced at
# persistence when creating JobPosting models via the dedup service.
from app.adapters.sources.adzuna import AdzunaAdapter
from app.adapters.sources.base import JobSourceAdapter, RawJob, SearchParams
from app.adapters.sources.remoteok import RemoteOKAdapter
from app.adapters.sources.themuse import TheMuseAdapter
from app.adapters.sources.usajobs import USAJobsAdapter
from app.agents.scouter import calculate_next_poll_time, merge_results
from app.repositories.job_pool_repository import JobPoolRepository
from app.services.job_enrichment_service import JobEnrichmentService
from app.services.scouter_errors import SourceError, is_retryable_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PollResult:
    """Result of a single poll cycle.

    Attributes:
        processed_jobs: All jobs processed (enriched new + linked existing).
        new_job_count: Number of new jobs saved to pool.
        existing_job_count: Number of existing jobs linked.
        error_sources: Sources that failed during fetch.
        last_polled_at: Timestamp when this poll completed.
        next_poll_at: Calculated time for the next scheduled poll.
    """

    processed_jobs: list[dict[str, Any]]
    new_job_count: int
    existing_job_count: int
    error_sources: list[str] = field(default_factory=list)
    last_polled_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    next_poll_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Source adapter registry
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: dict[str, type[JobSourceAdapter]] = {
    "Adzuna": AdzunaAdapter,
    "RemoteOK": RemoteOKAdapter,
    "TheMuse": TheMuseAdapter,
    "USAJobs": USAJobsAdapter,
}


def get_source_adapter(source_name: str) -> JobSourceAdapter | None:
    """Get an adapter instance for a source name.

    Args:
        source_name: Canonical source name (e.g., "Adzuna").

    Returns:
        Adapter instance or None if source is unknown.
    """
    adapter_class = _ADAPTER_REGISTRY.get(source_name)
    if adapter_class:
        return adapter_class()
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class JobFetchService:
    """Orchestrates the job fetch pipeline: fetch, merge, pool, enrich, save.

    Calls source adapters, merges results, partitions new vs existing
    via the shared pool, enriches new jobs, and persists.

    Args:
        db: Async database session (caller controls transaction).
        user_id: UUID of the user initiating the poll.
        persona_id: UUID of the persona being polled for.
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        persona_id: UUID,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.persona_id = persona_id

    async def run_poll(
        self,
        enabled_sources: list[str],
        polling_frequency: str = "daily",
    ) -> PollResult:
        """Execute a full poll cycle.

        REQ-016 §6.2: Single entry point for the job discovery pipeline.

        Pipeline:
            1. Fetch from all enabled sources (parallel)
            2. Merge results into flat list
            3. Resolve source IDs and partition new vs existing
            4. Enrich new jobs (extraction + ghost scoring)
            5. Save new jobs to pool / link existing jobs
            6. Calculate poll timestamps

        Args:
            enabled_sources: Source names to fetch from.
            polling_frequency: "twice_daily", "daily", or "weekly".

        Returns:
            PollResult with all processed jobs and metadata.
        """
        # Step 1: Fetch from all sources
        source_results, error_sources = await self.fetch_from_sources(
            enabled_sources,
        )

        # Step 2: Merge into flat list
        merged_jobs = merge_results(source_results)

        # Step 3: Partition new vs existing via pool check
        new_jobs, existing_jobs = await self._partition_jobs(merged_jobs)

        # Step 4: Enrich new jobs only
        enriched_new = await JobEnrichmentService.enrich_jobs(new_jobs)

        # Step 5: Save new + link existing
        saved_count = await self._save_new_jobs(enriched_new)
        linked_count = await self._link_existing_jobs(existing_jobs)

        # Step 6: Calculate poll timestamps
        now = datetime.now(UTC)
        next_poll = calculate_next_poll_time(now, polling_frequency)

        return PollResult(
            processed_jobs=enriched_new + existing_jobs,
            new_job_count=saved_count,
            existing_job_count=linked_count,
            error_sources=error_sources,
            last_polled_at=now,
            next_poll_at=next_poll,
        )

    async def fetch_from_sources(
        self,
        enabled_sources: list[str],
    ) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
        """Fetch jobs from all enabled sources in parallel.

        REQ-016 §6.2: Parallel fetch via asyncio.gather with fail-forward.
        Source errors are logged and recorded; other sources continue.

        Args:
            enabled_sources: Source names to query.

        Returns:
            (source_results, error_sources) where source_results maps
            source name to list of job dicts, and error_sources lists
            names of sources that failed.
        """
        # Resolve adapters first — skip unknown sources
        adapters: dict[str, JobSourceAdapter] = {}
        for name in enabled_sources:
            adapter = get_source_adapter(name)
            if adapter:
                adapters[name] = adapter
            else:
                logger.warning("Unknown source adapter: %s", name)

        if not adapters:
            return {}, []

        params = SearchParams(
            keywords=["software", "engineer"],
            remote_only=False,
            results_per_page=25,
        )

        # Parallel fetch — return_exceptions so one failure doesn't cancel all
        names = list(adapters.keys())
        tasks = [adapters[name].fetch_jobs(params) for name in names]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, list[dict[str, Any]]] = {}
        error_sources: list[str] = []

        for name, outcome in zip(names, gathered, strict=True):
            if isinstance(outcome, SourceError):
                logger.warning(
                    "Source %s failed: %s (retryable: %s)",
                    name,
                    str(outcome),
                    is_retryable_error(outcome),
                )
                error_sources.append(name)
            elif isinstance(outcome, Exception):
                logger.warning(
                    "Unexpected error fetching from %s: %s: %s",
                    name,
                    type(outcome).__name__,
                    outcome,
                )
                error_sources.append(name)
            else:
                # WHY cast: gather(return_exceptions=True) returns T | BaseException;
                # the isinstance checks above narrow away all exception types.
                jobs = cast(list[RawJob], outcome)
                results[name] = [
                    {
                        "external_id": job.external_id,
                        "title": job.title,
                        "company": job.company,
                        "description": job.description,
                        "source_url": job.source_url,
                        "location": job.location,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                        "posted_date": job.posted_date,
                        "source_name": name,
                    }
                    for job in jobs
                ]
                logger.info("Fetched %d jobs from %s", len(jobs), name)

        return results, error_sources

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _partition_jobs(
        self,
        merged_jobs: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Partition jobs into new and existing via pool check.

        For each job: resolve source_id, then check pool via two-tier
        dedup (external_id + description_hash).

        Args:
            merged_jobs: Flat list of job dicts with source_name.

        Returns:
            (new_jobs, existing_jobs) partitioned by pool membership.
        """
        new_jobs: list[dict[str, Any]] = []
        existing_jobs: list[dict[str, Any]] = []

        # Cache resolved source IDs to avoid repeated DB lookups
        source_id_cache: dict[str, UUID | None] = {}

        for job in merged_jobs:
            source_name = job.get("source_name", "")

            # Resolve source_id (cached per source)
            if source_name not in source_id_cache:
                source_id_cache[
                    source_name
                ] = await JobPoolRepository.resolve_source_id(self.db, source_name)

            source_id = source_id_cache[source_name]
            if source_id is None:
                logger.warning(
                    "Skipping job %s: unresolvable source %s",
                    job.get("external_id"),
                    source_name,
                )
                continue

            # Check pool
            is_existing, checked_job = await JobPoolRepository.check_job_in_pool(
                self.db,
                job,
                source_id,
            )

            if is_existing:
                existing_jobs.append(checked_job)
            else:
                new_jobs.append(checked_job)

        return new_jobs, existing_jobs

    async def _save_new_jobs(
        self,
        enriched_jobs: list[dict[str, Any]],
    ) -> int:
        """Save enriched new jobs to the shared pool.

        Args:
            enriched_jobs: Jobs enriched with extraction + ghost scores.

        Returns:
            Count of successfully saved jobs.
        """
        saved = 0
        for job in enriched_jobs:
            result = await JobPoolRepository.save_job_to_pool(
                self.db,
                job,
                self.persona_id,
                self.user_id,
            )
            if result is not None:
                saved += 1
        return saved

    async def _link_existing_jobs(
        self,
        existing_jobs: list[dict[str, Any]],
    ) -> int:
        """Create persona_jobs links for existing pool jobs.

        Args:
            existing_jobs: Jobs already in pool needing persona links.

        Returns:
            Count of successfully linked jobs.
        """
        linked = 0
        for job in existing_jobs:
            result = await JobPoolRepository.link_existing_job(
                self.db,
                job,
                self.persona_id,
                self.user_id,
            )
            if result is not None:
                linked += 1
        return linked
