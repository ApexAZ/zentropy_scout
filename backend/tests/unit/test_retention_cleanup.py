"""Tests for retention cleanup service.

REQ-002 §5.1, REQ-005 §7: Verify data retention rules enforce correct
cleanup behavior — orphan PDFs purged after 7 days, resolved change flags
after 30 days, archived records after 180 days, expired jobs after 180 days
(favorites protected).
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BaseResume, Persona
from app.models.cover_letter import CoverLetter, SubmittedCoverLetterPDF
from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona_settings import PersonaChangeFlag
from app.models.resume import JobVariant, SubmittedResumePDF
from app.services.retention_cleanup import (
    AllCleanupResult,
    ArchivedRecordsCleanupResult,
    OrphanPdfCleanupResult,
    cleanup_archived_records,
    cleanup_expired_jobs,
    cleanup_orphan_pdfs,
    cleanup_resolved_change_flags,
    run_all_cleanups,
)
from tests.conftest import TEST_USER_ID

# SQL for creating cleanup functions (mirrors migration 007_cleanup_functions).
# Each function is a separate string because asyncpg does not support
# multiple statements in a single prepared statement.
# NOTE: If 007_cleanup_functions.py is updated, this SQL must be kept in sync.
_CLEANUP_FUNCTIONS = [
    """
    CREATE OR REPLACE FUNCTION cleanup_orphan_pdfs()
    RETURNS TABLE(deleted_resume_pdfs BIGINT, deleted_cover_letter_pdfs BIGINT)
    LANGUAGE plpgsql
    SET search_path = public
    AS $$
    DECLARE resume_count BIGINT; cover_letter_count BIGINT;
    BEGIN
        WITH deleted AS (
            DELETE FROM submitted_resume_pdfs
            WHERE application_id IS NULL AND generated_at < now() - interval '7 days'
            RETURNING id
        ) SELECT COUNT(*) INTO resume_count FROM deleted;
        WITH deleted AS (
            DELETE FROM submitted_cover_letter_pdfs
            WHERE application_id IS NULL AND generated_at < now() - interval '7 days'
            RETURNING id
        ) SELECT COUNT(*) INTO cover_letter_count FROM deleted;
        deleted_resume_pdfs := resume_count;
        deleted_cover_letter_pdfs := cover_letter_count;
        RETURN NEXT;
    END; $$
    """,
    """
    CREATE OR REPLACE FUNCTION cleanup_resolved_change_flags()
    RETURNS BIGINT
    LANGUAGE plpgsql
    SET search_path = public
    AS $$
    DECLARE deleted_count BIGINT;
    BEGIN
        WITH deleted AS (
            DELETE FROM persona_change_flags
            WHERE status = 'Resolved' AND resolved_at < now() - interval '30 days'
            RETURNING id
        ) SELECT COUNT(*) INTO deleted_count FROM deleted;
        RETURN deleted_count;
    END; $$
    """,
    """
    CREATE OR REPLACE FUNCTION cleanup_archived_records()
    RETURNS TABLE(deleted_job_variants BIGINT, deleted_cover_letters BIGINT)
    LANGUAGE plpgsql
    SET search_path = public
    AS $$
    DECLARE variant_count BIGINT; letter_count BIGINT;
    BEGIN
        WITH deleted AS (
            DELETE FROM job_variants
            WHERE archived_at IS NOT NULL AND archived_at < now() - interval '180 days'
            RETURNING id
        ) SELECT COUNT(*) INTO variant_count FROM deleted;
        WITH deleted AS (
            DELETE FROM cover_letters
            WHERE archived_at IS NOT NULL AND archived_at < now() - interval '180 days'
            RETURNING id
        ) SELECT COUNT(*) INTO letter_count FROM deleted;
        deleted_job_variants := variant_count;
        deleted_cover_letters := letter_count;
        RETURN NEXT;
    END; $$
    """,
    """
    CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
    RETURNS BIGINT
    LANGUAGE plpgsql
    SET search_path = public
    AS $$
    DECLARE deleted_count BIGINT;
    BEGIN
        WITH deleted AS (
            DELETE FROM job_postings
            WHERE status IN ('Expired', 'Dismissed')
              AND updated_at < now() - interval '180 days'
              AND is_favorite = false
            RETURNING id
        ) SELECT COUNT(*) INTO deleted_count FROM deleted;
        RETURN deleted_count;
    END; $$
    """,
    """
    CREATE OR REPLACE FUNCTION run_all_cleanups()
    RETURNS TABLE(
        orphan_resume_pdfs BIGINT, orphan_cover_letter_pdfs BIGINT,
        resolved_change_flags BIGINT, archived_job_variants BIGINT,
        archived_cover_letters BIGINT, expired_jobs BIGINT
    )
    LANGUAGE plpgsql
    SET search_path = public
    AS $$
    DECLARE
        pdf_result RECORD; flags_count BIGINT;
        archived_result RECORD; jobs_count BIGINT;
    BEGIN
        SELECT * INTO pdf_result FROM cleanup_orphan_pdfs();
        SELECT cleanup_resolved_change_flags() INTO flags_count;
        SELECT * INTO archived_result FROM cleanup_archived_records();
        SELECT cleanup_expired_jobs() INTO jobs_count;
        orphan_resume_pdfs := pdf_result.deleted_resume_pdfs;
        orphan_cover_letter_pdfs := pdf_result.deleted_cover_letter_pdfs;
        resolved_change_flags := flags_count;
        archived_job_variants := archived_result.deleted_job_variants;
        archived_cover_letters := archived_result.deleted_cover_letters;
        expired_jobs := jobs_count;
        RETURN NEXT;
    END; $$
    """,
]


@pytest_asyncio.fixture(autouse=True)
async def _create_cleanup_functions(db_session: AsyncSession):
    """Create PostgreSQL cleanup functions needed by retention tests.

    The test database uses Base.metadata.create_all which creates tables
    but not stored procedures from Alembic migrations. This fixture
    creates the cleanup functions before each test.
    """
    for sql in _CLEANUP_FUNCTIONS:
        await db_session.execute(text(sql))
    await db_session.commit()


# =============================================================================
# Shared Fixtures
# =============================================================================

_RETENTION_PERSONA_ID = uuid.UUID("00000000-0000-0000-0000-100000000001")
_RETENTION_JOB_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-100000000002")
_RETENTION_JOB_POSTING_ID = uuid.UUID("00000000-0000-0000-0000-100000000003")
_RETENTION_BASE_RESUME_ID = uuid.UUID("00000000-0000-0000-0000-100000000004")


@pytest_asyncio.fixture
async def retention_user(db_session: AsyncSession):
    """Create test user for retention tests."""
    from app.models import User

    user = User(id=TEST_USER_ID, email="retention@example.com")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def retention_persona(db_session: AsyncSession, retention_user):
    """Create test persona for retention tests."""
    persona = Persona(
        id=_RETENTION_PERSONA_ID,
        user_id=retention_user.id,
        email="retention@example.com",
        full_name="Retention Test User",
        phone="555-0000",
        home_city="Test City",
        home_state="TS",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.flush()
    return persona


@pytest_asyncio.fixture
async def retention_job_source(db_session: AsyncSession):
    """Create test job source for retention tests."""
    source = JobSource(
        id=_RETENTION_JOB_SOURCE_ID,
        source_name="RetentionTest",
        source_type="Manual",
        description="Source for retention tests",
    )
    db_session.add(source)
    await db_session.flush()
    return source


@pytest_asyncio.fixture
async def retention_job_posting(
    db_session: AsyncSession, retention_persona, retention_job_source
):
    """Create test job posting for retention tests."""
    posting = JobPosting(
        id=_RETENTION_JOB_POSTING_ID,
        persona_id=retention_persona.id,
        source_id=retention_job_source.id,
        job_title="Retention Engineer",
        company_name="Retention Corp",
        description="Test job for retention cleanup.",
        first_seen_date=date.today(),
        description_hash="retention_hash_001",
    )
    db_session.add(posting)
    await db_session.flush()
    return posting


@pytest_asyncio.fixture
async def retention_base_resume(db_session: AsyncSession, retention_persona):
    """Create test base resume for retention tests."""
    resume = BaseResume(
        id=_RETENTION_BASE_RESUME_ID,
        persona_id=retention_persona.id,
        name="Retention Test Resume",
        role_type="Engineer",
        summary="Test resume for retention cleanup.",
    )
    db_session.add(resume)
    await db_session.flush()
    return resume


# =============================================================================
# Orphan PDF Cleanup Tests (7-day retention)
# =============================================================================


class TestCleanupOrphanPdfs:
    """REQ-005 §7: Orphan PDF cleanup — 7-day retention."""

    @pytest.mark.asyncio
    async def test_deletes_old_orphan_resume_pdf(
        self,
        db_session: AsyncSession,
        retention_base_resume,
    ):
        """Orphan resume PDF older than 7 days is deleted."""
        old_pdf = SubmittedResumePDF(
            id=uuid.uuid4(),
            application_id=None,
            resume_source_type="Base",
            resume_source_id=retention_base_resume.id,
            file_name="old_orphan.pdf",
            file_binary=b"%PDF-old",
            generated_at=datetime.now(UTC) - timedelta(days=8),
        )
        db_session.add(old_pdf)
        await db_session.commit()

        result = await cleanup_orphan_pdfs(db_session)

        assert isinstance(result, OrphanPdfCleanupResult)
        assert result.deleted_resume_pdfs >= 1

        # Verify actually deleted from database
        check = await db_session.execute(
            select(SubmittedResumePDF).where(SubmittedResumePDF.id == old_pdf.id)
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_retains_recent_orphan_resume_pdf(
        self,
        db_session: AsyncSession,
        retention_base_resume,
    ):
        """Orphan resume PDF younger than 7 days is retained."""
        recent_pdf = SubmittedResumePDF(
            id=uuid.uuid4(),
            application_id=None,
            resume_source_type="Base",
            resume_source_id=retention_base_resume.id,
            file_name="recent_orphan.pdf",
            file_binary=b"%PDF-recent",
            generated_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(recent_pdf)
        await db_session.commit()

        await cleanup_orphan_pdfs(db_session)

        # Verify still exists
        check = await db_session.execute(
            select(SubmittedResumePDF).where(SubmittedResumePDF.id == recent_pdf.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_deletes_old_orphan_cover_letter_pdf(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_posting,
    ):
        """Orphan cover letter PDF older than 7 days is deleted."""
        cover_letter = CoverLetter(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            job_posting_id=retention_job_posting.id,
            draft_text="Test draft text for retention.",
            status="Draft",
        )
        db_session.add(cover_letter)
        await db_session.flush()

        old_pdf = SubmittedCoverLetterPDF(
            id=uuid.uuid4(),
            cover_letter_id=cover_letter.id,
            application_id=None,
            file_name="old_cover_letter.pdf",
            file_binary=b"%PDF-old-cl",
            generated_at=datetime.now(UTC) - timedelta(days=8),
        )
        db_session.add(old_pdf)
        await db_session.commit()

        result = await cleanup_orphan_pdfs(db_session)

        assert result.deleted_cover_letter_pdfs >= 1

        check = await db_session.execute(
            select(SubmittedCoverLetterPDF).where(
                SubmittedCoverLetterPDF.id == old_pdf.id
            )
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_orphans(
        self,
        db_session: AsyncSession,
        retention_persona,  # noqa: ARG002 - ensures user/persona exist
    ):
        """Cleanup returns zero counts when no orphan PDFs exist."""
        result = await cleanup_orphan_pdfs(db_session)

        assert result.deleted_resume_pdfs == 0
        assert result.deleted_cover_letter_pdfs == 0


# =============================================================================
# PersonaChangeFlag Cleanup Tests (30-day retention)
# =============================================================================


class TestCleanupResolvedChangeFlags:
    """REQ-005 §7: Resolved PersonaChangeFlag cleanup — 30-day retention."""

    @pytest.mark.asyncio
    async def test_deletes_old_resolved_flag(
        self,
        db_session: AsyncSession,
        retention_persona,
    ):
        """Resolved flag older than 30 days is deleted."""
        old_flag = PersonaChangeFlag(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            change_type="job_added",
            item_id=uuid.uuid4(),
            item_description="Old resolved job",
            status="Resolved",
            resolution="added_to_all",
            resolved_at=datetime.now(UTC) - timedelta(days=31),
        )
        db_session.add(old_flag)
        await db_session.commit()

        deleted_count = await cleanup_resolved_change_flags(db_session)

        assert deleted_count >= 1

        check = await db_session.execute(
            select(PersonaChangeFlag).where(PersonaChangeFlag.id == old_flag.id)
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_retains_recent_resolved_flag(
        self,
        db_session: AsyncSession,
        retention_persona,
    ):
        """Resolved flag younger than 30 days is retained."""
        recent_flag = PersonaChangeFlag(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            change_type="skill_added",
            item_id=uuid.uuid4(),
            item_description="Recent resolved skill",
            status="Resolved",
            resolution="skipped",
            resolved_at=datetime.now(UTC) - timedelta(days=29),
        )
        db_session.add(recent_flag)
        await db_session.commit()

        await cleanup_resolved_change_flags(db_session)

        check = await db_session.execute(
            select(PersonaChangeFlag).where(PersonaChangeFlag.id == recent_flag.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_retains_pending_flag(
        self,
        db_session: AsyncSession,
        retention_persona,
    ):
        """Pending (unresolved) flag is never deleted regardless of age."""
        pending_flag = PersonaChangeFlag(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            change_type="education_added",
            item_id=uuid.uuid4(),
            item_description="Old pending education",
            status="Pending",
            created_at=datetime.now(UTC) - timedelta(days=60),
        )
        db_session.add(pending_flag)
        await db_session.commit()

        await cleanup_resolved_change_flags(db_session)

        check = await db_session.execute(
            select(PersonaChangeFlag).where(PersonaChangeFlag.id == pending_flag.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_flags(
        self,
        db_session: AsyncSession,
        retention_persona,  # noqa: ARG002 - ensures user/persona exist
    ):
        """Cleanup returns zero when no resolved flags exist."""
        deleted_count = await cleanup_resolved_change_flags(db_session)

        assert deleted_count == 0


# =============================================================================
# Archived Records Cleanup Tests (180-day retention)
# =============================================================================


class TestCleanupArchivedRecords:
    """REQ-005 §7: Hard delete archived records — 180-day retention."""

    @pytest.mark.asyncio
    async def test_deletes_old_archived_job_variant(
        self,
        db_session: AsyncSession,
        retention_base_resume,
        retention_job_posting,
    ):
        """Archived job variant older than 180 days is hard deleted."""
        old_variant = JobVariant(
            id=uuid.uuid4(),
            base_resume_id=retention_base_resume.id,
            job_posting_id=retention_job_posting.id,
            summary="Old archived variant",
            status="Archived",
            archived_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(old_variant)
        await db_session.commit()

        result = await cleanup_archived_records(db_session)

        assert isinstance(result, ArchivedRecordsCleanupResult)
        assert result.deleted_job_variants >= 1

        check = await db_session.execute(
            select(JobVariant).where(JobVariant.id == old_variant.id)
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_retains_recently_archived_job_variant(
        self,
        db_session: AsyncSession,
        retention_base_resume,
        retention_job_posting,
    ):
        """Archived job variant younger than 180 days is retained."""
        recent_variant = JobVariant(
            id=uuid.uuid4(),
            base_resume_id=retention_base_resume.id,
            job_posting_id=retention_job_posting.id,
            summary="Recently archived variant",
            status="Archived",
            archived_at=datetime.now(UTC) - timedelta(days=179),
        )
        db_session.add(recent_variant)
        await db_session.commit()

        await cleanup_archived_records(db_session)

        check = await db_session.execute(
            select(JobVariant).where(JobVariant.id == recent_variant.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_deletes_old_archived_cover_letter(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_posting,
    ):
        """Archived cover letter older than 180 days is hard deleted."""
        old_letter = CoverLetter(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            job_posting_id=retention_job_posting.id,
            draft_text="Old archived cover letter.",
            status="Archived",
            archived_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(old_letter)
        await db_session.commit()

        result = await cleanup_archived_records(db_session)

        assert result.deleted_cover_letters >= 1

        check = await db_session.execute(
            select(CoverLetter).where(CoverLetter.id == old_letter.id)
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_retains_active_job_variant(
        self,
        db_session: AsyncSession,
        retention_base_resume,
        retention_job_posting,
    ):
        """Active (non-archived) job variant is never deleted."""
        active_variant = JobVariant(
            id=uuid.uuid4(),
            base_resume_id=retention_base_resume.id,
            job_posting_id=retention_job_posting.id,
            summary="Active variant should not be deleted",
            status="Draft",
        )
        db_session.add(active_variant)
        await db_session.commit()

        await cleanup_archived_records(db_session)

        check = await db_session.execute(
            select(JobVariant).where(JobVariant.id == active_variant.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_archived(
        self,
        db_session: AsyncSession,
        retention_persona,  # noqa: ARG002 - ensures user/persona exist
    ):
        """Cleanup returns zero counts when no archived records exist."""
        result = await cleanup_archived_records(db_session)

        assert result.deleted_job_variants == 0
        assert result.deleted_cover_letters == 0


# =============================================================================
# Expired Jobs Cleanup Tests (180-day retention, favorites protected)
# =============================================================================


class TestCleanupExpiredJobs:
    """REQ-005 §7: Hard delete expired/dismissed jobs — 180-day retention."""

    @pytest.mark.asyncio
    async def test_deletes_old_expired_job(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_source,
    ):
        """Expired job older than 180 days (not favorited) is hard deleted."""

        old_job = JobPosting(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            source_id=retention_job_source.id,
            job_title="Old Expired Job",
            company_name="Gone Corp",
            description="This job expired long ago.",
            first_seen_date=date.today() - timedelta(days=365),
            description_hash="expired_hash_001",
            status="Expired",
            is_favorite=False,
            updated_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(old_job)
        await db_session.commit()

        deleted_count = await cleanup_expired_jobs(db_session)

        assert deleted_count >= 1

        check = await db_session.execute(
            select(JobPosting).where(JobPosting.id == old_job.id)
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_deletes_old_dismissed_job(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_source,
    ):
        """Dismissed job older than 180 days (not favorited) is hard deleted."""

        dismissed_job = JobPosting(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            source_id=retention_job_source.id,
            job_title="Old Dismissed Job",
            company_name="Dismissed Corp",
            description="This job was dismissed long ago.",
            first_seen_date=date.today() - timedelta(days=365),
            description_hash="dismissed_hash_001",
            status="Dismissed",
            is_favorite=False,
            updated_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(dismissed_job)
        await db_session.commit()

        deleted_count = await cleanup_expired_jobs(db_session)

        assert deleted_count >= 1

        check = await db_session.execute(
            select(JobPosting).where(JobPosting.id == dismissed_job.id)
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_retains_recently_expired_job(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_source,
    ):
        """Expired job younger than 180 days is retained."""

        recent_job = JobPosting(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            source_id=retention_job_source.id,
            job_title="Recent Expired Job",
            company_name="Recent Corp",
            description="This job expired recently.",
            first_seen_date=date.today() - timedelta(days=90),
            description_hash="recent_expired_hash",
            status="Expired",
            is_favorite=False,
            updated_at=datetime.now(UTC) - timedelta(days=179),
        )
        db_session.add(recent_job)
        await db_session.commit()

        await cleanup_expired_jobs(db_session)

        check = await db_session.execute(
            select(JobPosting).where(JobPosting.id == recent_job.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_retains_favorited_expired_job(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_source,
    ):
        """Favorited expired job is protected from deletion regardless of age."""

        fav_job = JobPosting(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            source_id=retention_job_source.id,
            job_title="Favorited Expired Job",
            company_name="Fav Corp",
            description="This job is favorited so protected.",
            first_seen_date=date.today() - timedelta(days=365),
            description_hash="fav_expired_hash",
            status="Expired",
            is_favorite=True,
            updated_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(fav_job)
        await db_session.commit()

        await cleanup_expired_jobs(db_session)

        check = await db_session.execute(
            select(JobPosting).where(JobPosting.id == fav_job.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_retains_active_job(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_job_source,
    ):
        """Active (Discovered) job is never deleted by cleanup."""

        active_job = JobPosting(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            source_id=retention_job_source.id,
            job_title="Active Job",
            company_name="Active Corp",
            description="This job is still active.",
            first_seen_date=date.today(),
            description_hash="active_hash",
            status="Discovered",
            is_favorite=False,
        )
        db_session.add(active_job)
        await db_session.commit()

        await cleanup_expired_jobs(db_session)

        check = await db_session.execute(
            select(JobPosting).where(JobPosting.id == active_job.id)
        )
        assert check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_expired(
        self,
        db_session: AsyncSession,
        retention_persona,  # noqa: ARG002 - ensures user/persona exist
    ):
        """Cleanup returns zero when no expired jobs exist."""
        deleted_count = await cleanup_expired_jobs(db_session)

        assert deleted_count == 0


# =============================================================================
# Run All Cleanups Tests
# =============================================================================


class TestRunAllCleanups:
    """REQ-005 §7: Master cleanup function runs all four cleanup jobs."""

    @pytest.mark.asyncio
    async def test_returns_aggregate_results(
        self,
        db_session: AsyncSession,
        retention_persona,  # noqa: ARG002 - ensures user/persona exist
    ):
        """Run all cleanups returns AllCleanupResult with zero counts when empty."""
        result = await run_all_cleanups(db_session)

        assert isinstance(result, AllCleanupResult)
        assert result.orphan_resume_pdfs == 0
        assert result.orphan_cover_letter_pdfs == 0
        assert result.resolved_change_flags == 0
        assert result.archived_job_variants == 0
        assert result.archived_cover_letters == 0
        assert result.expired_jobs == 0

    @pytest.mark.asyncio
    async def test_cleans_all_categories(
        self,
        db_session: AsyncSession,
        retention_persona,
        retention_base_resume,
        retention_job_posting,
        retention_job_source,
    ):
        """Run all cleanups processes all four retention categories."""

        # 1. Old orphan resume PDF
        old_pdf = SubmittedResumePDF(
            id=uuid.uuid4(),
            application_id=None,
            resume_source_type="Base",
            resume_source_id=retention_base_resume.id,
            file_name="all_cleanup_orphan.pdf",
            file_binary=b"%PDF-all",
            generated_at=datetime.now(UTC) - timedelta(days=8),
        )
        db_session.add(old_pdf)

        # 2. Old resolved change flag
        old_flag = PersonaChangeFlag(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            change_type="certification_added",
            item_id=uuid.uuid4(),
            item_description="Old cert",
            status="Resolved",
            resolution="added_to_all",
            resolved_at=datetime.now(UTC) - timedelta(days=31),
        )
        db_session.add(old_flag)

        # 3. Old archived job variant
        old_variant = JobVariant(
            id=uuid.uuid4(),
            base_resume_id=retention_base_resume.id,
            job_posting_id=retention_job_posting.id,
            summary="All-cleanup archived variant",
            status="Archived",
            archived_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(old_variant)

        # 4. Old expired job
        old_job = JobPosting(
            id=uuid.uuid4(),
            persona_id=retention_persona.id,
            source_id=retention_job_source.id,
            job_title="All Cleanup Expired",
            company_name="Cleanup Corp",
            description="Expired for all cleanup test.",
            first_seen_date=date.today() - timedelta(days=365),
            description_hash="all_cleanup_hash",
            status="Expired",
            is_favorite=False,
            updated_at=datetime.now(UTC) - timedelta(days=181),
        )
        db_session.add(old_job)

        await db_session.commit()

        result = await run_all_cleanups(db_session)

        assert result.orphan_resume_pdfs >= 1
        assert result.resolved_change_flags >= 1
        assert result.archived_job_variants >= 1
        assert result.expired_jobs >= 1
