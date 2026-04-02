"""Tests for JobPostingRepository.

REQ-015 §6, §9: Global CRUD and dedup lookups for the shared job pool.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.repositories.job_posting_repository import JobPostingRepository

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")
_TODAY = date.today()
_HASH_A = "a" * 64
_HASH_B = "b" * 64

# job_source fixture provided by tests/unit/conftest.py


@pytest_asyncio.fixture
async def job_posting(db_session: AsyncSession, job_source: JobSource) -> JobPosting:
    """Create a test job posting in the shared pool."""
    jp = JobPosting(
        source_id=job_source.id,
        external_id="ext-001",
        job_title="Software Engineer",
        company_name="Acme Corp",
        description="Build great things",
        description_hash=_HASH_A,
        first_seen_date=_TODAY,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


class TestGetById:
    """Test JobPostingRepository.get_by_id()."""

    async def test_returns_job_when_found(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """Existing job posting is returned by ID."""
        result = await JobPostingRepository.get_by_id(db_session, job_posting.id)
        assert result is not None
        assert result.id == job_posting.id
        assert result.job_title == "Software Engineer"

    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Non-existent ID returns None."""
        result = await JobPostingRepository.get_by_id(db_session, _MISSING_UUID)
        assert result is None


class TestGetBySourceAndExternalId:
    """Test JobPostingRepository.get_by_source_and_external_id()."""

    async def test_returns_job_when_found(
        self, db_session: AsyncSession, job_posting: JobPosting, job_source: JobSource
    ):
        """Matching source_id + external_id returns job."""
        result = await JobPostingRepository.get_by_source_and_external_id(
            db_session, source_id=job_source.id, external_id="ext-001"
        )
        assert result is not None
        assert result.id == job_posting.id

    async def test_returns_none_wrong_source(
        self,
        db_session: AsyncSession,
        job_posting: JobPosting,  # noqa: ARG002
    ):
        """Wrong source_id returns None."""
        result = await JobPostingRepository.get_by_source_and_external_id(
            db_session, source_id=_MISSING_UUID, external_id="ext-001"
        )
        assert result is None

    async def test_returns_none_wrong_external_id(
        self,
        db_session: AsyncSession,
        job_posting: JobPosting,  # noqa: ARG002
        job_source: JobSource,
    ):
        """Wrong external_id returns None."""
        result = await JobPostingRepository.get_by_source_and_external_id(
            db_session, source_id=job_source.id, external_id="nonexistent"
        )
        assert result is None

    async def test_returns_none_when_no_jobs(self, db_session: AsyncSession):
        """Empty table returns None."""
        result = await JobPostingRepository.get_by_source_and_external_id(
            db_session, source_id=_MISSING_UUID, external_id="ext-001"
        )
        assert result is None


class TestGetByDescriptionHash:
    """Test JobPostingRepository.get_by_description_hash()."""

    async def test_returns_job_when_found(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """Matching description_hash returns job."""
        result = await JobPostingRepository.get_by_description_hash(db_session, _HASH_A)
        assert result is not None
        assert result.id == job_posting.id

    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Non-matching hash returns None."""
        result = await JobPostingRepository.get_by_description_hash(db_session, _HASH_B)
        assert result is None


class TestCreate:
    """Test JobPostingRepository.create()."""

    async def test_rejects_unknown_optional_fields(
        self, db_session: AsyncSession, job_source: JobSource
    ):
        """Unknown optional field names raise ValueError."""
        with pytest.raises(ValueError, match="not_a_field"):
            await JobPostingRepository.create(
                db_session,
                source_id=job_source.id,
                job_title="Bad",
                company_name="BadCo",
                description="Bad desc",
                description_hash="f" * 64,
                first_seen_date=_TODAY,
                not_a_field="bad",
            )


class TestUpdate:
    """Test JobPostingRepository.update()."""

    async def test_updates_is_active(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """is_active can be toggled."""
        result = await JobPostingRepository.update(
            db_session, job_posting.id, is_active=False
        )
        assert result is not None
        assert result.is_active is False

    async def test_updates_ghost_score(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """ghost_score can be updated."""
        result = await JobPostingRepository.update(
            db_session, job_posting.id, ghost_score=75
        )
        assert result is not None
        assert result.ghost_score == 75

    async def test_updates_repost_fields(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """Repost detection fields can be updated."""
        prev_ids = [str(uuid.uuid4())]
        result = await JobPostingRepository.update(
            db_session,
            job_posting.id,
            repost_count=2,
            previous_posting_ids=prev_ids,
        )
        assert result is not None
        assert result.repost_count == 2
        assert result.previous_posting_ids == prev_ids

    async def test_updates_also_found_on(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """also_found_on JSONB can be updated (server-side dedup tracking)."""
        new_sources = {"sources": [{"name": "Indeed", "url": "https://indeed.com/j/1"}]}
        result = await JobPostingRepository.update(
            db_session, job_posting.id, also_found_on=new_sources
        )
        assert result is not None
        assert result.also_found_on == new_sources

    async def test_returns_none_for_nonexistent(self, db_session: AsyncSession):
        """Update on non-existent ID returns None."""
        result = await JobPostingRepository.update(
            db_session, _MISSING_UUID, is_active=False
        )
        assert result is None

    async def test_rejects_unknown_fields(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """Unknown field names raise ValueError."""
        with pytest.raises(ValueError, match="not_a_field"):
            await JobPostingRepository.update(
                db_session, job_posting.id, not_a_field="bad"
            )

    async def test_rejects_id_update(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """id field cannot be updated."""
        with pytest.raises(ValueError, match="id"):
            await JobPostingRepository.update(
                db_session,
                job_posting.id,
                id=uuid.uuid4(),  # pyright: ignore[reportArgumentType]
            )

    async def test_rejects_source_id_update(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """source_id cannot be changed after creation."""
        with pytest.raises(ValueError, match="source_id"):
            await JobPostingRepository.update(
                db_session,
                job_posting.id,
                source_id=uuid.uuid4(),  # pyright: ignore[reportArgumentType]
            )

    async def test_preserves_unmodified_fields(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """Fields not passed to update remain unchanged."""
        await JobPostingRepository.update(db_session, job_posting.id, ghost_score=50)
        result = await JobPostingRepository.get_by_id(db_session, job_posting.id)
        assert result is not None
        assert result.ghost_score == 50
        assert result.job_title == "Software Engineer"


class TestDeactivate:
    """Test JobPostingRepository.deactivate()."""

    async def test_sets_is_active_false(
        self, db_session: AsyncSession, job_posting: JobPosting
    ):
        """Deactivate sets is_active=False."""
        result = await JobPostingRepository.deactivate(db_session, job_posting.id)
        assert result is not None
        assert result.is_active is False

    async def test_returns_none_for_nonexistent(self, db_session: AsyncSession):
        """Deactivate on non-existent ID returns None."""
        result = await JobPostingRepository.deactivate(db_session, _MISSING_UUID)
        assert result is None
