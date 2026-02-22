"""Tests for migration 014: drop per-user columns + FK updates.

REQ-015 §4, §11 steps 7–10: Verifies that the migration correctly:
- Adds persona_job_id FK to applications (backfilled from persona_jobs)
- Drops per-user columns from job_postings (persona_id, status, is_favorite,
  fit_score, stretch_score, failed_non_negotiables, dismissed_at, score_details)
- Drops obsolete CHECK constraints and persona FK
- Updates indexes (removes persona-scoped, adds global)
- Downgrade restores all columns, constraints, and indexes
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
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

_REVISION = "014_drop_per_user_columns"
_DOWN_REVISION = "013_backfill_persona_jobs"

# ---------------------------------------------------------------------------
# SQL fragments — pre-014 schema (persona_id still on job_postings)
# ---------------------------------------------------------------------------
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
    "INSERT INTO job_sources "
    "(id, source_name, source_type, description, created_at, updated_at) "
    "VALUES (:id, :name, 'API', 'Test source', now(), now())"
)
_INSERT_JOB_POSTING_PRE014 = text(
    "INSERT INTO job_postings "
    "(id, persona_id, source_id, job_title, company_name, description, "
    "description_hash, first_seen_date, created_at, updated_at) "
    "VALUES (:id, :persona_id, :source_id, :job_title, :company_name, "
    "'Job description', :desc_hash, CURRENT_DATE, now(), now())"
)
_INSERT_JOB_POSTING_POST014 = text(
    "INSERT INTO job_postings "
    "(id, source_id, job_title, company_name, description, "
    "description_hash, first_seen_date, created_at, updated_at) "
    "VALUES (:id, :source_id, :job_title, :company_name, "
    "'Job description', :desc_hash, CURRENT_DATE, now(), now())"
)
_INSERT_PERSONA_JOB = text(
    "INSERT INTO persona_jobs "
    "(id, persona_id, job_posting_id, status, is_favorite, discovery_method, "
    "discovered_at, created_at, updated_at) "
    "VALUES (:id, :persona_id, :job_posting_id, 'Discovered', false, 'scouter', "
    "now(), now(), now())"
)
_INSERT_BASE_RESUME = text(
    "INSERT INTO base_resumes "
    "(id, persona_id, name, role_type, summary, "
    "created_at, updated_at) "
    "VALUES (:id, :persona_id, 'Test Resume', 'Engineer', 'Summary text', "
    "now(), now())"
)
_INSERT_JOB_VARIANT = text(
    "INSERT INTO job_variants "
    "(id, base_resume_id, job_posting_id, summary, "
    "created_at, updated_at) "
    "VALUES (:id, :base_resume_id, :job_posting_id, 'Variant summary', "
    "now(), now())"
)
_INSERT_APPLICATION = text(
    "INSERT INTO applications "
    "(id, persona_id, job_posting_id, job_variant_id, job_snapshot, "
    "created_at, updated_at, applied_at, status_updated_at) "
    "VALUES (:id, :persona_id, :job_posting_id, :job_variant_id, "
    "'{}'::jsonb, now(), now(), now(), now())"
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


async def _column_exists(session: AsyncSession, table: str, column: str) -> bool:
    """Check if a column exists on a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column)"
        ),
        {"table": table, "column": column},
    )
    return result.scalar()  # type: ignore[return-value]


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


async def _constraint_exists(
    session: AsyncSession, table: str, constraint_name: str
) -> bool:
    """Check if a named constraint exists on a table."""
    result = await session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_name = :table AND constraint_name = :constraint)"
        ),
        {"table": table, "constraint": constraint_name},
    )
    return result.scalar()  # type: ignore[return-value]


async def _create_test_data_post014(
    session: AsyncSession,
) -> dict[str, uuid.UUID]:
    """Insert prerequisite test data at 014 schema level (no persona_id)."""
    user_id = uuid.uuid4()
    persona_id = uuid.uuid4()
    source_id = uuid.uuid4()
    job_id = uuid.uuid4()
    pj_id = uuid.uuid4()

    await session.execute(_INSERT_USER, {"id": user_id, "email": "test@example.com"})
    await session.execute(
        _INSERT_PERSONA,
        {"id": persona_id, "user_id": user_id, "email": "persona@example.com"},
    )
    await session.execute(_INSERT_JOB_SOURCE, {"id": source_id, "name": "TestSource"})
    await session.execute(
        _INSERT_JOB_POSTING_POST014,
        {
            "id": job_id,
            "source_id": source_id,
            "job_title": "Software Engineer",
            "company_name": "Acme Corp",
            "desc_hash": "a" * 64,
        },
    )
    await session.execute(
        _INSERT_PERSONA_JOB,
        {
            "id": pj_id,
            "persona_id": persona_id,
            "job_posting_id": job_id,
        },
    )
    await session.flush()

    return {
        "user_id": user_id,
        "persona_id": persona_id,
        "source_id": source_id,
        "job_id": job_id,
        "persona_job_id": pj_id,
    }


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def migration_engine():
    """Create engine and run alembic migrations up to 014."""
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
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
    """Create session on migrated database (at 014 level)."""
    session_factory = async_sessionmaker(
        migration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seeded_engine():
    """Upgrade to 013, seed test data, then upgrade to 014.

    Creates: 1 user, 1 persona, 1 source, 1 job_posting (with persona_id),
    1 persona_jobs link, 1 base_resume, 1 job_variant, 1 application.
    Then upgrades to 014 which backfills applications.persona_job_id.
    """
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    ids = {
        "user_id": uuid.uuid4(),
        "persona_id": uuid.uuid4(),
        "source_id": uuid.uuid4(),
        "job_id": uuid.uuid4(),
        "persona_job_id": uuid.uuid4(),
        "application_id": uuid.uuid4(),
        "base_resume_id": uuid.uuid4(),
        "job_variant_id": uuid.uuid4(),
    }

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, _DOWN_REVISION)

        async with engine.begin() as conn:
            await conn.execute(
                _INSERT_USER,
                {"id": ids["user_id"], "email": "seed@example.com"},
            )
            await conn.execute(
                _INSERT_PERSONA,
                {
                    "id": ids["persona_id"],
                    "user_id": ids["user_id"],
                    "email": "sp@example.com",
                },
            )
            await conn.execute(
                _INSERT_JOB_SOURCE,
                {"id": ids["source_id"], "name": "SeedSource"},
            )
            await conn.execute(
                _INSERT_JOB_POSTING_PRE014,
                {
                    "id": ids["job_id"],
                    "persona_id": ids["persona_id"],
                    "source_id": ids["source_id"],
                    "job_title": "Backend Dev",
                    "company_name": "SeedCo",
                    "desc_hash": "b" * 64,
                },
            )
            await conn.execute(
                _INSERT_PERSONA_JOB,
                {
                    "id": ids["persona_job_id"],
                    "persona_id": ids["persona_id"],
                    "job_posting_id": ids["job_id"],
                },
            )
            await conn.execute(
                _INSERT_BASE_RESUME,
                {
                    "id": ids["base_resume_id"],
                    "persona_id": ids["persona_id"],
                },
            )
            await conn.execute(
                _INSERT_JOB_VARIANT,
                {
                    "id": ids["job_variant_id"],
                    "base_resume_id": ids["base_resume_id"],
                    "job_posting_id": ids["job_id"],
                },
            )
            await conn.execute(
                _INSERT_APPLICATION,
                {
                    "id": ids["application_id"],
                    "persona_id": ids["persona_id"],
                    "job_posting_id": ids["job_id"],
                    "job_variant_id": ids["job_variant_id"],
                },
            )

        await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)
    finally:
        settings.database_name = original_name

    yield engine, ids

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_session(
    seeded_engine,
) -> AsyncGenerator[tuple[AsyncSession, dict[str, uuid.UUID]], None]:
    """Session on seeded + migrated database, with test IDs."""
    engine, ids = seeded_engine
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session, ids
        await session.rollback()


# =============================================================================
# A. applications.persona_job_id (REQ-015 §4.4, §11 step 7)
# =============================================================================


class TestApplicationPersonaJobId:
    """Verify persona_job_id FK added to applications."""

    @pytest.mark.asyncio
    async def test_column_exists(self, migration_session: AsyncSession):
        """applications.persona_job_id column exists after migration."""
        assert await _column_exists(migration_session, "applications", "persona_job_id")

    @pytest.mark.asyncio
    async def test_column_is_nullable(self, migration_session: AsyncSession):
        """persona_job_id is nullable (ON DELETE SET NULL target)."""
        result = await migration_session.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'applications' "
                "AND column_name = 'persona_job_id'"
            )
        )
        assert result.scalar() == "YES"

    @pytest.mark.asyncio
    async def test_fk_constraint_exists(self, migration_session: AsyncSession):
        """FK constraint on persona_job_id references persona_jobs."""
        assert await _constraint_exists(
            migration_session, "applications", "fk_applications_persona_job_id"
        )

    @pytest.mark.asyncio
    async def test_backfill_correct(
        self,
        seeded_session: tuple[AsyncSession, dict[str, uuid.UUID]],
    ):
        """persona_job_id is backfilled from matching persona_jobs row."""
        session, ids = seeded_session
        result = await session.execute(
            text("SELECT persona_job_id FROM applications WHERE id = :id"),
            {"id": ids["application_id"]},
        )
        assert result.scalar() == ids["persona_job_id"]

    @pytest.mark.asyncio
    async def test_fk_set_null_on_persona_job_delete(
        self,
        seeded_session: tuple[AsyncSession, dict[str, uuid.UUID]],
    ):
        """Deleting persona_job sets application.persona_job_id to NULL."""
        session, ids = seeded_session

        await session.execute(
            text("DELETE FROM persona_jobs WHERE id = :id"),
            {"id": ids["persona_job_id"]},
        )
        await session.flush()

        result = await session.execute(
            text("SELECT persona_job_id FROM applications WHERE id = :id"),
            {"id": ids["application_id"]},
        )
        assert result.scalar() is None

    @pytest.mark.asyncio
    async def test_unique_constraint_preserved(self, migration_session: AsyncSession):
        """Original UNIQUE(persona_id, job_posting_id) still enforced."""
        assert await _constraint_exists(
            migration_session, "applications", "uq_application_persona_job"
        )


# =============================================================================
# B. job_postings — dropped per-user columns (REQ-015 §11 steps 8–9)
# =============================================================================


class TestJobPostingsColumnsDropped:
    """Verify per-user columns removed from job_postings."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column",
        [
            "persona_id",
            "status",
            "is_favorite",
            "fit_score",
            "stretch_score",
            "failed_non_negotiables",
            "dismissed_at",
            "score_details",
        ],
    )
    async def test_per_user_column_removed(
        self, migration_session: AsyncSession, column: str
    ):
        """Per-user column no longer exists on job_postings."""
        assert not await _column_exists(migration_session, "job_postings", column)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "column",
        [
            "id",
            "source_id",
            "job_title",
            "company_name",
            "description",
            "description_hash",
            "is_active",
            "first_seen_date",
            "ghost_score",
            "also_found_on",
            "expired_at",
        ],
    )
    async def test_retained_column_exists(
        self, migration_session: AsyncSession, column: str
    ):
        """Retained shared columns still exist on job_postings."""
        assert await _column_exists(migration_session, "job_postings", column)

    @pytest.mark.asyncio
    async def test_insert_without_persona_id(self, migration_session: AsyncSession):
        """Job postings can be inserted without persona_id."""
        ids = await _create_test_data_post014(migration_session)
        result = await migration_session.execute(
            text("SELECT id FROM job_postings WHERE id = :id"),
            {"id": ids["job_id"]},
        )
        assert result.scalar() is not None


# =============================================================================
# C. job_postings — constraint changes
# =============================================================================


class TestConstraintChanges:
    """Verify constraint updates on job_postings."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "constraint_name",
        [
            "ck_jobposting_status",
            "ck_jobposting_fit_score",
            "ck_jobposting_stretch_score",
        ],
    )
    async def test_per_user_check_constraint_removed(
        self, migration_session: AsyncSession, constraint_name: str
    ):
        """CHECK constraints for dropped columns are removed."""
        assert not await _constraint_exists(
            migration_session, "job_postings", constraint_name
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "constraint_name",
        [
            "ck_jobposting_work_model",
            "ck_jobposting_seniority",
            "ck_jobposting_ghost_score",
        ],
    )
    async def test_retained_check_constraint_exists(
        self, migration_session: AsyncSession, constraint_name: str
    ):
        """CHECK constraints for retained columns still exist."""
        assert await _constraint_exists(
            migration_session, "job_postings", constraint_name
        )

    @pytest.mark.asyncio
    async def test_persona_fk_removed(self, migration_session: AsyncSession):
        """persona_id FK constraint removed from job_postings."""
        assert not await _constraint_exists(
            migration_session, "job_postings", "job_postings_persona_id_fkey"
        )


# =============================================================================
# D. Index changes (REQ-015 §4.1, §11 step 10)
# =============================================================================


class TestIndexChanges:
    """Verify index updates on job_postings."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_job_postings_persona_id",
            "idx_job_postings_persona_id_status",
            "idx_job_postings_persona_id_fit_score",
        ],
    )
    async def test_persona_index_dropped(
        self, migration_session: AsyncSession, index_name: str
    ):
        """Persona-scoped indexes are removed."""
        assert not await _index_exists(migration_session, "job_postings", index_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_job_postings_is_active",
            "idx_job_postings_company_name_job_title",
            "idx_job_postings_first_seen_date",
        ],
    )
    async def test_new_global_index_created(
        self, migration_session: AsyncSession, index_name: str
    ):
        """New global indexes are created."""
        assert await _index_exists(migration_session, "job_postings", index_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "index_name",
        [
            "idx_job_postings_description_hash",
            "idx_job_postings_company_name",
            "idx_job_postings_source_id",
        ],
    )
    async def test_existing_global_index_preserved(
        self, migration_session: AsyncSession, index_name: str
    ):
        """Pre-existing global indexes remain intact."""
        assert await _index_exists(migration_session, "job_postings", index_name)


# =============================================================================
# E. Downgrade (REQ-015 §11.4)
# =============================================================================


class TestMigrationDowngrade:
    """Verify migration 014 downgrade back to 013."""

    @pytest.mark.asyncio
    async def test_downgrade_restores_schema(self):
        """Downgrading 014 restores columns, constraints, indexes."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)

            # Verify columns are gone
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'job_postings' "
                        "AND column_name = 'persona_id')"
                    )
                )
                assert result.scalar() is False

            # Downgrade
            await asyncio.to_thread(command.downgrade, alembic_cfg, _DOWN_REVISION)

            async with engine.begin() as conn:
                # Columns restored
                for col in [
                    "persona_id",
                    "status",
                    "is_favorite",
                    "fit_score",
                    "stretch_score",
                    "failed_non_negotiables",
                    "dismissed_at",
                    "score_details",
                ]:
                    result = await conn.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 "
                            "FROM information_schema.columns "
                            "WHERE table_name = 'job_postings' "
                            "AND column_name = :col)"
                        ),
                        {"col": col},
                    )
                    assert result.scalar() is True, f"Column {col} not restored"

                # persona_job_id removed from applications
                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 "
                        "FROM information_schema.columns "
                        "WHERE table_name = 'applications' "
                        "AND column_name = 'persona_job_id')"
                    )
                )
                assert result.scalar() is False

                # Old indexes restored
                for idx in [
                    "idx_job_postings_persona_id",
                    "idx_job_postings_persona_id_status",
                    "idx_job_postings_persona_id_fit_score",
                ]:
                    result = await conn.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                            "WHERE indexname = :idx)"
                        ),
                        {"idx": idx},
                    )
                    assert result.scalar() is True, f"Index {idx} not restored"

                # New indexes removed
                for idx in [
                    "idx_job_postings_is_active",
                    "idx_job_postings_company_name_job_title",
                    "idx_job_postings_first_seen_date",
                ]:
                    result = await conn.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                            "WHERE indexname = :idx)"
                        ),
                        {"idx": idx},
                    )
                    assert result.scalar() is False, (
                        f"Index {idx} not removed on downgrade"
                    )
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_downgrade_backfills_persona_id(self):
        """Downgrading 014 backfills persona_id from persona_jobs."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        ids = {
            "user_id": uuid.uuid4(),
            "persona_id": uuid.uuid4(),
            "source_id": uuid.uuid4(),
            "job_id": uuid.uuid4(),
            "pj_id": uuid.uuid4(),
        }

        try:
            # Upgrade to 013, seed data, upgrade to 014
            await asyncio.to_thread(command.upgrade, alembic_cfg, _DOWN_REVISION)

            async with engine.begin() as conn:
                await conn.execute(
                    _INSERT_USER,
                    {"id": ids["user_id"], "email": "dg@example.com"},
                )
                await conn.execute(
                    _INSERT_PERSONA,
                    {
                        "id": ids["persona_id"],
                        "user_id": ids["user_id"],
                        "email": "dgp@example.com",
                    },
                )
                await conn.execute(
                    _INSERT_JOB_SOURCE,
                    {"id": ids["source_id"], "name": "DGSource"},
                )
                await conn.execute(
                    _INSERT_JOB_POSTING_PRE014,
                    {
                        "id": ids["job_id"],
                        "persona_id": ids["persona_id"],
                        "source_id": ids["source_id"],
                        "job_title": "DG Eng",
                        "company_name": "DGCo",
                        "desc_hash": "d" * 64,
                    },
                )
                await conn.execute(
                    _INSERT_PERSONA_JOB,
                    {
                        "id": ids["pj_id"],
                        "persona_id": ids["persona_id"],
                        "job_posting_id": ids["job_id"],
                    },
                )

            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)

            # Verify persona_id column is gone
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 "
                        "FROM information_schema.columns "
                        "WHERE table_name = 'job_postings' "
                        "AND column_name = 'persona_id')"
                    )
                )
                assert result.scalar() is False

            # Downgrade to 013
            await asyncio.to_thread(command.downgrade, alembic_cfg, _DOWN_REVISION)

            # Verify persona_id backfilled from persona_jobs
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT persona_id FROM job_postings WHERE id = :id"),
                    {"id": ids["job_id"]},
                )
                assert result.scalar() == ids["persona_id"]
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_downgrade_deletes_orphaned_postings(self):
        """Downgrade deletes job_postings with no persona_jobs link."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        source_id = uuid.uuid4()
        orphan_job_id = uuid.uuid4()

        try:
            await asyncio.to_thread(command.upgrade, alembic_cfg, _REVISION)

            # Insert a job_posting at 014 level with no persona_jobs link
            async with engine.begin() as conn:
                await conn.execute(
                    _INSERT_USER,
                    {"id": uuid.uuid4(), "email": "orph@example.com"},
                )
                await conn.execute(
                    _INSERT_JOB_SOURCE,
                    {"id": source_id, "name": "OrphanSource"},
                )
                await conn.execute(
                    _INSERT_JOB_POSTING_POST014,
                    {
                        "id": orphan_job_id,
                        "source_id": source_id,
                        "job_title": "Orphan Job",
                        "company_name": "OrphanCo",
                        "desc_hash": "e" * 64,
                    },
                )

            # Downgrade to 013
            await asyncio.to_thread(command.downgrade, alembic_cfg, _DOWN_REVISION)

            # Verify the orphaned posting was deleted
            async with engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM job_postings WHERE id = :id)"),
                    {"id": orphan_job_id},
                )
                assert result.scalar() is False
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
