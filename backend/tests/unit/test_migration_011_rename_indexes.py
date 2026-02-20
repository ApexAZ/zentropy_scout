"""Tests for migration 011: rename all indexes to explicit convention.

REQ-014 §8.1: Verifies that the index rename migration correctly renames
all 49 indexes from abbreviated convention (idx_persona_user) to explicit
idx_{table}_{column} convention (idx_personas_user_id) for AI-searchability.

Tests upgrade (old → new names) and downgrade (new → old names).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

if TYPE_CHECKING:
    from alembic.config import Config
    from sqlalchemy.ext.asyncio import AsyncConnection

TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)

# Complete mapping: (old_name, new_name, table)
# Sorted by migration origin for traceability.
INDEX_RENAMES: list[tuple[str, str, str]] = [
    # Migration 001: users, job_sources
    ("idx_user_email", "idx_users_email", "users"),
    ("idx_jobsource_name", "idx_job_sources_source_name", "job_sources"),
    # Migration 002: personas
    ("idx_persona_user", "idx_personas_user_id", "personas"),
    ("idx_persona_email", "idx_personas_email", "personas"),
    # Migration 003: work_histories
    ("idx_workhistory_persona", "idx_work_histories_persona_id", "work_histories"),
    (
        "idx_workhistory_order",
        "idx_work_histories_persona_id_display_order",
        "work_histories",
    ),
    # Migration 003: skills
    ("idx_skill_persona", "idx_skills_persona_id", "skills"),
    ("idx_skill_name", "idx_skills_persona_id_skill_name", "skills"),
    # Migration 003: educations
    ("idx_education_persona", "idx_educations_persona_id", "educations"),
    # Migration 003: certifications
    ("idx_certification_persona", "idx_certifications_persona_id", "certifications"),
    # Migration 003: achievement_stories
    (
        "idx_achievementstory_persona",
        "idx_achievement_stories_persona_id",
        "achievement_stories",
    ),
    # Migration 003: voice_profiles
    ("idx_voiceprofile_persona", "idx_voice_profiles_persona_id", "voice_profiles"),
    # Migration 003: custom_non_negotiables
    (
        "idx_customnonneg_persona",
        "idx_custom_non_negotiables_persona_id",
        "custom_non_negotiables",
    ),
    # Migration 003: persona_embeddings
    (
        "idx_personaembedding_persona",
        "idx_persona_embeddings_persona_id",
        "persona_embeddings",
    ),
    (
        "idx_personaembedding_type",
        "idx_persona_embeddings_persona_id_embedding_type",
        "persona_embeddings",
    ),
    (
        "idx_personaembedding_vector",
        "idx_persona_embeddings_vector",
        "persona_embeddings",
    ),
    # Migration 003: resume_files
    ("idx_resumefile_persona", "idx_resume_files_persona_id", "resume_files"),
    ("idx_resumefile_active", "idx_resume_files_persona_id_is_active", "resume_files"),
    # Migration 003: base_resumes
    ("idx_baseresume_persona", "idx_base_resumes_persona_id", "base_resumes"),
    (
        "idx_baseresume_primary",
        "idx_base_resumes_persona_id_is_primary",
        "base_resumes",
    ),
    # Migration 003: persona_change_flags
    (
        "idx_personachangeflag_persona",
        "idx_persona_change_flags_persona_id",
        "persona_change_flags",
    ),
    (
        "idx_personachangeflag_status",
        "idx_persona_change_flags_persona_id_status",
        "persona_change_flags",
    ),
    # Migration 003: user_source_preferences
    (
        "idx_usersourcepref_persona",
        "idx_user_source_preferences_persona_id",
        "user_source_preferences",
    ),
    # Migration 003: polling_configurations
    (
        "idx_pollingconfig_persona",
        "idx_polling_configurations_persona_id",
        "polling_configurations",
    ),
    (
        "idx_pollingconfig_nextpoll",
        "idx_polling_configurations_next_poll_at",
        "polling_configurations",
    ),
    # Migration 003: job_postings
    ("idx_jobposting_persona", "idx_job_postings_persona_id", "job_postings"),
    ("idx_jobposting_status", "idx_job_postings_persona_id_status", "job_postings"),
    ("idx_jobposting_source", "idx_job_postings_source_id", "job_postings"),
    (
        "idx_jobposting_external",
        "idx_job_postings_source_id_external_id",
        "job_postings",
    ),
    ("idx_jobposting_hash", "idx_job_postings_description_hash", "job_postings"),
    ("idx_jobposting_company", "idx_job_postings_company_name", "job_postings"),
    (
        "idx_jobposting_fitscore",
        "idx_job_postings_persona_id_fit_score",
        "job_postings",
    ),
    # Migration 004: bullets
    ("idx_bullet_workhistory", "idx_bullets_work_history_id", "bullets"),
    ("idx_bullet_order", "idx_bullets_work_history_id_display_order", "bullets"),
    # Migration 004: job_variants
    ("idx_jobvariant_baseresume", "idx_job_variants_base_resume_id", "job_variants"),
    ("idx_jobvariant_jobposting", "idx_job_variants_job_posting_id", "job_variants"),
    ("idx_jobvariant_status", "idx_job_variants_status", "job_variants"),
    # Migration 004: cover_letters
    ("idx_coverletter_persona", "idx_cover_letters_persona_id", "cover_letters"),
    (
        "idx_coverletter_application",
        "idx_cover_letters_application_id",
        "cover_letters",
    ),
    ("idx_coverletter_jobposting", "idx_cover_letters_job_posting_id", "cover_letters"),
    # Migration 004: extracted_skills
    (
        "idx_extractedskill_jobposting",
        "idx_extracted_skills_job_posting_id",
        "extracted_skills",
    ),
    # Migration 005: applications
    ("idx_application_persona", "idx_applications_persona_id", "applications"),
    ("idx_application_jobposting", "idx_applications_job_posting_id", "applications"),
    ("idx_application_status", "idx_applications_persona_id_status", "applications"),
    # Migration 005: submitted_resume_pdfs
    (
        "idx_submittedresumepdf_application",
        "idx_submitted_resume_pdfs_application_id",
        "submitted_resume_pdfs",
    ),
    # Migration 005: submitted_cover_letter_pdfs
    (
        "idx_submittedcoverletterpdf_application",
        "idx_submitted_cover_letter_pdfs_application_id",
        "submitted_cover_letter_pdfs",
    ),
    (
        "idx_submittedcoverletterpdf_coverletter",
        "idx_submitted_cover_letter_pdfs_cover_letter_id",
        "submitted_cover_letter_pdfs",
    ),
    # Migration 006: timeline_events
    (
        "idx_timelineevent_application",
        "idx_timeline_events_application_id",
        "timeline_events",
    ),
    (
        "idx_timelineevent_date",
        "idx_timeline_events_application_id_event_date",
        "timeline_events",
    ),
]

TOTAL_RENAMES = 49


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
    """Patch settings.database_name so alembic migrates the test DB.

    Returns:
        Original database_name to restore later.
    """
    original = settings.database_name
    settings.database_name = f"{original}_test"
    return original


def _create_alembic_config() -> Config:
    """Create alembic Config without ini file.

    Avoids fileConfig() which disables existing loggers and breaks
    pytest's caplog fixture for tests running after migration tests.
    """
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    return cfg


async def _get_index_names(session: AsyncSession, table: str) -> set[str]:
    """Get all index names for a given table from pg_indexes."""
    result = await session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = :table"
        ),
        {"table": table},
    )
    return {row[0] for row in result.fetchall()}


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def upgraded_engine():
    """Create engine migrated to 011_rename_indexes."""
    from tests.conftest import skip_if_no_postgres

    skip_if_no_postgres()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await _reset_schema(conn)

    from alembic import command

    alembic_cfg = _create_alembic_config()
    original_name = _patch_settings_for_test_db()

    try:
        await asyncio.to_thread(command.upgrade, alembic_cfg, "011_rename_indexes")
    finally:
        settings.database_name = original_name

    yield engine

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def upgraded_session(
    upgraded_engine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create session on database migrated to 011."""
    session_factory = async_sessionmaker(
        upgraded_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Sanity: rename count matches expectation
# =============================================================================


class TestRenameMapping:
    """Verify the rename mapping is complete and consistent."""

    def test_rename_count_is_49(self):
        """Migration renames exactly 49 indexes (53 total minus 4 already correct)."""
        assert len(INDEX_RENAMES) == TOTAL_RENAMES

    def test_no_duplicate_old_names(self):
        """Every old name appears exactly once."""
        old_names = [r[0] for r in INDEX_RENAMES]
        assert len(old_names) == len(set(old_names))

    def test_no_duplicate_new_names(self):
        """Every new name appears exactly once."""
        new_names = [r[1] for r in INDEX_RENAMES]
        assert len(new_names) == len(set(new_names))

    def test_new_names_follow_convention(self):
        """All new names match idx_{table}_{columns} pattern."""
        for _old, new, table in INDEX_RENAMES:
            assert new.startswith(f"idx_{table}"), (
                f"{new} should start with idx_{table}"
            )


# =============================================================================
# Upgrade tests
# =============================================================================


class TestUpgrade:
    """After migration 011 upgrade, all indexes have new names."""

    @pytest.mark.asyncio
    async def test_all_new_names_exist(self, upgraded_session: AsyncSession):
        """Every new index name exists in pg_indexes after upgrade."""
        for _old, new, table in INDEX_RENAMES:
            indexes = await _get_index_names(upgraded_session, table)
            assert new in indexes, (
                f"Expected index {new} on table {table}, found: {indexes}"
            )

    @pytest.mark.asyncio
    async def test_no_old_names_remain(self, upgraded_session: AsyncSession):
        """No old index names remain after upgrade."""
        for old, _new, table in INDEX_RENAMES:
            indexes = await _get_index_names(upgraded_session, table)
            assert old not in indexes, (
                f"Old index {old} should not exist on table {table} after upgrade"
            )

    @pytest.mark.asyncio
    async def test_auth_indexes_unchanged(self, upgraded_session: AsyncSession):
        """Migration 010 auth indexes (already correct) are not affected."""
        auth_indexes = [
            ("accounts", "idx_accounts_user_id"),
            ("sessions", "idx_sessions_user_id"),
            ("sessions", "idx_sessions_expires"),
            ("verification_tokens", "idx_verification_tokens_expires"),
        ]
        for table, expected_name in auth_indexes:
            indexes = await _get_index_names(upgraded_session, table)
            assert expected_name in indexes, (
                f"Auth index {expected_name} should still exist on {table}"
            )


# =============================================================================
# Downgrade tests
# =============================================================================


class TestDowngrade:
    """After downgrade from 011, all indexes have old names restored."""

    @pytest.mark.asyncio
    async def test_downgrade_restores_old_names(self):
        """Downgrading 011 restores all 49 old index names."""
        from alembic import command

        from tests.conftest import skip_if_no_postgres

        skip_if_no_postgres()

        engine = create_async_engine(TEST_DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            await _reset_schema(conn)

        alembic_cfg = _create_alembic_config()
        original_name = _patch_settings_for_test_db()

        try:
            # Upgrade to 011
            await asyncio.to_thread(command.upgrade, alembic_cfg, "011_rename_indexes")

            # Downgrade back to 010
            await asyncio.to_thread(command.downgrade, alembic_cfg, "010_auth_tables")

            # Verify old names restored
            session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with session_factory() as session:
                for old, new, table in INDEX_RENAMES:
                    indexes = await _get_index_names(session, table)
                    assert old in indexes, (
                        f"Old index {old} not restored on table {table} "
                        f"after downgrade, found: {indexes}"
                    )
                    assert new not in indexes, (
                        f"New index {new} should not exist on table {table} "
                        f"after downgrade"
                    )
        finally:
            settings.database_name = original_name

        async with engine.begin() as conn:
            await _reset_schema(conn)

        await engine.dispose()
