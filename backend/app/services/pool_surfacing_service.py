"""Pool surfacing service for the shared job pool.

REQ-015 §7: Background surfacing of pool jobs to matching personas.

Flow per surfacing pass:
1. Query new active jobs since last run (max 50).
2. For each job, query all personas with loaded skills.
3. Keyword pre-screen: skip if no skill overlap.
4. Lightweight fit score: hard skills overlap, experience alignment,
   work model alignment. Soft skills and role title use neutral score.
5. If fit_score >= persona.minimum_fit_threshold → create persona_jobs
   with discovery_method='pool'.
6. UNIQUE constraint prevents re-surfacing.

Cross-tenant: runs with system-level privileges (no user_id scope).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.persona_job import PersonaJob
from app.services.content_security import release_expired_quarantines
from app.services.pool_scoring import calculate_lightweight_fit, keyword_pre_screen

logger = logging.getLogger(__name__)

# Rate limits (REQ-015 §7.4)
_MAX_JOBS_PER_PASS = 50
_MAX_PERSONAS_PER_JOB = 100

# Bound persona query to prevent OOM with large user bases.
_MAX_PERSONAS_PER_QUERY = 500


@dataclass(frozen=True)
class SurfacingPassResult:
    """Result of a single surfacing pass.

    Attributes:
        jobs_processed: Number of jobs evaluated.
        links_created: Number of new persona_jobs links created.
        links_skipped_threshold: Skipped because fit_score < threshold.
        links_skipped_existing: Skipped because link already existed.
        started_at: When the pass started.
        finished_at: When the pass finished.
    """

    jobs_processed: int
    links_created: int
    links_skipped_threshold: int
    links_skipped_existing: int
    started_at: datetime
    finished_at: datetime


# ---------------------------------------------------------------------------
# Database query helpers
# ---------------------------------------------------------------------------


async def get_unsurfaced_jobs(
    db: AsyncSession,
    *,
    since: datetime,
    limit: int = _MAX_JOBS_PER_PASS,
) -> list[JobPosting]:
    """Query new active, non-quarantined job postings since a given timestamp.

    REQ-015 §8.4: Surfacing worker skips quarantined jobs to prevent
    pool poisoning from affecting other users.

    Args:
        db: Async database session.
        since: Only include jobs created after this timestamp.
        limit: Maximum number of jobs to return.

    Returns:
        List of active, non-quarantined JobPosting records, newest first.
    """
    stmt = (
        select(JobPosting)
        .where(
            JobPosting.is_active.is_(True),
            JobPosting.is_quarantined.is_(False),
            JobPosting.created_at >= since,
        )
        .order_by(JobPosting.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_active_personas_with_skills(
    db: AsyncSession,
    *,
    limit: int = _MAX_PERSONAS_PER_QUERY,
) -> list[Persona]:
    """Query personas that have completed onboarding, with skills loaded.

    Args:
        db: Async database session.
        limit: Maximum personas to load (prevents OOM with large user bases).

    Returns:
        List of Persona records with skills eagerly loaded.
    """
    stmt = (
        select(Persona)
        .where(Persona.onboarding_complete.is_(True))
        .options(selectinload(Persona.skills))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_existing_persona_ids_for_job(
    db: AsyncSession,
    job_posting_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Query persona IDs that already have a link to this job.

    Args:
        db: Async database session.
        job_posting_id: UUID of the job posting.

    Returns:
        Set of persona UUIDs with existing persona_jobs links.
    """
    stmt = select(PersonaJob.persona_id).where(
        PersonaJob.job_posting_id == job_posting_id
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


# ---------------------------------------------------------------------------
# Surfacing orchestration
# ---------------------------------------------------------------------------


async def surface_job_to_personas(
    db: AsyncSession,
    job: JobPosting,
    personas: list[Persona],
    *,
    max_personas: int = _MAX_PERSONAS_PER_JOB,
) -> tuple[int, int, int]:
    """Surface a single job to matching personas.

    Args:
        db: Async database session.
        job: The job posting to surface.
        personas: All candidate personas (with skills loaded).
        max_personas: Maximum personas to evaluate per job.

    Returns:
        Tuple of (links_created, skipped_threshold, skipped_existing).
    """
    existing_persona_ids = await get_existing_persona_ids_for_job(db, job.id)

    created = 0
    skipped_threshold = 0
    skipped_existing = 0

    evaluated = 0
    for persona in personas:
        if evaluated >= max_personas:
            break

        # Skip already-linked personas
        if persona.id in existing_persona_ids:
            skipped_existing += 1
            continue

        evaluated += 1

        # Keyword pre-screen
        skill_names = [s.skill_name for s in persona.skills]
        if not keyword_pre_screen(job.job_title, job.description or "", skill_names):
            skipped_threshold += 1
            continue

        # Lightweight fit score
        fit_result = calculate_lightweight_fit(job, persona, persona.skills)

        if fit_result.total < persona.minimum_fit_threshold:
            skipped_threshold += 1
            continue

        # Create persona_jobs link
        link = await _create_pool_link(
            db,
            persona_id=persona.id,
            job_posting_id=job.id,
            fit_score=fit_result.total,
        )
        if link is not None:
            created += 1
        else:
            skipped_existing += 1

    return created, skipped_threshold, skipped_existing


async def run_surfacing_pass(
    db: AsyncSession,
    *,
    since: datetime,
) -> SurfacingPassResult:
    """Execute a single surfacing pass.

    REQ-015 §7: Main entry point for the surfacing worker.

    Args:
        db: Async database session.
        since: Only evaluate jobs created after this timestamp.

    Returns:
        SurfacingPassResult with statistics.
    """
    started_at = datetime.now(UTC)

    # REQ-015 §8.4: Release expired quarantines before surfacing
    await release_expired_quarantines(db)

    jobs = await get_unsurfaced_jobs(db, since=since)
    if not jobs:
        return SurfacingPassResult(
            jobs_processed=0,
            links_created=0,
            links_skipped_threshold=0,
            links_skipped_existing=0,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )

    personas = await get_active_personas_with_skills(db)
    if not personas:
        return SurfacingPassResult(
            jobs_processed=len(jobs),
            links_created=0,
            links_skipped_threshold=0,
            links_skipped_existing=0,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )

    total_created = 0
    total_skipped_threshold = 0
    total_skipped_existing = 0

    for job in jobs:
        created, skipped_thresh, skipped_exist = await surface_job_to_personas(
            db, job, personas
        )
        total_created += created
        total_skipped_threshold += skipped_thresh
        total_skipped_existing += skipped_exist

    await db.commit()

    finished_at = datetime.now(UTC)
    logger.info(
        "Surfacing pass complete: %d jobs, %d links created, %d below threshold, %d existing",
        len(jobs),
        total_created,
        total_skipped_threshold,
        total_skipped_existing,
    )

    return SurfacingPassResult(
        jobs_processed=len(jobs),
        links_created=total_created,
        links_skipped_threshold=total_skipped_threshold,
        links_skipped_existing=total_skipped_existing,
        started_at=started_at,
        finished_at=finished_at,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _create_pool_link(
    db: AsyncSession,
    *,
    persona_id: uuid.UUID,
    job_posting_id: uuid.UUID,
    fit_score: int,
) -> PersonaJob | None:
    """Create a persona_jobs link with discovery_method='pool'.

    Uses savepoint + IntegrityError recovery for UNIQUE constraint races.

    Args:
        db: Async database session.
        persona_id: FK to personas.
        job_posting_id: FK to job_postings.
        fit_score: Calculated lightweight fit score.

    Returns:
        Created PersonaJob, or None if link already exists.
    """
    try:
        async with db.begin_nested():
            persona_job = PersonaJob(
                persona_id=persona_id,
                job_posting_id=job_posting_id,
                discovery_method="pool",
                status="Discovered",
                fit_score=fit_score,
                scored_at=datetime.now(UTC),
            )
            db.add(persona_job)
            await db.flush()
        return persona_job
    except IntegrityError:
        logger.debug(
            "Pool link already exists: persona=%s job=%s",
            persona_id,
            job_posting_id,
        )
        return None
