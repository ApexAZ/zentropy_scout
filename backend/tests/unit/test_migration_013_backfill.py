"""Tests for migration 013: backfill persona_jobs from existing job_postings.

REQ-015 §11 steps 4–5: Verifies that the migration correctly populates
persona_jobs from existing job_postings data and backfills is_active.
This is a data-only migration — no DDL changes.

Step 4: INSERT INTO persona_jobs SELECT from job_postings
  - 'Expired' status → 'Discovered' (expiry tracked by is_active)
  - discovery_method = 'scouter' for all existing records
  - discovered_at = first_seen_date
  - scored_at = updated_at when fit_score IS NOT NULL

Step 5: UPDATE job_postings SET is_active = false WHERE status = 'Expired'
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)

# Reusable SQL fragments
_INSERT_USER = text(
    "INSERT INTO users (id, email, created_at, updated_at) "
    "VALUES (:id, :email, now(), now())"
)
_INSERT_PERSONA = text(
    "INSERT INTO personas "
    "(id, user_id, email, full_name, phone, home_city, home_state, home_country, "
    "created_at, updated_at) "
    "VALUES (:id, :user_id, :email, 'Test User', '555-0100', 'City', 'State', 'US', "
    "now(), now())"
)
_INSERT_JOB_SOURCE = text(
    "INSERT INTO job_sources (id, source_name, source_type, description, created_at, updated_at) "
    "VALUES (:id, :name, 'API', 'Test source', now(), now())"
)
_INSERT_JOB_POSTING = text(
    "INSERT INTO job_postings "
    "(id, persona_id, source_id, external_id, job_title, company_name, description, "
    "description_hash, first_seen_date, status, is_favorite, fit_score, stretch_score, "
    "failed_non_negotiables, score_details, dismissed_at, "
    "created_at, updated_at) "
    "VALUES (:id, :persona_id, :source_id, :external_id, :job_title, :company_name, "
    "'Job description', :desc_hash, :first_seen_date, :status, :is_favorite, "
    ":fit_score, :stretch_score, :failed_non_negotiables, :score_details, :dismissed_at, "
    ":created_at, :updated_at)"
)

# Reusable SELECT queries (extracted to avoid S1192 duplication)
_SELECT_PJ_STATUS = text("SELECT status FROM persona_jobs WHERE job_posting_id = :jid")
_COUNT_PERSONA_JOBS = text("SELECT COUNT(*) FROM persona_jobs")
_SELECT_PJ_IS_FAVORITE = text(
    "SELECT is_favorite FROM persona_jobs WHERE job_posting_id = :jid"
)
_SELECT_PJ_DISMISSED_AT = text(
    "SELECT dismissed_at FROM persona_jobs WHERE job_posting_id = :jid"
)
_SELECT_PJ_SCORED_AT = text(
    "SELECT scored_at FROM persona_jobs WHERE job_posting_id = :jid"
)
_SELECT_JP_IS_ACTIVE = text("SELECT is_active FROM job_postings WHERE id = :id")


# =============================================================================
# Helpers
# =============================================================================


async def _reset_schema(conn: AsyncConnection) -> None:
    """Drop and recreate public schema with required extensions."""
    await conn.execute(text("DROP SCHEMA public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _patch_settings_for_test_db() -> str:
    """Patch settings.database_name so alembic migrates the test DB."""
    original = settings.database_name
    settings.database_name = f"{original}_test"
    return original


def _create_alembic_config() -> Config:
    """Create alembic Config without ini file."""
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    return cfg


async def _seed_job_postings(
    engine: AsyncEngine,
) -> dict[str, uuid.UUID | list[uuid.UUID]]:
    """Insert test data at migration 012 level (pre-backfill).

    Creates job postings with various statuses to test backfill behavior.
    Returns dict with IDs for verification.
    """
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    user_id = uuid.uuid4()
    persona_id = uuid.uuid4()
    source_id = uuid.uuid4()

    discovered_id = uuid.uuid4()
    dismissed_id = uuid.uuid4()
    applied_id = uuid.uuid4()
    expired_id = uuid.uuid4()
    no_score_id = uuid.uuid4()

    async with session_factory() as session:
        await session.execute(
            _INSERT_USER, {"id": user_id, "email": "backfill@example.com"}
        )
        await session.execute(
            _INSERT_PERSONA,
            {"id": persona_id, "user_id": user_id, "email": "bp@example.com"},
        )
        await session.execute(
            _INSERT_JOB_SOURCE, {"id": source_id, "name": "BackfillSource"}
        )

        # Discovered job with scores
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": discovered_id,
                "persona_id": persona_id,
                "source_id": source_id,
                "external_id": "ext-disc",
                "job_title": "Discovered Job",
                "company_name": "DiscCorp",
                "desc_hash": "d" * 64,
                "first_seen_date": date(2026, 1, 15),
                "status": "Discovered",
                "is_favorite": True,
                "fit_score": 85,
                "stretch_score": 30,
                "failed_non_negotiables": json.dumps(["remote_only"]),
                "score_details": json.dumps({"overall": 85}),
                "dismissed_at": None,
                "created_at": datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC),
            },
        )

        # Dismissed job with dismissed_at timestamp
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": dismissed_id,
                "persona_id": persona_id,
                "source_id": source_id,
                "external_id": "ext-dism",
                "job_title": "Dismissed Job",
                "company_name": "DismCorp",
                "desc_hash": "e" * 64,
                "first_seen_date": date(2026, 1, 10),
                "status": "Dismissed",
                "is_favorite": False,
                "fit_score": 40,
                "stretch_score": 60,
                "failed_non_negotiables": None,
                "score_details": None,
                "dismissed_at": datetime(2026, 1, 12, 15, 0, 0, tzinfo=UTC),
                "created_at": datetime(2026, 1, 10, 9, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 12, 15, 0, 0, tzinfo=UTC),
            },
        )

        # Applied job
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": applied_id,
                "persona_id": persona_id,
                "source_id": source_id,
                "external_id": "ext-appl",
                "job_title": "Applied Job",
                "company_name": "ApplCorp",
                "desc_hash": "f" * 64,
                "first_seen_date": date(2026, 1, 5),
                "status": "Applied",
                "is_favorite": True,
                "fit_score": 92,
                "stretch_score": 15,
                "failed_non_negotiables": json.dumps([]),
                "score_details": json.dumps({"overall": 92}),
                "dismissed_at": None,
                "created_at": datetime(2026, 1, 5, 8, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 8, 14, 0, 0, tzinfo=UTC),
            },
        )

        # Expired job — should become Discovered + is_active=false
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": expired_id,
                "persona_id": persona_id,
                "source_id": source_id,
                "external_id": "ext-expr",
                "job_title": "Expired Job",
                "company_name": "ExprCorp",
                "desc_hash": "0" * 64,
                "first_seen_date": date(2025, 12, 1),
                "status": "Expired",
                "is_favorite": False,
                "fit_score": 70,
                "stretch_score": 50,
                "failed_non_negotiables": None,
                "score_details": json.dumps({"overall": 70}),
                "dismissed_at": None,
                "created_at": datetime(2025, 12, 1, 7, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            },
        )

        # Job with no scores (fit_score IS NULL)
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": no_score_id,
                "persona_id": persona_id,
                "source_id": source_id,
                "external_id": "ext-noscore",
                "job_title": "Unscored Job",
                "company_name": "NoScoreCorp",
                "desc_hash": "1" * 64,
                "first_seen_date": date(2026, 2, 1),
                "status": "Discovered",
                "is_favorite": False,
                "fit_score": None,
                "stretch_score": None,
                "failed_non_negotiables": None,
                "score_details": None,
                "dismissed_at": None,
                "created_at": datetime(2026, 2, 1, 6, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 2, 1, 6, 0, 0, tzinfo=UTC),
            },
        )

        await session.commit()

    return {
        "user_id": user_id,
        "persona_id": persona_id,
        "source_id": source_id,
        "discovered_id": discovered_id,
        "dismissed_id": dismissed_id,
        "applied_id": applied_id,
        "expired_id": expired_id,
        "no_score_id": no_score_id,
        "all_job_ids": [
            discovered_id,
            dismissed_id,
            applied_id,
            expired_id,
            no_score_id,
        ],
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def seeded_backfill() -> AsyncGenerator[
    tuple[AsyncSession, dict[str, uuid.UUID | list[uuid.UUID]]], None
]:
    """Seed test data at 012 level, run migration 013, yield session + IDs.

    This fixture consolidates the seed-then-upgrade pattern used by most
    tests. It migrates to 012, seeds 5 job_postings with varied statuses,
    runs migration 013 (backfill), then yields a session for assertions.
    """
    from alembic import command

    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "012_persona_jobs")
    finally:
        settings.database_name = original_name

    ids = await _seed_job_postings(engine)

    original_name = _patch_settings_for_test_db()
    try:
        await asyncio.to_thread(
            command.upgrade, alembic_cfg, "013_backfill_persona_jobs"
        )
    finally:
        settings.database_name = original_name

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session, ids
        await session.rollback()

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def empty_backfill_session() -> AsyncGenerator[AsyncSession, None]:
    """Run migration 013 on empty database (no job_postings to backfill)."""
    from alembic import command

    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(
            command.upgrade, alembic_cfg, "013_backfill_persona_jobs"
        )
    finally:
        settings.database_name = original_name

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


# =============================================================================
# A. Backfill — row count integrity (REQ-015 §11 step 4)
# =============================================================================


class TestBackfillRowCount:
    """Verify persona_jobs has one row per job_posting after backfill."""

    @pytest.mark.asyncio
    async def test_persona_jobs_row_count_matches_job_postings(self, seeded_backfill):
        """Backfill creates exactly one persona_jobs row per job_posting."""
        session, ids = seeded_backfill

        jp_count = await session.execute(text("SELECT COUNT(*) FROM job_postings"))
        pj_count = await session.execute(_COUNT_PERSONA_JOBS)
        assert jp_count.scalar() == pj_count.scalar() == len(ids["all_job_ids"])

    @pytest.mark.asyncio
    async def test_backfill_no_duplicates(self, seeded_backfill):
        """Backfill does not create duplicate (persona_id, job_posting_id) pairs."""
        session, _ = seeded_backfill

        result = await session.execute(
            text(
                "SELECT persona_id, job_posting_id, COUNT(*) "
                "FROM persona_jobs "
                "GROUP BY persona_id, job_posting_id "
                "HAVING COUNT(*) > 1"
            )
        )
        duplicates = result.fetchall()
        assert len(duplicates) == 0, f"Found duplicate persona_jobs: {duplicates}"


# =============================================================================
# B. Backfill — status mapping (REQ-015 §11 step 4)
# =============================================================================


class TestBackfillStatusMapping:
    """Verify status values are correctly mapped during backfill."""

    @pytest.mark.asyncio
    async def test_discovered_status_preserved(self, seeded_backfill):
        """Discovered status maps to Discovered in persona_jobs."""
        session, ids = seeded_backfill

        result = await session.execute(
            _SELECT_PJ_STATUS,
            {"jid": ids["discovered_id"]},
        )
        assert result.scalar() == "Discovered"

    @pytest.mark.asyncio
    async def test_dismissed_status_preserved(self, seeded_backfill):
        """Dismissed status maps to Dismissed in persona_jobs."""
        session, ids = seeded_backfill

        result = await session.execute(
            _SELECT_PJ_STATUS,
            {"jid": ids["dismissed_id"]},
        )
        assert result.scalar() == "Dismissed"

    @pytest.mark.asyncio
    async def test_applied_status_preserved(self, seeded_backfill):
        """Applied status maps to Applied in persona_jobs."""
        session, ids = seeded_backfill

        result = await session.execute(
            _SELECT_PJ_STATUS,
            {"jid": ids["applied_id"]},
        )
        assert result.scalar() == "Applied"

    @pytest.mark.asyncio
    async def test_expired_status_becomes_discovered(self, seeded_backfill):
        """Expired status maps to Discovered (expiry tracked by is_active)."""
        session, ids = seeded_backfill

        result = await session.execute(
            _SELECT_PJ_STATUS,
            {"jid": ids["expired_id"]},
        )
        assert result.scalar() == "Discovered"


# =============================================================================
# C. Backfill — field mapping (REQ-015 §11 step 4)
# =============================================================================


class TestBackfillFieldMapping:
    """Verify per-user fields are correctly copied to persona_jobs."""

    @pytest.mark.asyncio
    async def test_is_favorite_copied(self, seeded_backfill):
        """is_favorite value is copied from job_postings to persona_jobs."""
        session, ids = seeded_backfill

        # Discovered job had is_favorite=true
        result = await session.execute(
            _SELECT_PJ_IS_FAVORITE,
            {"jid": ids["discovered_id"]},
        )
        assert result.scalar() is True

        # Dismissed job had is_favorite=false
        result = await session.execute(
            _SELECT_PJ_IS_FAVORITE,
            {"jid": ids["dismissed_id"]},
        )
        assert result.scalar() is False

    @pytest.mark.asyncio
    async def test_scores_copied(self, seeded_backfill):
        """fit_score and stretch_score are copied from job_postings."""
        session, ids = seeded_backfill

        result = await session.execute(
            text(
                "SELECT fit_score, stretch_score FROM persona_jobs "
                "WHERE job_posting_id = :jid"
            ),
            {"jid": ids["discovered_id"]},
        )
        row = result.fetchone()
        assert row[0] == 85
        assert row[1] == 30

    @pytest.mark.asyncio
    async def test_null_scores_preserved(self, seeded_backfill):
        """NULL scores remain NULL in persona_jobs."""
        session, ids = seeded_backfill

        result = await session.execute(
            text(
                "SELECT fit_score, stretch_score FROM persona_jobs "
                "WHERE job_posting_id = :jid"
            ),
            {"jid": ids["no_score_id"]},
        )
        row = result.fetchone()
        assert row[0] is None
        assert row[1] is None

    @pytest.mark.asyncio
    async def test_dismissed_at_copied(self, seeded_backfill):
        """dismissed_at timestamp is copied from job_postings."""
        session, ids = seeded_backfill

        result = await session.execute(
            _SELECT_PJ_DISMISSED_AT,
            {"jid": ids["dismissed_id"]},
        )
        assert result.scalar() is not None

        # Non-dismissed job has NULL dismissed_at
        result = await session.execute(
            _SELECT_PJ_DISMISSED_AT,
            {"jid": ids["discovered_id"]},
        )
        assert result.scalar() is None

    @pytest.mark.asyncio
    async def test_jsonb_fields_copied(self, seeded_backfill):
        """failed_non_negotiables and score_details JSONB fields copied."""
        session, ids = seeded_backfill

        result = await session.execute(
            text(
                "SELECT failed_non_negotiables, score_details "
                "FROM persona_jobs WHERE job_posting_id = :jid"
            ),
            {"jid": ids["discovered_id"]},
        )
        row = result.fetchone()
        assert row[0] == ["remote_only"]
        assert row[1] == {"overall": 85}

    @pytest.mark.asyncio
    async def test_discovery_method_set_to_scouter(self, seeded_backfill):
        """All backfilled rows have discovery_method='scouter'."""
        session, _ = seeded_backfill

        result = await session.execute(
            text("SELECT DISTINCT discovery_method FROM persona_jobs")
        )
        methods = [row[0] for row in result.fetchall()]
        assert methods == ["scouter"]

    @pytest.mark.asyncio
    async def test_discovered_at_uses_first_seen_date(self, seeded_backfill):
        """discovered_at is populated from job_postings.first_seen_date."""
        session, ids = seeded_backfill

        result = await session.execute(
            text(
                "SELECT discovered_at::date FROM persona_jobs "
                "WHERE job_posting_id = :jid"
            ),
            {"jid": ids["discovered_id"]},
        )
        assert result.scalar() == date(2026, 1, 15)

    @pytest.mark.asyncio
    async def test_scored_at_set_when_fit_score_present(self, seeded_backfill):
        """scored_at is populated from updated_at when fit_score IS NOT NULL."""
        session, ids = seeded_backfill

        # Scored job should have scored_at
        result = await session.execute(
            _SELECT_PJ_SCORED_AT,
            {"jid": ids["discovered_id"]},
        )
        assert result.scalar() is not None

        # Unscored job should have NULL scored_at
        result = await session.execute(
            _SELECT_PJ_SCORED_AT,
            {"jid": ids["no_score_id"]},
        )
        assert result.scalar() is None

    @pytest.mark.asyncio
    async def test_persona_id_linked_correctly(self, seeded_backfill):
        """persona_id in persona_jobs matches the original job_postings.persona_id."""
        session, ids = seeded_backfill

        result = await session.execute(
            text("SELECT DISTINCT persona_id FROM persona_jobs")
        )
        persona_ids = [row[0] for row in result.fetchall()]
        assert len(persona_ids) == 1
        assert persona_ids[0] == ids["persona_id"]

    @pytest.mark.asyncio
    async def test_timestamps_copied(self, seeded_backfill):
        """created_at and updated_at are copied from job_postings."""
        session, ids = seeded_backfill

        result = await session.execute(
            text(
                "SELECT created_at, updated_at FROM persona_jobs "
                "WHERE job_posting_id = :jid"
            ),
            {"jid": ids["discovered_id"]},
        )
        row = result.fetchone()
        assert row[0] is not None
        assert row[1] is not None


# =============================================================================
# D. is_active backfill (REQ-015 §11 step 5)
# =============================================================================


class TestIsActiveBackfill:
    """Verify is_active is correctly set based on job_postings.status."""

    @pytest.mark.asyncio
    async def test_expired_jobs_set_inactive(self, seeded_backfill):
        """Jobs with status='Expired' get is_active=false."""
        session, ids = seeded_backfill

        result = await session.execute(_SELECT_JP_IS_ACTIVE, {"id": ids["expired_id"]})
        assert result.scalar() is False

    @pytest.mark.asyncio
    async def test_non_expired_jobs_remain_active(self, seeded_backfill):
        """Jobs with status != 'Expired' keep is_active=true."""
        session, ids = seeded_backfill

        for job_id in [
            ids["discovered_id"],
            ids["dismissed_id"],
            ids["applied_id"],
            ids["no_score_id"],
        ]:
            result = await session.execute(_SELECT_JP_IS_ACTIVE, {"id": job_id})
            assert result.scalar() is True, f"Job {job_id} should be active"


# =============================================================================
# E. Backfill with empty database (edge case)
# =============================================================================


class TestBackfillEmptyDatabase:
    """Verify migration handles empty job_postings gracefully."""

    @pytest.mark.asyncio
    async def test_backfill_on_empty_db(self, empty_backfill_session: AsyncSession):
        """Migration succeeds with no job_postings rows (no data to backfill)."""
        result = await empty_backfill_session.execute(_COUNT_PERSONA_JOBS)
        assert result.scalar() == 0


# =============================================================================
# F. Downgrade (REQ-015 §11.4)
# =============================================================================


class TestBackfillDowngrade:
    """Verify migration 013 can be cleanly downgraded."""

    @pytest.mark.asyncio
    async def test_downgrade_removes_backfilled_data(self):
        """Downgrading 013 removes backfilled persona_jobs rows and
        resets is_active to true."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            # Migrate up to 012, seed data, then upgrade to 013
            await asyncio.to_thread(command.upgrade, alembic_cfg, "012_persona_jobs")

            await _seed_job_postings(engine)

            await asyncio.to_thread(
                command.upgrade, alembic_cfg, "013_backfill_persona_jobs"
            )

            # Verify backfill happened
            session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with session_factory() as session:
                result = await session.execute(_COUNT_PERSONA_JOBS)
                assert result.scalar() == 5

            # Downgrade back to 012
            await asyncio.to_thread(command.downgrade, alembic_cfg, "012_persona_jobs")

            # Verify downgrade cleaned up
            async with session_factory() as session:
                result = await session.execute(_COUNT_PERSONA_JOBS)
                assert result.scalar() == 0

                result = await session.execute(
                    text("SELECT COUNT(*) FROM job_postings WHERE is_active = false")
                )
                assert result.scalar() == 0
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
