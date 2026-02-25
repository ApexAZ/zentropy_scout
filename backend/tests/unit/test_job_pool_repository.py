"""Tests for JobPoolRepository check and resolve operations.

REQ-016 §6.4: Pool existence check (two-tier) and source resolution.
Save/link tests are in test_job_pool_repository_dedup.py.
"""

import hashlib
from datetime import date
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.repositories.job_pool_repository import JobPoolRepository

_TODAY = date.today()
# Intentionally non-matching hash — ensures tier-1 (external_id) lookup
# exercises a separate code path from tier-2 (description hash) lookup.
_HASH_A = "a" * 64


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job() -> dict[str, Any]:
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
# check_job_in_pool
# ---------------------------------------------------------------------------


class TestCheckJobInPool:
    """Tests for pool existence check (two-tier lookup)."""

    async def test_new_job_not_in_pool(
        self,
        db_session: AsyncSession,
        job_source: JobSource,
        sample_job: dict[str, Any],
    ):
        """Job not in pool returns (False, enriched_job)."""
        is_existing, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, sample_job, job_source.id
        )

        assert is_existing is False
        assert enriched["source_id"] == str(job_source.id)
        assert "pool_job_posting_id" not in enriched

    async def test_existing_by_external_id(
        self,
        db_session: AsyncSession,
        job_source: JobSource,
        sample_job: dict[str, Any],
    ):
        """Job found by source_id + external_id returns (True, enriched)."""
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

        job: dict[str, Any] = {
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

        job: dict[str, Any] = {"external_id": "", "description": description}

        is_existing, enriched = await JobPoolRepository.check_job_in_pool(
            db_session, job, job_source.id
        )

        assert is_existing is True
        assert enriched["pool_job_posting_id"] == str(jp.id)

    async def test_preserves_original_job_data(
        self,
        db_session: AsyncSession,
        job_source: JobSource,
        sample_job: dict[str, Any],
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
    """Tests for source name to UUID resolution."""

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
