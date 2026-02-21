"""Cross-persona deduplication of job_postings.

Standalone script (not an Alembic migration). Run after migration 013,
before migration 014.

REQ-015 §11 step 6 (§11.3): Merge duplicate job_postings across personas.

Usage:
    cd backend && python -m scripts.dedup_cross_persona

Steps per duplicate group:
    1. Group job_postings by description_hash
    2. Hash collision guard: verify company_name matches
    3. Pick oldest (by created_at) as canonical
    4. Reassign ALL child FKs to canonical
    5. Handle persona_jobs UNIQUE conflicts
    6. Merge also_found_on JSONB arrays
    7. Delete duplicate rows
"""

import json
import logging
from dataclasses import dataclass, field
from typing import TypedDict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Child tables with job_posting_id FK (simple UPDATE — no UNIQUE conflicts).
# applications has UNIQUE(persona_id, job_posting_id) — handled separately.
# job_embeddings excluded: table has no migration yet (model-only).
# Frozen to prevent accidental mutation (f-string SQL uses these names).
_SIMPLE_CHILD_TABLES: frozenset[str] = frozenset(
    {
        "cover_letters",
        "job_variants",
        "extracted_skills",
    }
)


class DuplicateGroup(TypedDict):
    """A group of job_postings sharing the same description_hash."""

    description_hash: str
    job_ids: list[UUID]
    company_names: list[str]


@dataclass
class DeduplicationStats:
    """Statistics from a deduplication run."""

    groups_found: int = 0
    groups_merged: int = 0
    groups_skipped: int = 0
    duplicates_deleted: int = 0
    child_fks_reassigned: dict[str, int] = field(default_factory=dict)
    persona_jobs_reassigned: int = 0
    persona_jobs_conflicts: int = 0


async def find_duplicate_groups(
    session: AsyncSession,
) -> list[DuplicateGroup]:
    """Find job_postings groups with duplicate description_hash.

    Args:
        session: Active async database session.

    Returns:
        List of DuplicateGroup dicts with job_ids ordered oldest-first.
    """
    result = await session.execute(
        text(
            "SELECT description_hash, "
            "array_agg(id ORDER BY created_at ASC) AS job_ids, "
            "array_agg(company_name ORDER BY created_at ASC) AS company_names "
            "FROM job_postings "
            "GROUP BY description_hash "
            "HAVING count(*) > 1"
        )
    )
    return [
        DuplicateGroup(
            description_hash=row[0],
            job_ids=row[1],
            company_names=row[2],
        )
        for row in result.fetchall()
    ]


def _companies_match(company_names: list[str]) -> bool:
    """Hash collision guard: verify all company names match.

    Normalizes by stripping whitespace and lowercasing before comparison.
    Returns False if no company names are available (cannot verify).
    """
    normalized = {name.strip().lower() for name in company_names if name}
    if not normalized:
        return False
    return len(normalized) == 1


async def _reassign_child_fks(
    session: AsyncSession,
    canonical_id: UUID,
    duplicate_ids: list[UUID],
) -> dict[str, int]:
    """Reassign child FK references from duplicates to canonical.

    For simple tables: direct UPDATE.
    For applications (UNIQUE on persona_id + job_posting_id):
    reassign non-conflicting, delete conflicting.

    Returns:
        Dict mapping table name to number of rows reassigned.
    """
    stats: dict[str, int] = {}

    # Simple reassignment — no unique constraint concerns
    for table in _SIMPLE_CHILD_TABLES:
        result = await session.execute(
            text(
                f"UPDATE {table} "  # noqa: S608
                "SET job_posting_id = :cid "
                "WHERE job_posting_id = ANY(:dids)"
            ),
            {"cid": canonical_id, "dids": duplicate_ids},
        )
        stats[table] = result.rowcount

    # Applications: UNIQUE(persona_id, job_posting_id) — two-phase
    result = await session.execute(
        text(
            "UPDATE applications "
            "SET job_posting_id = :cid "
            "WHERE job_posting_id = ANY(:dids) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM applications a2 "
            "  WHERE a2.persona_id = applications.persona_id "
            "  AND a2.job_posting_id = :cid"
            ")"
        ),
        {"cid": canonical_id, "dids": duplicate_ids},
    )
    stats["applications"] = result.rowcount

    # Delete remaining conflicting applications
    del_result = await session.execute(
        text("DELETE FROM applications WHERE job_posting_id = ANY(:dids)"),
        {"dids": duplicate_ids},
    )
    if del_result.rowcount > 0:
        logger.warning(
            "Deleted %d conflicting applications during dedup "
            "(same persona had applications to both canonical and duplicate)",
            del_result.rowcount,
        )

    return stats


async def _handle_persona_jobs(
    session: AsyncSession,
    canonical_id: UUID,
    duplicate_ids: list[UUID],
) -> tuple[int, int]:
    """Reassign persona_jobs, handling UNIQUE constraint conflicts.

    Phase 1: Reassign persona_jobs where the persona does NOT already
             have a link to the canonical job.
    Phase 2: Delete remaining (conflicting) persona_jobs — the persona
             already has a link to canonical, so the duplicate is redundant.

    Returns:
        Tuple of (reassigned_count, conflict_count).
    """
    # Phase 1: Reassign non-conflicting
    result = await session.execute(
        text(
            "UPDATE persona_jobs "
            "SET job_posting_id = :cid "
            "WHERE job_posting_id = ANY(:dids) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM persona_jobs pj2 "
            "  WHERE pj2.persona_id = persona_jobs.persona_id "
            "  AND pj2.job_posting_id = :cid"
            ")"
        ),
        {"cid": canonical_id, "dids": duplicate_ids},
    )
    reassigned = result.rowcount

    # Phase 2: Delete conflicting (persona already linked to canonical)
    result = await session.execute(
        text("DELETE FROM persona_jobs WHERE job_posting_id = ANY(:dids)"),
        {"dids": duplicate_ids},
    )
    conflicts = result.rowcount

    if conflicts > 0:
        logger.info(
            "Deleted %d conflicting persona_jobs "
            "(personas already linked to canonical)",
            conflicts,
        )

    return reassigned, conflicts


async def _merge_also_found_on(
    session: AsyncSession,
    canonical_id: UUID,
    duplicate_ids: list[UUID],
) -> None:
    """Merge also_found_on JSONB arrays from duplicates into canonical.

    Deduplicates sources by source_id to avoid repeated entries.
    """
    result = await session.execute(
        text(
            "SELECT id, also_found_on "
            "FROM job_postings "
            "WHERE id = :cid OR id = ANY(:dids)"
        ),
        {"cid": canonical_id, "dids": duplicate_ids},
    )

    merged_sources: list[dict] = []
    seen_keys: set[str] = set()

    for row in result.fetchall():
        afo = row[1]
        if not isinstance(afo, dict) or "sources" not in afo:
            continue
        for source in afo["sources"]:
            if not isinstance(source, dict):
                continue
            key = str(source.get("source_id", ""))
            if key and key not in seen_keys:
                seen_keys.add(key)
                merged_sources.append(source)

    if merged_sources:
        await session.execute(
            text("UPDATE job_postings SET also_found_on = :merged WHERE id = :cid"),
            {
                "cid": canonical_id,
                "merged": json.dumps({"sources": merged_sources}),
            },
        )


async def _delete_duplicates(
    session: AsyncSession,
    duplicate_ids: list[UUID],
) -> int:
    """Delete duplicate job_postings rows.

    All child FKs must be reassigned or deleted before calling this.
    RESTRICT children (applications, cover_letters, job_variants,
    persona_jobs) must be fully reassigned first. Only extracted_skills
    uses CASCADE and would auto-delete any remaining rows.
    """
    result = await session.execute(
        text("DELETE FROM job_postings WHERE id = ANY(:dids)"),
        {"dids": duplicate_ids},
    )
    return result.rowcount


async def run_dedup(session: AsyncSession) -> DeduplicationStats:
    """Main dedup entry point.

    Finds duplicate groups by description_hash, merges each group into
    the oldest (canonical) record, and returns statistics.

    Args:
        session: Active async database session. Caller is responsible
                 for committing or rolling back.

    Returns:
        DeduplicationStats with counts of groups found, merged, skipped,
        and child records reassigned.
    """
    stats = DeduplicationStats()

    # Prevent concurrent dedup runs (advisory lock released on commit/rollback)
    await session.execute(text("SELECT pg_advisory_xact_lock(2015113)"))

    groups = await find_duplicate_groups(session)
    stats.groups_found = len(groups)

    for group in groups:
        canonical_id = group["job_ids"][0]
        duplicate_ids = group["job_ids"][1:]
        company_names = group["company_names"]

        # Hash collision guard
        if not _companies_match(company_names):
            logger.warning(
                "Skipping hash %s: company names differ %s",
                group["description_hash"],
                company_names,
            )
            stats.groups_skipped += 1
            continue

        # Reassign child FKs
        fk_stats = await _reassign_child_fks(session, canonical_id, duplicate_ids)
        for table, count in fk_stats.items():
            stats.child_fks_reassigned[table] = (
                stats.child_fks_reassigned.get(table, 0) + count
            )

        # Handle persona_jobs (with UNIQUE conflict resolution)
        reassigned, conflicts = await _handle_persona_jobs(
            session, canonical_id, duplicate_ids
        )
        stats.persona_jobs_reassigned += reassigned
        stats.persona_jobs_conflicts += conflicts

        # Merge also_found_on JSONB arrays
        await _merge_also_found_on(session, canonical_id, duplicate_ids)

        # Delete duplicate job_postings
        deleted = await _delete_duplicates(session, duplicate_ids)
        stats.duplicates_deleted += deleted
        stats.groups_merged += 1

    logger.info(
        "Dedup complete: %d groups found, %d merged, %d skipped, %d duplicates deleted",
        stats.groups_found,
        stats.groups_merged,
        stats.groups_skipped,
        stats.duplicates_deleted,
    )

    return stats


async def main() -> None:
    """CLI entry point: run dedup against the configured database."""
    import sys

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        result = await run_dedup(session)
        await session.commit()

    await engine.dispose()

    logger.info("Final stats: %s", result)
    sys.exit(0)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
