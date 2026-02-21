"""Tests for migration 012: persona_jobs table and job_postings changes.

REQ-015 §4, §11 steps 1–3: Verifies that the migration correctly creates
the persona_jobs table with all per-user columns, adds is_active to
job_postings, and adds the partial UNIQUE constraint on (source_id,
external_id) WHERE both NOT NULL.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
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
    "description_hash, first_seen_date, created_at, updated_at) "
    "VALUES (:id, :persona_id, :source_id, :external_id, :job_title, :company_name, "
    "'Job description', :desc_hash, CURRENT_DATE, now(), now())"
)
_INSERT_PERSONA_JOB = text(
    "INSERT INTO persona_jobs "
    "(id, persona_id, job_posting_id, status, is_favorite, discovery_method, "
    "discovered_at, created_at, updated_at) "
    "VALUES (:id, :persona_id, :job_posting_id, :status, :is_favorite, :discovery_method, "
    "now(), now(), now())"
)
_INSERT_PERSONA_JOB_MINIMAL = text(
    "INSERT INTO persona_jobs (id, persona_id, job_posting_id) VALUES (:id, :pid, :jid)"
)


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


async def _create_test_data(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Insert prerequisite test data and return IDs."""
    user_id = uuid.uuid4()
    persona_id = uuid.uuid4()
    source_id = uuid.uuid4()
    job_id = uuid.uuid4()

    await session.execute(_INSERT_USER, {"id": user_id, "email": "test@example.com"})
    await session.execute(
        _INSERT_PERSONA,
        {"id": persona_id, "user_id": user_id, "email": "persona@example.com"},
    )
    await session.execute(_INSERT_JOB_SOURCE, {"id": source_id, "name": "TestSource"})
    await session.execute(
        _INSERT_JOB_POSTING,
        {
            "id": job_id,
            "persona_id": persona_id,
            "source_id": source_id,
            "external_id": "ext-001",
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "desc_hash": "a" * 64,
        },
    )
    await session.flush()

    return {
        "user_id": user_id,
        "persona_id": persona_id,
        "source_id": source_id,
        "job_id": job_id,
    }


async def _index_exists(session: AsyncSession, table: str, index_name: str) -> bool:
    """Check if a named index exists on a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
            "WHERE tablename = :table AND indexname = :index)"
        ),
        {"table": table, "index": index_name},
    )
    return result.scalar()  # type: ignore[return-value]


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 012."""
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "012_persona_jobs")
    finally:
        settings.database_name = original_name

    yield engine

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def migration_session(
    migration_engine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create session on migrated database."""
    session_factory = async_sessionmaker(
        migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# A. persona_jobs table — existence and columns (REQ-015 §4.2)
# =============================================================================


class TestPersonaJobsTableCreation:
    """Verify persona_jobs table is created with all columns."""

    @pytest.mark.asyncio
    async def test_table_exists(self, migration_session: AsyncSession):
        """persona_jobs table is created by migration."""
        result = await migration_session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'persona_jobs')"
            )
        )
        assert result.scalar() is True

    @pytest.mark.asyncio
    async def test_all_columns_present(self, migration_session: AsyncSession):
        """persona_jobs table has all required columns."""
        result = await migration_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'persona_jobs' ORDER BY ordinal_position"
            )
        )
        columns = {row[0] for row in result.fetchall()}
        expected = {
            "id",
            "persona_id",
            "job_posting_id",
            "status",
            "is_favorite",
            "dismissed_at",
            "fit_score",
            "stretch_score",
            "failed_non_negotiables",
            "score_details",
            "discovery_method",
            "discovered_at",
            "scored_at",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("column", "expected"),
        [
            ("status", "Discovered"),
            ("is_favorite", False),
            ("discovery_method", "pool"),
        ],
    )
    async def test_column_defaults(
        self, migration_session: AsyncSession, column: str, expected: object
    ):
        """Server defaults are applied for columns with defaults."""
        ids = await _create_test_data(migration_session)
        pj_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_PERSONA_JOB_MINIMAL,
            {"id": pj_id, "pid": ids["persona_id"], "jid": ids["job_id"]},
        )
        await migration_session.flush()

        # Column name comes from test constants, not user input
        result = await migration_session.execute(
            text(f"SELECT {column} FROM persona_jobs WHERE id = :id"),  # noqa: S608
            {"id": pj_id},
        )
        assert result.scalar() == expected


# =============================================================================
# B. persona_jobs — constraints (REQ-015 §4.2)
# =============================================================================


class TestPersonaJobsConstraints:
    """Verify FK, UNIQUE, and CHECK constraints on persona_jobs."""

    @pytest.mark.asyncio
    async def test_unique_persona_job_posting(self, migration_session: AsyncSession):
        """Duplicate (persona_id, job_posting_id) raises IntegrityError."""
        ids = await _create_test_data(migration_session)
        await migration_session.execute(
            _INSERT_PERSONA_JOB,
            {
                "id": uuid.uuid4(),
                "persona_id": ids["persona_id"],
                "job_posting_id": ids["job_id"],
                "status": "Discovered",
                "is_favorite": False,
                "discovery_method": "scouter",
            },
        )
        await migration_session.flush()

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                _INSERT_PERSONA_JOB,
                {
                    "id": uuid.uuid4(),
                    "persona_id": ids["persona_id"],
                    "job_posting_id": ids["job_id"],
                    "status": "Discovered",
                    "is_favorite": False,
                    "discovery_method": "pool",
                },
            )

    @pytest.mark.asyncio
    async def test_status_check_constraint(self, migration_session: AsyncSession):
        """Invalid status value raises IntegrityError."""
        ids = await _create_test_data(migration_session)

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                _INSERT_PERSONA_JOB,
                {
                    "id": uuid.uuid4(),
                    "persona_id": ids["persona_id"],
                    "job_posting_id": ids["job_id"],
                    "status": "InvalidStatus",
                    "is_favorite": False,
                    "discovery_method": "scouter",
                },
            )

    @pytest.mark.asyncio
    async def test_discovery_method_check_constraint(
        self, migration_session: AsyncSession
    ):
        """Invalid discovery_method raises IntegrityError."""
        ids = await _create_test_data(migration_session)

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                _INSERT_PERSONA_JOB,
                {
                    "id": uuid.uuid4(),
                    "persona_id": ids["persona_id"],
                    "job_posting_id": ids["job_id"],
                    "status": "Discovered",
                    "is_favorite": False,
                    "discovery_method": "invalid_method",
                },
            )

    @pytest.mark.asyncio
    async def test_fit_score_range_constraint(self, migration_session: AsyncSession):
        """fit_score outside 0-100 raises IntegrityError."""
        ids = await _create_test_data(migration_session)

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                text(
                    "INSERT INTO persona_jobs "
                    "(id, persona_id, job_posting_id, fit_score) "
                    "VALUES (:id, :pid, :jid, 101)"
                ),
                {"id": uuid.uuid4(), "pid": ids["persona_id"], "jid": ids["job_id"]},
            )

    @pytest.mark.asyncio
    async def test_stretch_score_range_constraint(
        self, migration_session: AsyncSession
    ):
        """stretch_score outside 0-100 raises IntegrityError."""
        ids = await _create_test_data(migration_session)

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                text(
                    "INSERT INTO persona_jobs "
                    "(id, persona_id, job_posting_id, stretch_score) "
                    "VALUES (:id, :pid, :jid, -1)"
                ),
                {"id": uuid.uuid4(), "pid": ids["persona_id"], "jid": ids["job_id"]},
            )

    @pytest.mark.asyncio
    async def test_persona_fk_cascade(self, migration_session: AsyncSession):
        """Deleting a persona cascades to delete persona_jobs links."""
        ids = await _create_test_data(migration_session)
        pj_id = uuid.uuid4()
        await migration_session.execute(
            _INSERT_PERSONA_JOB,
            {
                "id": pj_id,
                "persona_id": ids["persona_id"],
                "job_posting_id": ids["job_id"],
                "status": "Discovered",
                "is_favorite": False,
                "discovery_method": "scouter",
            },
        )
        await migration_session.flush()

        await migration_session.execute(
            text("DELETE FROM personas WHERE id = :id"), {"id": ids["persona_id"]}
        )
        await migration_session.flush()

        result = await migration_session.execute(
            text("SELECT id FROM persona_jobs WHERE id = :id"), {"id": pj_id}
        )
        assert result.fetchone() is None

    @pytest.mark.asyncio
    async def test_job_posting_fk_restrict(self, migration_session: AsyncSession):
        """Deleting a job_posting with persona_jobs link raises IntegrityError."""
        ids = await _create_test_data(migration_session)
        await migration_session.execute(
            _INSERT_PERSONA_JOB,
            {
                "id": uuid.uuid4(),
                "persona_id": ids["persona_id"],
                "job_posting_id": ids["job_id"],
                "status": "Discovered",
                "is_favorite": False,
                "discovery_method": "scouter",
            },
        )
        await migration_session.flush()

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                text("DELETE FROM job_postings WHERE id = :id"), {"id": ids["job_id"]}
            )

    @pytest.mark.asyncio
    async def test_valid_status_values_accepted(self, migration_session: AsyncSession):
        """All valid status values are accepted by CHECK constraint."""
        ids = await _create_test_data(migration_session)

        for status in ("Discovered", "Dismissed", "Applied"):
            job_id = uuid.uuid4()
            await migration_session.execute(
                _INSERT_JOB_POSTING,
                {
                    "id": job_id,
                    "persona_id": ids["persona_id"],
                    "source_id": ids["source_id"],
                    "external_id": f"ext-{status}",
                    "job_title": f"Job {status}",
                    "company_name": "Acme",
                    "desc_hash": uuid.uuid4().hex + uuid.uuid4().hex,
                },
            )
            await migration_session.execute(
                _INSERT_PERSONA_JOB,
                {
                    "id": uuid.uuid4(),
                    "persona_id": ids["persona_id"],
                    "job_posting_id": job_id,
                    "status": status,
                    "is_favorite": False,
                    "discovery_method": "scouter",
                },
            )
        await migration_session.flush()


# =============================================================================
# C. persona_jobs — indexes (REQ-015 §4.2)
# =============================================================================


class TestPersonaJobsIndexes:
    """Verify indexes created on persona_jobs table."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_persona_jobs_persona_id",
            "idx_persona_jobs_job_posting_id",
            "idx_persona_jobs_persona_id_status",
            "idx_persona_jobs_persona_id_fit_score",
        ],
    )
    async def test_index_exists(self, migration_session: AsyncSession, index_name: str):
        """Required indexes exist on persona_jobs table."""
        assert await _index_exists(migration_session, "persona_jobs", index_name)


# =============================================================================
# D. job_postings — is_active column (REQ-015 §4.1)
# =============================================================================


class TestJobPostingsIsActive:
    """Verify is_active column added to job_postings."""

    @pytest.mark.asyncio
    async def test_is_active_column_exists(self, migration_session: AsyncSession):
        """job_postings has is_active BOOLEAN column."""
        result = await migration_session.execute(
            text(
                "SELECT data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_name = 'job_postings' AND column_name = 'is_active'"
            )
        )
        row = result.fetchone()
        assert row is not None, "job_postings.is_active column does not exist"
        assert row[0] == "boolean"
        assert row[1] == "NO"
        assert "true" in str(row[2]).lower()

    @pytest.mark.asyncio
    async def test_is_active_defaults_to_true(self, migration_session: AsyncSession):
        """New job_postings rows default to is_active = true."""
        ids = await _create_test_data(migration_session)

        result = await migration_session.execute(
            text("SELECT is_active FROM job_postings WHERE id = :id"),
            {"id": ids["job_id"]},
        )
        assert result.scalar() is True


# =============================================================================
# E. job_postings — partial UNIQUE on (source_id, external_id) (REQ-015 §10.3)
# =============================================================================


class TestJobPostingsSourceUniqueConstraint:
    """Verify partial UNIQUE on (source_id, external_id) WHERE both NOT NULL."""

    @pytest.mark.asyncio
    async def test_partial_unique_index_exists(self, migration_session: AsyncSession):
        """Partial unique index on (source_id, external_id) exists."""
        assert await _index_exists(
            migration_session, "job_postings", "uq_job_postings_source_id_external_id"
        )

    @pytest.mark.asyncio
    async def test_duplicate_source_external_rejected(
        self, migration_session: AsyncSession
    ):
        """Duplicate (source_id, external_id) raises IntegrityError."""
        ids = await _create_test_data(migration_session)

        with pytest.raises(IntegrityError):
            await migration_session.execute(
                _INSERT_JOB_POSTING,
                {
                    "id": uuid.uuid4(),
                    "persona_id": ids["persona_id"],
                    "source_id": ids["source_id"],
                    "external_id": "ext-001",
                    "job_title": "Different Title",
                    "company_name": "Different Co",
                    "desc_hash": "b" * 64,
                },
            )

    @pytest.mark.asyncio
    async def test_null_external_id_allows_duplicates(
        self, migration_session: AsyncSession
    ):
        """Multiple rows with NULL external_id are allowed (partial UNIQUE)."""
        ids = await _create_test_data(migration_session)

        for i in range(2):
            await migration_session.execute(
                _INSERT_JOB_POSTING,
                {
                    "id": uuid.uuid4(),
                    "persona_id": ids["persona_id"],
                    "source_id": ids["source_id"],
                    "external_id": None,
                    "job_title": f"Job {i}",
                    "company_name": "NullCo",
                    "desc_hash": uuid.uuid4().hex + uuid.uuid4().hex,
                },
            )
        await migration_session.flush()


# =============================================================================
# F. Downgrade (REQ-015 §11.4)
# =============================================================================


class TestMigrationDowngrade:
    """Verify migration 012 can be cleanly downgraded."""

    @pytest.mark.asyncio
    async def test_downgrade_removes_persona_jobs_and_is_active(self):
        """Downgrading 012 removes persona_jobs table, is_active column,
        and partial unique index."""
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

            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = 'persona_jobs')"
                    )
                )
                assert result.scalar() is True

                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'job_postings' AND column_name = 'is_active')"
                    )
                )
                assert result.scalar() is True

            await asyncio.to_thread(
                command.downgrade, alembic_cfg, "011_rename_indexes"
            )

            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = 'persona_jobs')"
                    )
                )
                assert result.scalar() is False

                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'job_postings' "
                        "AND column_name = 'is_active')"
                    )
                )
                assert result.scalar() is False

                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                        "WHERE indexname = 'uq_job_postings_source_id_external_id')"
                    )
                )
                assert result.scalar() is False
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
