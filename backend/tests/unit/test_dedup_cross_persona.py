"""Tests for cross-persona deduplication script.

REQ-015 §11 step 6 (§11.3): Verifies that the dedup script correctly merges
duplicate job_postings across personas, reassigns child FKs, handles
persona_jobs UNIQUE conflicts, and merges also_found_on JSONB arrays.

Test data layout:
  Group 1 (merge): job_1 (persona_A), job_2 (persona_B) — same hash, same company
    Child records on job_2: extracted_skill, cover_letter
  Group 2 (skip):  job_3 (persona_A), job_4 (persona_B) — same hash, DIFFERENT company
  Unique:          job_5 (persona_A) — no duplicate
  Same-persona:    job_6, job_7 (both persona_A) — UNIQUE conflict on persona_jobs
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
from scripts.dedup_cross_persona import find_duplicate_groups, run_dedup

TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)

# ---------------------------------------------------------------------------
# Reusable SQL fragments
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
    "INSERT INTO job_sources (id, source_name, source_type, description, "
    "created_at, updated_at) "
    "VALUES (:id, :name, 'API', 'Test source', now(), now())"
)
_INSERT_JOB_POSTING = text(
    "INSERT INTO job_postings "
    "(id, persona_id, source_id, external_id, job_title, company_name, description, "
    "description_hash, first_seen_date, status, is_favorite, also_found_on, "
    "created_at, updated_at) "
    "VALUES (:id, :persona_id, :source_id, :external_id, :job_title, :company_name, "
    "'Job description text', :desc_hash, :first_seen_date, 'Discovered', false, "
    ":also_found_on, :created_at, :updated_at)"
)
_INSERT_EXTRACTED_SKILL = text(
    "INSERT INTO extracted_skills (id, job_posting_id, skill_name, skill_type) "
    "VALUES (:id, :job_posting_id, :skill_name, 'Hard')"
)
_INSERT_COVER_LETTER = text(
    "INSERT INTO cover_letters (id, persona_id, job_posting_id, draft_text, "
    "created_at, updated_at) "
    "VALUES (:id, :persona_id, :job_posting_id, 'Draft text', now(), now())"
)

# Reusable SELECT queries
_COUNT_JOB_POSTINGS = text("SELECT COUNT(*) FROM job_postings")
_COUNT_PERSONA_JOBS = text("SELECT COUNT(*) FROM persona_jobs")
_COUNT_JOB_POSTINGS_BY_IDS = text(
    "SELECT COUNT(*) FROM job_postings WHERE id = ANY(:ids)"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


async def _seed_dedup_data(
    engine: AsyncEngine,
) -> dict[str, uuid.UUID | list[uuid.UUID]]:
    """Insert test data after migration 013 for dedup testing.

    Creates:
      - 2 users (A, B), 2 personas, 1 job source
      - Group 1: job_1 (persona_A) + job_2 (persona_B) — same hash, same company
        - extracted_skill on job_2, cover_letter on job_2
      - Group 2: job_3 (persona_A) + job_4 (persona_B) — same hash, DIFFERENT company
      - Unique: job_5 (persona_A)
      - Same-persona dup: job_6 + job_7 (both persona_A) — UNIQUE conflict test
    """
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    persona_a_id = uuid.uuid4()
    persona_b_id = uuid.uuid4()
    source_id = uuid.uuid4()

    # Group 1 — mergeable duplicates
    job_1_id = uuid.uuid4()
    job_2_id = uuid.uuid4()
    # Group 2 — hash collision (different companies)
    job_3_id = uuid.uuid4()
    job_4_id = uuid.uuid4()
    # Unique
    job_5_id = uuid.uuid4()
    # Same-persona duplicates
    job_6_id = uuid.uuid4()
    job_7_id = uuid.uuid4()

    # Child records for group 1
    skill_id = uuid.uuid4()
    cover_letter_id = uuid.uuid4()

    async with session_factory() as session:
        # Users + personas
        await session.execute(
            _INSERT_USER, {"id": user_a_id, "email": "user_a@example.com"}
        )
        await session.execute(
            _INSERT_USER, {"id": user_b_id, "email": "user_b@example.com"}
        )
        await session.execute(
            _INSERT_PERSONA,
            {"id": persona_a_id, "user_id": user_a_id, "email": "pa@example.com"},
        )
        await session.execute(
            _INSERT_PERSONA,
            {"id": persona_b_id, "user_id": user_b_id, "email": "pb@example.com"},
        )
        await session.execute(
            _INSERT_JOB_SOURCE, {"id": source_id, "name": "TestSource"}
        )

        # Group 1: same hash "aaa...a", same company "TechCorp"
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_1_id,
                "persona_id": persona_a_id,
                "source_id": source_id,
                "external_id": "ext-1",
                "job_title": "Engineer",
                "company_name": "TechCorp",
                "desc_hash": "a" * 64,
                "first_seen_date": date(2026, 1, 1),
                "also_found_on": json.dumps(
                    {
                        "sources": [
                            {"source_id": "src-linkedin", "source_name": "LinkedIn"}
                        ]
                    }
                ),
                "created_at": datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
            },
        )
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_2_id,
                "persona_id": persona_b_id,
                "source_id": source_id,
                "external_id": "ext-2",
                "job_title": "Engineer",
                "company_name": "TechCorp",
                "desc_hash": "a" * 64,
                "first_seen_date": date(2026, 1, 5),
                "also_found_on": json.dumps(
                    {"sources": [{"source_id": "src-indeed", "source_name": "Indeed"}]}
                ),
                "created_at": datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC),
            },
        )

        # Group 2: same hash "bbb...b", DIFFERENT companies
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_3_id,
                "persona_id": persona_a_id,
                "source_id": source_id,
                "external_id": "ext-3",
                "job_title": "Manager",
                "company_name": "AlphaCo",
                "desc_hash": "b" * 64,
                "first_seen_date": date(2026, 1, 2),
                "also_found_on": json.dumps({"sources": []}),
                "created_at": datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC),
            },
        )
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_4_id,
                "persona_id": persona_b_id,
                "source_id": source_id,
                "external_id": "ext-4",
                "job_title": "Manager",
                "company_name": "BetaCo",
                "desc_hash": "b" * 64,
                "first_seen_date": date(2026, 1, 3),
                "also_found_on": json.dumps({"sources": []}),
                "created_at": datetime(2026, 1, 3, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 3, 10, 0, 0, tzinfo=UTC),
            },
        )

        # Unique job (no duplicate)
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_5_id,
                "persona_id": persona_a_id,
                "source_id": source_id,
                "external_id": "ext-5",
                "job_title": "Designer",
                "company_name": "SoloCorp",
                "desc_hash": "c" * 64,
                "first_seen_date": date(2026, 1, 4),
                "also_found_on": json.dumps({"sources": []}),
                "created_at": datetime(2026, 1, 4, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 4, 10, 0, 0, tzinfo=UTC),
            },
        )

        # Same-persona duplicates: both persona_A, hash "ddd...d", same company
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_6_id,
                "persona_id": persona_a_id,
                "source_id": source_id,
                "external_id": "ext-6",
                "job_title": "Analyst",
                "company_name": "DupCorp",
                "desc_hash": "d" * 64,
                "first_seen_date": date(2026, 1, 6),
                "also_found_on": json.dumps({"sources": []}),
                "created_at": datetime(2026, 1, 6, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 6, 10, 0, 0, tzinfo=UTC),
            },
        )
        await session.execute(
            _INSERT_JOB_POSTING,
            {
                "id": job_7_id,
                "persona_id": persona_a_id,
                "source_id": source_id,
                "external_id": "ext-7",
                "job_title": "Analyst",
                "company_name": "DupCorp",
                "desc_hash": "d" * 64,
                "first_seen_date": date(2026, 1, 7),
                "also_found_on": json.dumps({"sources": []}),
                "created_at": datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC),
                "updated_at": datetime(2026, 1, 7, 10, 0, 0, tzinfo=UTC),
            },
        )

        # Child records on job_2 (group 1 duplicate — persona_B's copy)
        await session.execute(
            _INSERT_EXTRACTED_SKILL,
            {
                "id": skill_id,
                "job_posting_id": job_2_id,
                "skill_name": "Python",
            },
        )
        await session.execute(
            _INSERT_COVER_LETTER,
            {
                "id": cover_letter_id,
                "persona_id": persona_b_id,
                "job_posting_id": job_2_id,
            },
        )

        await session.commit()

    return {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "persona_a_id": persona_a_id,
        "persona_b_id": persona_b_id,
        "source_id": source_id,
        "job_1_id": job_1_id,
        "job_2_id": job_2_id,
        "job_3_id": job_3_id,
        "job_4_id": job_4_id,
        "job_5_id": job_5_id,
        "job_6_id": job_6_id,
        "job_7_id": job_7_id,
        "skill_id": skill_id,
        "cover_letter_id": cover_letter_id,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def dedup_session() -> AsyncGenerator[
    tuple[AsyncSession, dict[str, uuid.UUID | list[uuid.UUID]]], None
]:
    """Migrate to 013, seed dedup test data, yield session + IDs.

    Note: seed data is inserted AFTER migration 013, so persona_jobs only
    exist for the seeded job_postings (via the backfill migration). Additional
    job_postings added by _seed_dedup_data do NOT get auto-backfilled — we
    must insert their persona_jobs manually.
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
        # Migrate to 013 (empty DB — backfill does nothing)
        await asyncio.to_thread(
            command.upgrade, alembic_cfg, "013_backfill_persona_jobs"
        )
    finally:
        settings.database_name = original_name

    # Seed test data (job_postings + child records)
    ids = await _seed_dedup_data(engine)

    # Manually insert persona_jobs for seeded job_postings
    # (migration 013 backfill ran on empty DB, so no auto-backfill)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        insert_pj = text(
            "INSERT INTO persona_jobs (persona_id, job_posting_id, status, "
            "discovery_method, discovered_at, created_at, updated_at) "
            "VALUES (:pid, :jpid, 'Discovered', 'scouter', now(), now(), now())"
        )
        job_persona_pairs = [
            (ids["persona_a_id"], ids["job_1_id"]),
            (ids["persona_b_id"], ids["job_2_id"]),
            (ids["persona_a_id"], ids["job_3_id"]),
            (ids["persona_b_id"], ids["job_4_id"]),
            (ids["persona_a_id"], ids["job_5_id"]),
            (ids["persona_a_id"], ids["job_6_id"]),
            (ids["persona_a_id"], ids["job_7_id"]),
        ]
        for persona_id, job_id in job_persona_pairs:
            await session.execute(insert_pj, {"pid": persona_id, "jpid": job_id})
        await session.commit()

    async with session_factory() as session:
        yield session, ids
        await session.rollback()

    async with engine.begin() as conn:
        await _reset_schema(conn)

    await engine.dispose()


@pytest_asyncio.fixture
async def empty_dedup_session() -> AsyncGenerator[AsyncSession, None]:
    """Migrate to 013 on empty DB — no data to dedup."""
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


# ===========================================================================
# A. Group detection
# ===========================================================================


class TestFindDuplicateGroups:
    """Verify duplicate group detection by description_hash."""

    @pytest.mark.asyncio
    async def test_finds_correct_number_of_groups(self, dedup_session):
        """Should find 3 duplicate groups (a, b, d hashes)."""
        session, _ = dedup_session
        groups = await find_duplicate_groups(session)
        assert len(groups) == 3

    @pytest.mark.asyncio
    async def test_groups_ordered_by_created_at(self, dedup_session):
        """Within each group, job_ids are ordered oldest-first."""
        session, ids = dedup_session
        groups = await find_duplicate_groups(session)

        # Find the group with hash "aaa...a"
        group_a = next(g for g in groups if g["description_hash"] == "a" * 64)
        assert group_a["job_ids"][0] == ids["job_1_id"]
        assert group_a["job_ids"][1] == ids["job_2_id"]

    @pytest.mark.asyncio
    async def test_no_duplicates_returns_empty(self, empty_dedup_session):
        """Empty DB produces no duplicate groups."""
        groups = await find_duplicate_groups(empty_dedup_session)
        assert len(groups) == 0


# ===========================================================================
# B. Hash collision guard
# ===========================================================================


class TestHashCollisionGuard:
    """Verify company name mismatch skips merge (hash collision defense)."""

    @pytest.mark.asyncio
    async def test_skips_group_with_different_companies(self, dedup_session):
        """Group 2 (AlphaCo vs BetaCo) should be skipped."""
        session, ids = dedup_session
        stats = await run_dedup(session)

        # Group 2 jobs should both still exist
        result = await session.execute(
            _COUNT_JOB_POSTINGS_BY_IDS,
            {"ids": [ids["job_3_id"], ids["job_4_id"]]},
        )
        assert result.scalar() == 2
        assert stats.groups_skipped == 1


# ===========================================================================
# C. FK reassignment
# ===========================================================================


class TestFkReassignment:
    """Verify child FK references reassigned from duplicate to canonical."""

    @pytest.mark.asyncio
    async def test_extracted_skills_reassigned(self, dedup_session):
        """Extracted skill on job_2 should point to job_1 after dedup."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            text("SELECT job_posting_id FROM extracted_skills WHERE id = :id"),
            {"id": ids["skill_id"]},
        )
        assert result.scalar() == ids["job_1_id"]

    @pytest.mark.asyncio
    async def test_cover_letters_reassigned(self, dedup_session):
        """Cover letter on job_2 should point to job_1 after dedup."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            text("SELECT job_posting_id FROM cover_letters WHERE id = :id"),
            {"id": ids["cover_letter_id"]},
        )
        assert result.scalar() == ids["job_1_id"]


# ===========================================================================
# D. persona_jobs handling (UNIQUE conflict)
# ===========================================================================


class TestPersonaJobsHandling:
    """Verify persona_jobs reassignment with UNIQUE constraint conflicts."""

    @pytest.mark.asyncio
    async def test_cross_persona_link_reassigned(self, dedup_session):
        """persona_B's link to job_2 should be reassigned to job_1."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            text(
                "SELECT job_posting_id FROM persona_jobs "
                "WHERE persona_id = :pid AND job_posting_id = :jpid"
            ),
            {"pid": ids["persona_b_id"], "jpid": ids["job_1_id"]},
        )
        assert result.scalar() == ids["job_1_id"]

    @pytest.mark.asyncio
    async def test_same_persona_conflict_deletes_duplicate_link(self, dedup_session):
        """When persona_A has links to both job_6 and job_7, the duplicate
        link (job_7) should be deleted — not reassigned (UNIQUE violation)."""
        session, ids = dedup_session
        await run_dedup(session)

        # persona_A should have exactly one link to job_6 (canonical)
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM persona_jobs "
                "WHERE persona_id = :pid AND job_posting_id = :jpid"
            ),
            {"pid": ids["persona_a_id"], "jpid": ids["job_6_id"]},
        )
        assert result.scalar() == 1

        # No links to deleted job_7
        result = await session.execute(
            text("SELECT COUNT(*) FROM persona_jobs WHERE job_posting_id = :jpid"),
            {"jpid": ids["job_7_id"]},
        )
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_stats_report_conflict_count(self, dedup_session):
        """Stats should report the number of persona_jobs conflicts."""
        session, _ = dedup_session
        stats = await run_dedup(session)

        # Group 4 (same-persona dup): 1 conflict
        assert stats.persona_jobs_conflicts == 1


# ===========================================================================
# E. also_found_on merge
# ===========================================================================


class TestAlsoFoundOnMerge:
    """Verify also_found_on JSONB arrays merged during dedup."""

    @pytest.mark.asyncio
    async def test_also_found_on_sources_merged(self, dedup_session):
        """Canonical job_1 should have sources from both job_1 and job_2."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            text("SELECT also_found_on FROM job_postings WHERE id = :id"),
            {"id": ids["job_1_id"]},
        )
        afo = result.scalar()
        source_ids = {s["source_id"] for s in afo["sources"]}
        assert "src-linkedin" in source_ids
        assert "src-indeed" in source_ids

    @pytest.mark.asyncio
    async def test_also_found_on_no_duplicates(self, dedup_session):
        """Merged sources should not contain duplicate source_ids."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            text("SELECT also_found_on FROM job_postings WHERE id = :id"),
            {"id": ids["job_1_id"]},
        )
        afo = result.scalar()
        source_ids = [s["source_id"] for s in afo["sources"]]
        assert len(source_ids) == len(set(source_ids))


# ===========================================================================
# F. Duplicate deletion
# ===========================================================================


class TestDuplicateDeletion:
    """Verify duplicate job_postings are deleted after merge."""

    @pytest.mark.asyncio
    async def test_duplicates_deleted(self, dedup_session):
        """job_2 and job_7 should be deleted (duplicates from group 1 and 4)."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            _COUNT_JOB_POSTINGS_BY_IDS,
            {"ids": [ids["job_2_id"], ids["job_7_id"]]},
        )
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_canonical_jobs_preserved(self, dedup_session):
        """Canonical jobs (job_1, job_6) should still exist."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            _COUNT_JOB_POSTINGS_BY_IDS,
            {"ids": [ids["job_1_id"], ids["job_6_id"]]},
        )
        assert result.scalar() == 2

    @pytest.mark.asyncio
    async def test_skipped_group_jobs_preserved(self, dedup_session):
        """Group 2 jobs (hash collision — skipped) should both exist."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            _COUNT_JOB_POSTINGS_BY_IDS,
            {"ids": [ids["job_3_id"], ids["job_4_id"]]},
        )
        assert result.scalar() == 2

    @pytest.mark.asyncio
    async def test_unique_job_preserved(self, dedup_session):
        """job_5 (no duplicate) should still exist."""
        session, ids = dedup_session
        await run_dedup(session)

        result = await session.execute(
            text("SELECT COUNT(*) FROM job_postings WHERE id = :id"),
            {"id": ids["job_5_id"]},
        )
        assert result.scalar() == 1


# ===========================================================================
# G. Integration — run_dedup stats
# ===========================================================================


class TestRunDedupIntegration:
    """Verify run_dedup returns correct aggregate statistics."""

    @pytest.mark.asyncio
    async def test_stats_groups_found(self, dedup_session):
        """Should find 3 duplicate groups total."""
        session, _ = dedup_session
        stats = await run_dedup(session)
        assert stats.groups_found == 3

    @pytest.mark.asyncio
    async def test_stats_groups_merged(self, dedup_session):
        """Should merge 2 groups (group 1 and same-persona group)."""
        session, _ = dedup_session
        stats = await run_dedup(session)
        assert stats.groups_merged == 2

    @pytest.mark.asyncio
    async def test_stats_duplicates_deleted(self, dedup_session):
        """Should delete 2 duplicate job_postings (job_2 and job_7)."""
        session, _ = dedup_session
        stats = await run_dedup(session)
        assert stats.duplicates_deleted == 2

    @pytest.mark.asyncio
    async def test_stats_persona_jobs_reassigned(self, dedup_session):
        """Should reassign 1 persona_jobs link (persona_B: job_2 → job_1)."""
        session, _ = dedup_session
        stats = await run_dedup(session)
        assert stats.persona_jobs_reassigned == 1

    @pytest.mark.asyncio
    async def test_final_job_count(self, dedup_session):
        """After dedup, 5 job_postings should remain (7 - 2 deleted)."""
        session, _ = dedup_session
        await run_dedup(session)

        result = await session.execute(_COUNT_JOB_POSTINGS)
        assert result.scalar() == 5

    @pytest.mark.asyncio
    async def test_final_persona_jobs_count(self, dedup_session):
        """After dedup, 6 persona_jobs should remain (7 - 1 conflict)."""
        session, _ = dedup_session
        await run_dedup(session)

        result = await session.execute(_COUNT_PERSONA_JOBS)
        assert result.scalar() == 6


# ===========================================================================
# H. Empty database edge case
# ===========================================================================


class TestRunDedupEmptyDb:
    """Verify dedup handles empty database gracefully."""

    @pytest.mark.asyncio
    async def test_empty_db_no_error(self, empty_dedup_session):
        """run_dedup on empty DB should succeed with zero stats."""
        stats = await run_dedup(empty_dedup_session)
        assert stats.groups_found == 0
        assert stats.groups_merged == 0
        assert stats.duplicates_deleted == 0
