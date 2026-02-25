"""Tests for JobPoolRepository.

REQ-016 §6.4: Shared pool operations — check, save, link, resolve source.
Extracts pool logic from scouter_graph.py into a standalone repository.
"""

import hashlib
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.repositories.job_pool_repository import (
    JobPoolRepository,
    _build_dedup_job_data,
    _compute_description_hash,
)

_TODAY = date.today()
_HASH_A = "a" * 64
_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job() -> dict:
    """Raw job dict as produced by source adapters."""
    return {
        "external_id": "ext-001",
        "title": "Software Engineer",
        "company": "Acme Corp",
        "description": "Build great software",
        "source_url": "https://example.com/job/1",
        "location": "Remote",
        "salary_min": 100000,
        "salary_max": 150000,
        "posted_date": _TODAY,
        "source_name": "Adzuna",
    }


# ---------------------------------------------------------------------------
# _compute_description_hash
# ---------------------------------------------------------------------------


class TestComputeDescriptionHash:
    """Tests for SHA-256 description hashing."""

    def test_returns_sha256_hex_digest(self):
        """Hash is a 64-character hex string."""
        result = _compute_description_hash("some text")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_text_produces_same_hash(self):
        """Deterministic — same input, same output."""
        h1 = _compute_description_hash("Build great software")
        h2 = _compute_description_hash("Build great software")
        assert h1 == h2

    def test_different_text_produces_different_hash(self):
        """Different inputs produce different outputs."""
        h1 = _compute_description_hash("Build great software")
        h2 = _compute_description_hash("Analyze data trends")
        assert h1 != h2

    def test_matches_stdlib_sha256(self):
        """Result matches hashlib.sha256 directly."""
        text = "Build great software"
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert _compute_description_hash(text) == expected


# ---------------------------------------------------------------------------
# _build_dedup_job_data
# ---------------------------------------------------------------------------


class TestBuildDedupJobData:
    """Tests for transforming raw job dicts into dedup service input."""

    def test_includes_required_fields(self, sample_job: dict):
        """Required fields are mapped from job dict."""
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(sample_job, source_id)

        assert result["source_id"] == source_id
        assert result["job_title"] == "Software Engineer"
        assert result["company_name"] == "Acme Corp"
        assert result["description"] == "Build great software"
        assert result["first_seen_date"] == _TODAY

    def test_computes_description_hash(self, sample_job: dict):
        """Description hash is computed from description text."""
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(sample_job, source_id)
        expected_hash = hashlib.sha256(b"Build great software").hexdigest()
        assert result["description_hash"] == expected_hash

    def test_includes_optional_fields(self, sample_job: dict):
        """Optional fields are passed through."""
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(sample_job, source_id)

        assert result["external_id"] == "ext-001"
        assert result["source_url"] == "https://example.com/job/1"
        assert result["location"] == "Remote"
        assert result["salary_min"] == 100000
        assert result["salary_max"] == 150000

    def test_handles_missing_optional_fields(self):
        """Missing optional fields default to None."""
        minimal_job = {"description": "Minimal job"}
        source_id = uuid.uuid4()
        result = _build_dedup_job_data(minimal_job, source_id)

        assert result["job_title"] == ""
        assert result["company_name"] == ""
        assert result["external_id"] is None
        assert result["location"] is None


# ---------------------------------------------------------------------------
# check_job_in_pool
# ---------------------------------------------------------------------------


class TestCheckJobInPool:
    """Tests for pool existence check (two-tier lookup)."""

    async def test_new_job_not_in_pool(
        self, db_session: AsyncSession, job_source: JobSource, sample_job: dict
    ):
        """Job not in pool returns (False, enriched_job)."""
        is_existing, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, sample_job, job_source.id
        )

        assert is_existing is False
        assert enriched["source_id"] == str(job_source.id)
        assert "pool_job_posting_id" not in enriched

    async def test_existing_by_external_id(
        self, db_session: AsyncSession, job_source: JobSource, sample_job: dict
    ):
        """Job found by source_id + external_id returns (True, enriched)."""
        # Create a job posting in the pool with matching external_id
        jp = JobPosting(
            source_id=job_source.id,
            external_id="ext-001",
            job_title="Software Engineer",
            company_name="Acme Corp",
            description="Build great software",
            description_hash=_HASH_A,
            first_seen_date=_TODAY,
        )
        db_session.add(jp)
        await db_session.flush()
        await db_session.refresh(jp)

        is_existing, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, sample_job, job_source.id
        )

        assert is_existing is True
        assert enriched["pool_job_posting_id"] == str(jp.id)
        assert enriched["source_id"] == str(job_source.id)

    async def test_existing_by_description_hash(
        self, db_session: AsyncSession, job_source: JobSource
    ):
        """Job found by description hash (tier 2) returns (True, enriched)."""
        description = "Unique job description for hash test"
        desc_hash = hashlib.sha256(description.encode()).hexdigest()

        jp = JobPosting(
            source_id=job_source.id,
            external_id="different-ext-id",
            job_title="Backend Developer",
            company_name="HashCo",
            description=description,
            description_hash=desc_hash,
            first_seen_date=_TODAY,
        )
        db_session.add(jp)
        await db_session.flush()
        await db_session.refresh(jp)

        # Job with different external_id but same description
        job = {
            "external_id": "no-match-ext-id",
            "description": description,
            "source_name": "TestSource",
        }

        is_existing, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, job, job_source.id
        )

        assert is_existing is True
        assert enriched["pool_job_posting_id"] == str(jp.id)

    async def test_no_external_id_skips_tier1(
        self, db_session: AsyncSession, job_source: JobSource
    ):
        """Empty external_id skips tier-1 lookup, uses hash only."""
        description = "Job with no external ID"
        desc_hash = hashlib.sha256(description.encode()).hexdigest()

        jp = JobPosting(
            source_id=job_source.id,
            job_title="No ExtID Job",
            company_name="NoCo",
            description=description,
            description_hash=desc_hash,
            first_seen_date=_TODAY,
        )
        db_session.add(jp)
        await db_session.flush()
        await db_session.refresh(jp)

        job = {"external_id": "", "description": description}

        is_existing, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, job, job_source.id
        )

        assert is_existing is True
        assert enriched["pool_job_posting_id"] == str(jp.id)

    async def test_preserves_original_job_data(
        self, db_session: AsyncSession, job_source: JobSource, sample_job: dict
    ):
        """Enriched result preserves all original job fields."""
        _, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, sample_job, job_source.id
        )

        assert enriched["title"] == "Software Engineer"
        assert enriched["company"] == "Acme Corp"
        assert enriched["location"] == "Remote"


# ---------------------------------------------------------------------------
# resolve_source_id
# ---------------------------------------------------------------------------


class TestResolveSourceId:
    """Tests for source name → UUID resolution."""

    async def test_returns_existing_source_id(
        self, db_session: AsyncSession, job_source: JobSource
    ):
        """Known source in DB returns its UUID."""
        result = await JobPoolRepository.resolve_source_id(
            db_session, job_source.source_name
        )
        assert result == job_source.id

    async def test_auto_creates_adzuna(self, db_session: AsyncSession):
        """Adzuna is auto-created when not in DB."""
        result = await JobPoolRepository.resolve_source_id(db_session, "Adzuna")
        assert result is not None
        # Verify it's a valid UUID by using it in a DB lookup
        source = await db_session.get(JobSource, result)
        assert source is not None
        assert source.source_name == "Adzuna"

    async def test_auto_creates_remoteok(self, db_session: AsyncSession):
        """RemoteOK is auto-created when not in DB."""
        result = await JobPoolRepository.resolve_source_id(db_session, "RemoteOK")
        assert result is not None

    async def test_auto_creates_usajobs(self, db_session: AsyncSession):
        """USAJobs is auto-created when not in DB."""
        result = await JobPoolRepository.resolve_source_id(db_session, "USAJobs")
        assert result is not None

    async def test_returns_none_for_unknown_source(self, db_session: AsyncSession):
        """Unknown source name returns None (not auto-created)."""
        result = await JobPoolRepository.resolve_source_id(db_session, "UnknownSource")
        assert result is None

    async def test_created_source_has_api_type(self, db_session: AsyncSession):
        """Auto-created source has source_type='API'."""
        source_id = await JobPoolRepository.resolve_source_id(db_session, "TheMuse")
        assert source_id is not None

        source = await db_session.get(JobSource, source_id)
        assert source is not None
        assert source.source_type == "API"


# ---------------------------------------------------------------------------
# save_job_to_pool
# ---------------------------------------------------------------------------


class TestSaveJobToPool:
    """Tests for saving new jobs via dedup pipeline."""

    async def test_returns_job_posting_id_on_success(
        self, db_session: AsyncSession, sample_job: dict
    ):
        """Successful save returns the job posting ID string."""
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = uuid.uuid4()
        mock_outcome.action = "created"

        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ):
            source_id = uuid.uuid4()
            sample_job["source_id"] = str(source_id)
            result = await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, uuid.uuid4(), uuid.uuid4()
            )

        assert result == str(mock_outcome.job_posting.id)

    async def test_calls_dedup_with_scouter_discovery_method(
        self, db_session: AsyncSession, sample_job: dict
    ):
        """Dedup service is called with discovery_method='scouter'."""
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = uuid.uuid4()

        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ) as mock_dedup:
            source_id = uuid.uuid4()
            sample_job["source_id"] = str(source_id)
            persona_id = uuid.uuid4()
            user_id = uuid.uuid4()

            await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, persona_id, user_id
            )

            mock_dedup.assert_called_once()
            call_kwargs = mock_dedup.call_args.kwargs
            assert call_kwargs["discovery_method"] == "scouter"
            assert call_kwargs["persona_id"] == persona_id
            assert call_kwargs["user_id"] == user_id

    async def test_returns_none_on_value_error(
        self, db_session: AsyncSession, sample_job: dict
    ):
        """ValueError during save returns None."""
        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            side_effect=ValueError("bad data"),
        ):
            sample_job["source_id"] = str(uuid.uuid4())
            result = await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, uuid.uuid4(), uuid.uuid4()
            )

        assert result is None

    async def test_returns_none_on_unexpected_error(
        self, db_session: AsyncSession, sample_job: dict
    ):
        """Unexpected exception during save returns None."""
        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ):
            sample_job["source_id"] = str(uuid.uuid4())
            result = await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, uuid.uuid4(), uuid.uuid4()
            )

        assert result is None


# ---------------------------------------------------------------------------
# link_existing_job
# ---------------------------------------------------------------------------


class TestLinkExistingJob:
    """Tests for linking existing pool jobs to a persona."""

    async def test_returns_pool_id_on_success(self, db_session: AsyncSession):
        """Successful link returns the pool_job_posting_id."""
        mock_outcome = MagicMock()

        pool_id = str(uuid.uuid4())
        job = {
            "pool_job_posting_id": pool_id,
            "source_id": str(uuid.uuid4()),
            "description": "Existing job",
            "title": "Engineer",
            "company": "PoolCo",
        }

        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ):
            result = await JobPoolRepository.link_existing_job(
                db_session, job, uuid.uuid4(), uuid.uuid4()
            )

        assert result == pool_id

    async def test_returns_none_on_error(self, db_session: AsyncSession):
        """Error during linking returns None."""
        job = {
            "pool_job_posting_id": str(uuid.uuid4()),
            "source_id": str(uuid.uuid4()),
            "description": "Existing job",
            "title": "Engineer",
            "company": "PoolCo",
        }

        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            side_effect=ValueError("bad link"),
        ):
            result = await JobPoolRepository.link_existing_job(
                db_session, job, uuid.uuid4(), uuid.uuid4()
            )

        assert result is None

    async def test_calls_dedup_with_scouter_method(self, db_session: AsyncSession):
        """Link uses scouter discovery method."""
        mock_outcome = MagicMock()
        job = {
            "pool_job_posting_id": str(uuid.uuid4()),
            "source_id": str(uuid.uuid4()),
            "description": "Link test",
            "title": "Dev",
            "company": "LinkCo",
        }

        with patch(
            "app.repositories.job_pool_repository.deduplicate_and_save",
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ) as mock_dedup:
            await JobPoolRepository.link_existing_job(
                db_session, job, uuid.uuid4(), uuid.uuid4()
            )

            call_kwargs = mock_dedup.call_args.kwargs
            assert call_kwargs["discovery_method"] == "scouter"
