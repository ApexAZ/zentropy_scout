"""Tests for JobFetchService.

REQ-016 §6.2: Fetches jobs from enabled sources, merges results,
partitions new vs existing via pool check, enriches new jobs,
saves/links to pool, and updates poll state.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.job_fetch_service import JobFetchService, PollResult

# Module paths for patching
_GET_ADAPTER = "app.services.job_fetch_service.get_source_adapter"
_POOL_REPO = "app.services.job_fetch_service.JobPoolRepository"
_ENRICHMENT = "app.services.job_fetch_service.JobEnrichmentService"

# S1192: Duplicated source name strings used across tests
_SOURCE_ADZUNA = "Adzuna"
_SOURCE_REMOTEOK = "RemoteOK"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async database session."""
    return AsyncMock()


@pytest.fixture
def user_id() -> UUID:
    """Stable user UUID for test assertions."""
    return uuid4()


@pytest.fixture
def persona_id() -> UUID:
    """Stable persona UUID for test assertions."""
    return uuid4()


@pytest.fixture
def service(mock_db: AsyncMock, user_id, persona_id) -> JobFetchService:
    """JobFetchService with mocked DB session."""
    return JobFetchService(db=mock_db, user_id=user_id, persona_id=persona_id)


@pytest.fixture
def make_raw_job() -> Callable[..., MagicMock]:
    """Factory for creating mock RawJob objects from adapters."""

    def _make(
        external_id: str = "ext-001",
        title: str = "Python Developer",
        company: str = "Acme Inc",
        description: str = "Build APIs with Python",
        source_url: str = "https://example.com/job/001",
        location: str = "Remote",
        salary_min: int = 100000,
        salary_max: int = 150000,
        posted_date: str = "2026-02-20",
    ) -> MagicMock:
        job = MagicMock()
        job.external_id = external_id
        job.title = title
        job.company = company
        job.description = description
        job.source_url = source_url
        job.location = location
        job.salary_min = salary_min
        job.salary_max = salary_max
        job.posted_date = posted_date
        return job

    return _make


@pytest.fixture
def make_adapter() -> Callable[..., AsyncMock]:
    """Factory for creating mock source adapters."""

    def _make(raw_jobs: list[MagicMock] | Exception) -> AsyncMock:
        adapter = AsyncMock()
        if isinstance(raw_jobs, Exception):
            adapter.fetch_jobs = AsyncMock(side_effect=raw_jobs)
        else:
            adapter.fetch_jobs = AsyncMock(return_value=raw_jobs)
        return adapter

    return _make


# ---------------------------------------------------------------------------
# PollResult
# ---------------------------------------------------------------------------


class TestPollResult:
    """Tests for PollResult dataclass."""

    def test_captures_processed_jobs(self) -> None:
        """PollResult holds the combined list of processed jobs."""
        jobs: list[dict[str, Any]] = [{"id": "1", "title": "Job A"}]
        result = PollResult(
            processed_jobs=jobs,
            new_job_count=1,
            existing_job_count=0,
            error_sources=[],
        )

        assert result.processed_jobs == jobs
        assert result.new_job_count == 1

    def test_tracks_new_and_existing_counts(self) -> None:
        """PollResult distinguishes new saves from existing links."""
        result = PollResult(
            processed_jobs=[],
            new_job_count=5,
            existing_job_count=3,
            error_sources=[],
        )

        assert result.new_job_count == 5
        assert result.existing_job_count == 3

    def test_tracks_error_sources(self) -> None:
        """PollResult records sources that failed during fetch."""
        result = PollResult(
            processed_jobs=[],
            new_job_count=0,
            existing_job_count=0,
            error_sources=[_SOURCE_REMOTEOK, "TheMuse"],
        )

        assert _SOURCE_REMOTEOK in result.error_sources
        assert len(result.error_sources) == 2


# ---------------------------------------------------------------------------
# fetch_from_sources
# ---------------------------------------------------------------------------


class TestFetchFromSources:
    """Tests for parallel source fetching with fail-forward semantics."""

    async def test_fetches_from_all_enabled_sources(
        self,
        service,
        make_raw_job,
        make_adapter,
    ) -> None:
        """All enabled sources are queried and results keyed by source."""
        adzuna_job = make_raw_job(external_id="az-001", title="Job A")
        rok_job = make_raw_job(external_id="rok-001", title="Job B")

        def adapter_lookup(name):
            return {
                _SOURCE_ADZUNA: make_adapter([adzuna_job]),
                _SOURCE_REMOTEOK: make_adapter([rok_job]),
            }.get(name)

        with patch(_GET_ADAPTER, side_effect=adapter_lookup):
            results, errors = await service.fetch_from_sources(
                [_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
            )

        assert _SOURCE_ADZUNA in results
        assert _SOURCE_REMOTEOK in results
        assert errors == []

    async def test_transforms_raw_jobs_to_dicts(
        self,
        service,
        make_raw_job,
        make_adapter,
    ) -> None:
        """RawJob objects are converted to plain dicts with source_name."""
        raw = make_raw_job(
            external_id="az-001",
            title="Python Dev",
            company="Acme",
            location="Remote",
        )

        with patch(_GET_ADAPTER, return_value=make_adapter([raw])):
            results, _ = await service.fetch_from_sources([_SOURCE_ADZUNA])

        job = results[_SOURCE_ADZUNA][0]
        assert job["external_id"] == "az-001"
        assert job["title"] == "Python Dev"
        assert job["company"] == "Acme"
        assert job["source_name"] == _SOURCE_ADZUNA

    async def test_skips_unknown_adapters(self, service) -> None:
        """Unknown source names are skipped without error."""
        with patch(_GET_ADAPTER, return_value=None):
            results, errors = await service.fetch_from_sources(["UnknownSource"])

        assert results == {}
        assert errors == []

    async def test_continues_on_source_error(
        self,
        service,
        make_raw_job,
        make_adapter,
    ) -> None:
        """SourceError from one adapter doesn't block others (fail-forward)."""
        from app.services.scouter_errors import SourceError, SourceErrorType

        adzuna_job = make_raw_job(external_id="az-001")
        error = SourceError(_SOURCE_REMOTEOK, SourceErrorType.API_DOWN, "503 error")

        def adapter_lookup(name):
            return {
                _SOURCE_ADZUNA: make_adapter([adzuna_job]),
                _SOURCE_REMOTEOK: make_adapter(error),
            }.get(name)

        with patch(_GET_ADAPTER, side_effect=adapter_lookup):
            results, errors = await service.fetch_from_sources(
                [_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
            )

        assert _SOURCE_ADZUNA in results
        assert _SOURCE_REMOTEOK not in results
        assert _SOURCE_REMOTEOK in errors

    async def test_continues_on_unexpected_exception(
        self,
        service,
        make_raw_job,
        make_adapter,
    ) -> None:
        """Generic exceptions are caught; source recorded as error."""
        adzuna_job = make_raw_job(external_id="az-001")

        def adapter_lookup(name):
            return {
                _SOURCE_ADZUNA: make_adapter([adzuna_job]),
                _SOURCE_REMOTEOK: make_adapter(RuntimeError("unexpected")),
            }.get(name)

        with patch(_GET_ADAPTER, side_effect=adapter_lookup):
            results, errors = await service.fetch_from_sources(
                [_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
            )

        assert _SOURCE_ADZUNA in results
        assert _SOURCE_REMOTEOK in errors

    async def test_empty_sources_returns_empty(self, service) -> None:
        """Empty source list returns empty results and no errors."""
        results, errors = await service.fetch_from_sources([])

        assert results == {}
        assert errors == []


# ---------------------------------------------------------------------------
# run_poll — pipeline integration
# ---------------------------------------------------------------------------


class TestRunPoll:
    """Tests for the full poll orchestration pipeline."""

    async def test_returns_poll_result_with_new_jobs(self, service) -> None:
        """run_poll returns PollResult with enriched new jobs."""
        source_id = uuid4()
        raw_job = {
            "external_id": "a-1",
            "title": "Job A",
            "description": "desc",
            "source_name": _SOURCE_ADZUNA,
        }
        checked_job = {**raw_job, "source_id": str(source_id)}
        enriched_job = {**checked_job, "ghost_score": 25, "required_skills": []}

        with (
            patch.object(
                service,
                "fetch_from_sources",
                new_callable=AsyncMock,
                return_value=({_SOURCE_ADZUNA: [raw_job]}, []),
            ),
            patch(
                f"{_POOL_REPO}.resolve_source_id",
                new_callable=AsyncMock,
                return_value=source_id,
            ),
            patch(
                f"{_POOL_REPO}.check_job_in_pool",
                new_callable=AsyncMock,
                return_value=(False, checked_job),
            ),
            patch(
                f"{_ENRICHMENT}.enrich_jobs",
                new_callable=AsyncMock,
                return_value=[enriched_job],
            ),
            patch(
                f"{_POOL_REPO}.save_job_to_pool",
                new_callable=AsyncMock,
                return_value="saved-id",
            ),
        ):
            result = await service.run_poll([_SOURCE_ADZUNA])

        assert result.new_job_count == 1
        assert result.existing_job_count == 0
        assert len(result.processed_jobs) == 1

    async def test_links_existing_jobs_without_enrichment(self, service) -> None:
        """Existing pool jobs are linked but not re-enriched."""
        source_id = uuid4()
        raw_job = {
            "external_id": "old-1",
            "title": "Existing Job",
            "description": "desc",
            "source_name": _SOURCE_ADZUNA,
        }
        existing_job = {
            **raw_job,
            "source_id": str(source_id),
            "pool_job_posting_id": "existing-pool-id",
        }

        with (
            patch.object(
                service,
                "fetch_from_sources",
                new_callable=AsyncMock,
                return_value=({_SOURCE_ADZUNA: [raw_job]}, []),
            ),
            patch(
                f"{_POOL_REPO}.resolve_source_id",
                new_callable=AsyncMock,
                return_value=source_id,
            ),
            patch(
                f"{_POOL_REPO}.check_job_in_pool",
                new_callable=AsyncMock,
                return_value=(True, existing_job),
            ),
            patch(
                f"{_ENRICHMENT}.enrich_jobs",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_enrich,
            patch(
                f"{_POOL_REPO}.link_existing_job",
                new_callable=AsyncMock,
                return_value="existing-pool-id",
            ) as mock_link,
        ):
            result = await service.run_poll([_SOURCE_ADZUNA])

        assert result.new_job_count == 0
        assert result.existing_job_count == 1
        # Enrichment should only be called with new jobs (empty list)
        mock_enrich.assert_called_once_with([], provider=None)
        mock_link.assert_called_once()

    async def test_partitions_mixed_new_and_existing(self, service) -> None:
        """Mixed batch: new jobs get enriched+saved, existing get linked."""
        source_id = uuid4()
        new_raw = {
            "external_id": "new-1",
            "title": "New",
            "description": "d",
            "source_name": _SOURCE_ADZUNA,
        }
        old_raw = {
            "external_id": "old-1",
            "title": "Old",
            "description": "d",
            "source_name": _SOURCE_ADZUNA,
        }
        new_checked = {**new_raw, "source_id": str(source_id)}
        old_checked = {
            **old_raw,
            "source_id": str(source_id),
            "pool_job_posting_id": "pool-id",
        }

        async def check_mock(_db, job, _sid):
            if job["external_id"] == "new-1":
                return (False, new_checked)
            return (True, old_checked)

        enriched = {**new_checked, "ghost_score": 20, "required_skills": []}

        with (
            patch.object(
                service,
                "fetch_from_sources",
                new_callable=AsyncMock,
                return_value=({_SOURCE_ADZUNA: [new_raw, old_raw]}, []),
            ),
            patch(
                f"{_POOL_REPO}.resolve_source_id",
                new_callable=AsyncMock,
                return_value=source_id,
            ),
            patch(
                f"{_POOL_REPO}.check_job_in_pool",
                new_callable=AsyncMock,
                side_effect=check_mock,
            ),
            patch(
                f"{_ENRICHMENT}.enrich_jobs",
                new_callable=AsyncMock,
                return_value=[enriched],
            ),
            patch(
                f"{_POOL_REPO}.save_job_to_pool",
                new_callable=AsyncMock,
                return_value="saved-id",
            ),
            patch(
                f"{_POOL_REPO}.link_existing_job",
                new_callable=AsyncMock,
                return_value="pool-id",
            ),
        ):
            result = await service.run_poll([_SOURCE_ADZUNA])

        assert result.new_job_count == 1
        assert result.existing_job_count == 1
        assert len(result.processed_jobs) == 2

    async def test_includes_error_sources_in_result(self, service) -> None:
        """Error sources from fetch are propagated to PollResult."""
        with patch.object(
            service,
            "fetch_from_sources",
            new_callable=AsyncMock,
            return_value=({}, [_SOURCE_REMOTEOK]),
        ):
            result = await service.run_poll([_SOURCE_REMOTEOK])

        assert _SOURCE_REMOTEOK in result.error_sources

    async def test_empty_fetch_returns_zero_counts(self, service) -> None:
        """No jobs fetched returns PollResult with zero counts."""
        with patch.object(
            service,
            "fetch_from_sources",
            new_callable=AsyncMock,
            return_value=({}, []),
        ):
            result = await service.run_poll([_SOURCE_ADZUNA])

        assert result.new_job_count == 0
        assert result.existing_job_count == 0
        assert result.processed_jobs == []

    async def test_skips_jobs_with_unresolvable_source(self, service) -> None:
        """Jobs from unknown sources (resolve returns None) are skipped."""
        raw_job = {
            "external_id": "x-1",
            "title": "Job",
            "description": "d",
            "source_name": "UnknownSource",
        }

        with (
            patch.object(
                service,
                "fetch_from_sources",
                new_callable=AsyncMock,
                return_value=({"UnknownSource": [raw_job]}, []),
            ),
            patch(
                f"{_POOL_REPO}.resolve_source_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await service.run_poll(["UnknownSource"])

        assert result.new_job_count == 0
        assert result.processed_jobs == []

    async def test_calculates_poll_timestamps(self, service) -> None:
        """PollResult includes last_polled_at and next_poll_at."""
        with patch.object(
            service,
            "fetch_from_sources",
            new_callable=AsyncMock,
            return_value=({}, []),
        ):
            result = await service.run_poll([_SOURCE_ADZUNA], polling_frequency="daily")

        assert result.last_polled_at is not None
        assert result.next_poll_at is not None
        assert result.next_poll_at > result.last_polled_at

    async def test_weekly_frequency_extends_next_poll(self, service) -> None:
        """Weekly polling frequency sets next_poll_at ~7 days out."""
        with patch.object(
            service,
            "fetch_from_sources",
            new_callable=AsyncMock,
            return_value=({}, []),
        ):
            result = await service.run_poll(
                [_SOURCE_ADZUNA], polling_frequency="weekly"
            )

        delta = result.next_poll_at - result.last_polled_at
        assert delta >= timedelta(days=6, hours=23)

    async def test_save_failure_does_not_halt_batch(self, service) -> None:
        """If save_job_to_pool returns None, batch continues."""
        source_id = uuid4()
        jobs = [
            {
                "external_id": f"j-{i}",
                "title": f"Job {i}",
                "description": "d",
                "source_name": _SOURCE_ADZUNA,
            }
            for i in range(3)
        ]
        checked = [{**j, "source_id": str(source_id)} for j in jobs]
        enriched = [{**c, "ghost_score": 10, "required_skills": []} for c in checked]

        save_returns = ["id-1", None, "id-3"]

        with (
            patch.object(
                service,
                "fetch_from_sources",
                new_callable=AsyncMock,
                return_value=({_SOURCE_ADZUNA: jobs}, []),
            ),
            patch(
                f"{_POOL_REPO}.resolve_source_id",
                new_callable=AsyncMock,
                return_value=source_id,
            ),
            patch(
                f"{_POOL_REPO}.check_job_in_pool",
                new_callable=AsyncMock,
                side_effect=[(False, c) for c in checked],
            ),
            patch(
                f"{_ENRICHMENT}.enrich_jobs",
                new_callable=AsyncMock,
                return_value=enriched,
            ),
            patch(
                f"{_POOL_REPO}.save_job_to_pool",
                new_callable=AsyncMock,
                side_effect=save_returns,
            ),
        ):
            result = await service.run_poll([_SOURCE_ADZUNA])

        # All 3 jobs processed even though one save failed
        assert len(result.processed_jobs) == 3
        # Only 2 successfully saved (None return = failure)
        assert result.new_job_count == 2

    async def test_default_polling_frequency_is_daily(self, service) -> None:
        """Without explicit frequency, defaults to daily (~24h)."""
        with patch.object(
            service,
            "fetch_from_sources",
            new_callable=AsyncMock,
            return_value=({}, []),
        ):
            result = await service.run_poll([_SOURCE_ADZUNA])

        delta = result.next_poll_at - result.last_polled_at
        # Daily = 24 hours
        assert timedelta(hours=23) <= delta <= timedelta(hours=25)
