"""Job scoring service for the Strategist pipeline.

REQ-017 §6: Single orchestrator wrapping existing scoring services.

Orchestrates the complete scoring pipeline:
1. Load persona data with skills
2. Generate/cache persona embeddings
3. Load job postings
4. Non-negotiables filter (pass/fail gate)
5. Calculate fit/stretch scores via batch_score_jobs
6. Generate LLM rationale (if fit >= RATIONALE_SCORE_THRESHOLD)
7. Build score_details JSONB for frontend drill-down
8. Save scores to persona_jobs
9. Check auto-draft threshold (no-op at MVP)
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.persona_job import PersonaJob
from app.prompts.strategist import (
    SCORE_RATIONALE_SYSTEM_PROMPT,
    build_score_rationale_prompt,
)
from app.providers import ProviderError, factory
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType
from app.repositories.persona_job_repository import PersonaJobRepository
from app.schemas.prompt_params import ScoreData
from app.services.batch_scoring import ScoredJob, batch_score_jobs
from app.services.persona_embedding_generator import generate_persona_embeddings
from app.services.score_types import ScoreResult
from app.services.scoring_flow import (
    build_filtered_score_result,
    build_scored_result,
    filter_jobs_batch,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

RATIONALE_SCORE_THRESHOLD = 65
"""Only generate LLM rationale for jobs scoring >= this. REQ-017 §9."""

_MAX_BATCH_SIZE = 500
"""Maximum number of jobs to score in a single batch (DoS protection)."""

_LOW_MATCH_RATIONALE = (
    "Low match — this role does not closely align with your "
    "current skills and experience."
)
"""Fallback rationale for jobs below the RATIONALE_SCORE_THRESHOLD."""

_NOT_AVAILABLE = "N/A"
"""Fallback for missing persona/job attributes in rationale prompts."""


# =============================================================================
# Module-level helpers (enables clean test patching)
# =============================================================================


async def _load_persona(
    db: AsyncSession,
    persona_id: UUID,
    user_id: UUID,
) -> Persona:
    """Load a persona with skills eagerly loaded.

    Args:
        db: Async database session.
        persona_id: Persona UUID to load.
        user_id: Owner's user UUID for tenant isolation.

    Returns:
        Persona ORM model with skills relationship loaded.

    Raises:
        NotFoundError: If persona does not exist or user doesn't own it.
    """
    result = await db.execute(
        select(Persona)
        .where(Persona.id == persona_id, Persona.user_id == user_id)
        .options(selectinload(Persona.skills))
    )
    persona = result.scalar_one_or_none()
    if persona is None:
        raise NotFoundError("Persona", str(persona_id))
    return persona


async def _load_jobs(
    db: AsyncSession,
    job_posting_ids: list[UUID],
    user_id: UUID,
) -> list[JobPosting]:
    """Load job postings with extracted skills eagerly loaded.

    Only returns jobs linked to the user via persona_jobs → personas,
    ensuring tenant isolation in multi-tenant deployments.

    Args:
        db: Async database session.
        job_posting_ids: UUIDs of job postings to load.
        user_id: Owner's user UUID for tenant isolation.

    Returns:
        List of JobPosting ORM models.

    Raises:
        NotFoundError: If any job posting does not exist or is not
            accessible by the user.
    """
    # Subquery: job IDs linked to this user via persona_jobs → personas
    user_job_ids = (
        select(PersonaJob.job_posting_id)
        .join(Persona, PersonaJob.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
    )

    result = await db.execute(
        select(JobPosting)
        .where(
            JobPosting.id.in_(job_posting_ids),
            JobPosting.id.in_(user_job_ids),
        )
        .options(selectinload(JobPosting.extracted_skills))
    )
    jobs = list(result.scalars().all())
    found_ids = {j.id for j in jobs}
    missing = [jid for jid in job_posting_ids if jid not in found_ids]
    if missing:
        raise NotFoundError("JobPosting", str(missing[0]))
    return jobs


async def _load_discovered_job_ids(
    db: AsyncSession,
    persona_id: UUID,
    user_id: UUID,
) -> list[UUID]:
    """Load job posting IDs for all Discovered persona_jobs.

    Args:
        db: Async database session.
        persona_id: Persona UUID.
        user_id: Owner's user UUID for tenant isolation.

    Returns:
        List of job posting UUIDs with Discovered status.
    """
    result = await db.execute(
        select(PersonaJob.job_posting_id).where(
            PersonaJob.persona_id == persona_id,
            PersonaJob.status == "Discovered",
            PersonaJob.persona_id.in_(
                select(Persona.id).where(Persona.user_id == user_id)
            ),
        )
    )
    return list(result.scalars().all())


async def _save_score(
    db: AsyncSession,
    *,
    persona_id: UUID,
    job_posting_id: UUID,
    user_id: UUID,
    fit_score: int | None,
    stretch_score: int | None,
    score_details: dict[str, Any] | None,
    filtered_reason: str | None,
) -> None:
    """Persist score to the persona_jobs table.

    Updates existing record if found, otherwise logs a warning.

    Args:
        db: Async database session.
        persona_id: Persona UUID.
        job_posting_id: Job posting UUID.
        user_id: Owner's user UUID.
        fit_score: Fit score (0-100) or None if filtered.
        stretch_score: Stretch score (0-100) or None if filtered.
        score_details: JSONB component breakdown for frontend drill-down.
        filtered_reason: Why the job was filtered (None if scored).
    """
    existing = await PersonaJobRepository.get_by_persona_and_job(
        db,
        persona_id=persona_id,
        job_posting_id=job_posting_id,
        user_id=user_id,
    )
    if existing:
        await PersonaJobRepository.update(
            db,
            existing.id,
            user_id=user_id,
            fit_score=fit_score,
            stretch_score=stretch_score,
            score_details=score_details,
            failed_non_negotiables=(
                filtered_reason.split("|") if filtered_reason else None
            ),
            scored_at=datetime.now(UTC),
        )
    else:
        logger.warning(
            "No persona_job found for persona=%s job=%s — skipping score save",
            persona_id,
            job_posting_id,
        )


# =============================================================================
# Service
# =============================================================================


class JobScoringService:
    """Orchestrates job scoring: filter -> fit/stretch -> rationale -> save.

    REQ-017 §6.2: Single orchestrator wrapping existing scoring services.
    Delegates to unchanged modules: non_negotiables_filter, fit_score,
    stretch_score, batch_scoring, scoring_flow.

    Args:
        db: Async database session (caller controls transaction).
    """

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: LLMProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self._llm_provider = llm_provider
        self._embedding_provider = embedding_provider

    async def score_job(
        self,
        persona_id: UUID,
        job_posting_id: UUID,
        user_id: UUID,
    ) -> ScoreResult:
        """Score a single job against a persona.

        REQ-017 §6.2: Convenience wrapper around score_batch().

        Args:
            persona_id: Persona to score against.
            job_posting_id: Job posting to score.
            user_id: Owner's user UUID for tenant isolation.

        Returns:
            ScoreResult with fit/stretch scores or filtered_reason.

        Raises:
            NotFoundError: If persona or job posting not found.
        """
        results = await self.score_batch(persona_id, [job_posting_id], user_id)
        if not results:
            raise NotFoundError("JobPosting", str(job_posting_id))
        return results[0]

    async def score_batch(
        self,
        persona_id: UUID,
        job_posting_ids: list[UUID],
        user_id: UUID,
    ) -> list[ScoreResult]:
        """Score multiple jobs. Loads persona embeddings once, reuses for all.

        REQ-017 §6.2: Pipeline — load persona -> embeddings -> load jobs ->
        non-negotiables filter -> fit/stretch -> rationale -> save.

        Args:
            persona_id: Persona to score against.
            job_posting_ids: Job posting UUIDs to score.
            user_id: Owner's user UUID for tenant isolation.

        Returns:
            List of ScoreResult (one per input job).

        Raises:
            NotFoundError: If persona or any job posting not found.
            ValueError: If batch size exceeds _MAX_BATCH_SIZE.
        """
        if not job_posting_ids:
            return []

        if len(job_posting_ids) > _MAX_BATCH_SIZE:
            msg = (
                f"Batch size {len(job_posting_ids)} exceeds "
                f"maximum of {_MAX_BATCH_SIZE}"
            )
            raise ValueError(msg)

        # Step 1: Load persona with skills
        persona = await _load_persona(self.db, persona_id, user_id)

        # Step 2: Generate persona embeddings (once for entire batch)
        embedding_provider = (
            self._embedding_provider or factory.get_embedding_provider()
        )

        async def _embed_fn(text: str) -> list[list[float]]:
            result = await embedding_provider.embed([text])
            return result.vectors

        # WHY type: ignore: Persona ORM model satisfies PersonaLike protocol
        # structurally, but mypy sees list[Skill] vs list[SkillLike] as
        # incompatible due to invariant generic list typing.
        persona_embeddings = await generate_persona_embeddings(persona, _embed_fn)  # type: ignore[arg-type]

        # Step 3: Load job postings (user_id for tenant isolation)
        jobs = await _load_jobs(self.db, job_posting_ids, user_id)

        # Step 4: Non-negotiables filter
        # WHY type: ignore: JobPosting satisfies JobFilterDataLike structurally
        # but mypy can't verify Protocol conformance for ORM models.
        passing_jobs, filtered_results = filter_jobs_batch(persona, jobs)  # type: ignore[type-var]

        # Build results for filtered jobs
        results: list[ScoreResult] = []
        for fr in filtered_results:
            result = build_filtered_score_result(fr)
            results.append(result)
            await _save_score(
                self.db,
                persona_id=persona_id,
                job_posting_id=fr.job_id,
                user_id=user_id,
                fit_score=None,
                stretch_score=None,
                score_details=None,
                filtered_reason=result.get("filtered_reason"),
            )

        if not passing_jobs:
            return results

        # Steps 5-6: Calculate fit/stretch scores
        # WHY type: ignore: passing_jobs came from filter_jobs_batch which
        # returns list[JobFilterDataLike]; batch_score_jobs expects
        # list[JobPostingLike]. Both are satisfied by JobPosting ORM model.
        scored_jobs = await batch_score_jobs(
            jobs=passing_jobs,
            persona=persona,
            persona_embeddings=persona_embeddings,
            embedding_provider=embedding_provider,
        )

        # Build lookup for rationale generation
        job_lookup: dict[UUID, JobPosting] = {j.id: j for j in jobs}

        # Steps 7-9: Rationale, details, save for each scored job
        for scored in scored_jobs:
            job = job_lookup.get(scored.job_id)

            # Step 7: Generate rationale (conditional on threshold)
            explanation = await self._generate_rationale(scored, persona, job)

            # Step 8: Build score_details JSONB
            score_details = _build_score_details(scored)

            # Step 9: Build ScoreResult
            result = build_scored_result(
                job_id=scored.job_id,
                fit_score=float(scored.fit_score.total),
                stretch_score=float(scored.stretch_score.total),
                explanation=explanation,
                score_details=score_details,
            )
            results.append(result)

            # Save to persona_jobs
            await _save_score(
                self.db,
                persona_id=persona_id,
                job_posting_id=scored.job_id,
                user_id=user_id,
                fit_score=scored.fit_score.total,
                stretch_score=scored.stretch_score.total,
                score_details=score_details,
                filtered_reason=None,
            )

        # Step 10: Auto-draft check (no-op at MVP per REQ-018 §3.2)

        return results

    async def rescore_all_discovered(
        self,
        persona_id: UUID,
        user_id: UUID,
    ) -> list[ScoreResult]:
        """Re-score all Discovered jobs for a persona.

        REQ-017 §6.2: Called after persona updates to refresh scores.
        Regenerates persona embeddings, then rescores all active jobs.

        Args:
            persona_id: Persona to rescore for.
            user_id: Owner's user UUID for tenant isolation.

        Returns:
            List of ScoreResult for all discovered jobs.

        Raises:
            NotFoundError: If persona not found.
        """
        # Verify persona exists
        await _load_persona(self.db, persona_id, user_id)

        # Load discovered job IDs
        job_ids = await _load_discovered_job_ids(self.db, persona_id, user_id)
        if not job_ids:
            return []

        # Chunk to respect _MAX_BATCH_SIZE (DoS protection)
        all_results: list[ScoreResult] = []
        for i in range(0, len(job_ids), _MAX_BATCH_SIZE):
            chunk = job_ids[i : i + _MAX_BATCH_SIZE]
            chunk_results = await self.score_batch(persona_id, chunk, user_id)
            all_results.extend(chunk_results)
        return all_results

    async def _generate_rationale(
        self,
        scored: ScoredJob,
        persona: Persona,
        job: JobPosting | None,
    ) -> str:
        """Generate LLM rationale for a scored job.

        Only calls LLM when fit_score >= RATIONALE_SCORE_THRESHOLD (65).
        Falls back to generic message on LLM error.

        Args:
            scored: ScoredJob with fit/stretch results.
            persona: Persona ORM model (for experience data).
            job: JobPosting ORM model (for title/company data), or None if
                the job was not found in the lookup.

        Returns:
            Rationale string (LLM-generated or fallback).
        """
        if scored.fit_score.total < RATIONALE_SCORE_THRESHOLD:
            return _LOW_MATCH_RATIONALE

        try:
            llm = self._llm_provider or factory.get_llm_provider()

            score_data = ScoreData(
                fit_score=scored.fit_score.total,
                hard_skills_pct=int(scored.fit_score.components.get("hard_skills", 0)),
                matched_hard_skills=0,
                required_hard_skills=0,
                soft_skills_pct=int(scored.fit_score.components.get("soft_skills", 0)),
                experience_match=(
                    f"{int(scored.fit_score.components.get('experience_level', 0))}%"
                ),
                job_years=str(
                    getattr(job, "years_experience_min", _NOT_AVAILABLE)
                    or _NOT_AVAILABLE
                ),
                persona_years=str(
                    getattr(persona, "years_experience", _NOT_AVAILABLE)
                    or _NOT_AVAILABLE
                ),
                logistics_match=(
                    f"{int(scored.fit_score.components.get('location_logistics', 0))}%"
                ),
                stretch_score=scored.stretch_score.total,
                role_alignment_pct=int(
                    scored.stretch_score.components.get("target_role", 0)
                ),
                target_skills_found=(
                    f"{int(scored.stretch_score.components.get('target_skills', 0))}%"
                ),
                missing_skills="See component scores",
                bonus_skills="See component scores",
            )

            user_prompt = build_score_rationale_prompt(
                job_title=getattr(job, "job_title", "Unknown"),
                company_name=getattr(job, "company_name", "Unknown"),
                scores=score_data,
            )

            messages = [
                LLMMessage(role="system", content=SCORE_RATIONALE_SYSTEM_PROMPT),
                LLMMessage(  # nosemgrep: zentropy.llm-unsanitized-input  # sanitized inside build_score_rationale_prompt()
                    role="user", content=user_prompt
                ),
            ]

            response = await llm.complete(
                messages=messages,
                task=TaskType.SCORE_RATIONALE,
                max_tokens=500,
            )

            return response.content or _LOW_MATCH_RATIONALE

        except ProviderError:
            logger.warning(
                "Rationale generation failed for job %s, using fallback",
                scored.job_id,
                exc_info=True,
            )
            return (
                f"Score: {scored.fit_score.total}/100 fit, "
                f"{scored.stretch_score.total}/100 stretch."
            )


def _build_score_details(scored: ScoredJob) -> dict[str, Any]:
    """Build JSONB-serializable score_details from ScoredJob.

    Args:
        scored: ScoredJob with fit/stretch results.

    Returns:
        Dict with fit and stretch component breakdowns for
        frontend drill-down UI (REQ-012 Appendix A.3).
    """
    return {
        "fit": {
            "total": scored.fit_score.total,
            "components": dict(scored.fit_score.components),
            "weights": dict(scored.fit_score.weights),
        },
        "stretch": {
            "total": scored.stretch_score.total,
            "components": dict(scored.stretch_score.components),
            "weights": dict(scored.stretch_score.weights),
        },
    }
