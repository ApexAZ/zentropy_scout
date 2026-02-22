"""Global deduplication service for the shared job pool.

REQ-015 §6: 4-step global dedup pipeline.
1. source_id + external_id match → UPDATE existing
2. description_hash match → ADD to also_found_on
3. company + title + description similarity → LINK as repost
4. No match → CREATE new in shared pool

After dedup: create persona_jobs link for discovering user.
Race condition: savepoint + IntegrityError recovery.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.persona_job import PersonaJob
from app.repositories.job_posting_repository import (
    CREATABLE_OPTIONAL_FIELDS,
    JobPostingRepository,
)
from app.repositories.persona_job_repository import PersonaJobRepository
from app.services.job_deduplication import (
    DESCRIPTION_SIMILARITY_THRESHOLD_HIGH,
    DESCRIPTION_SIMILARITY_THRESHOLD_MEDIUM,
    calculate_description_similarity,
    is_similar_title,
)

logger = logging.getLogger(__name__)

# Cap description length for SequenceMatcher to bound O(n²) comparison time.
# 50 KB covers even the longest job descriptions while preventing DoS.
_MAX_SIMILARITY_DESC_LENGTH = 50_000

# Fields that can be updated on a same-source re-encounter.
# Excludes immutable/computed fields: id, source_id, created_at, updated_at,
# first_seen_date, ghost_signals, ghost_score, repost_count,
# previous_posting_ids, also_found_on, is_active.
_SOURCE_UPDATE_FIELDS: frozenset[str] = frozenset(
    {
        "job_title",
        "company_name",
        "company_url",
        "source_url",
        "apply_url",
        "location",
        "work_model",
        "seniority_level",
        "salary_min",
        "salary_max",
        "salary_currency",
        "description",
        "description_hash",
        "culture_text",
        "requirements",
        "raw_text",
        "years_experience_min",
        "years_experience_max",
        "posted_date",
        "application_deadline",
    }
)


@dataclass(frozen=True)
class DeduplicationOutcome:
    """Result of the global deduplication pipeline.

    Attributes:
        action: Which dedup step matched.
        job_posting: The shared pool JobPosting (existing or new).
        persona_job: The per-user PersonaJob link.
        confidence: Match confidence (High, Medium, or None for create_new).
        matched_job_id: UUID of the matched existing job, or None.
    """

    action: Literal[
        "update_existing",
        "add_to_also_found_on",
        "create_linked_repost",
        "create_new",
    ]
    job_posting: JobPosting
    persona_job: PersonaJob
    confidence: Literal["High", "Medium"] | None
    matched_job_id: uuid.UUID | None


async def deduplicate_and_save(
    db: AsyncSession,
    *,
    job_data: dict[str, Any],
    persona_id: uuid.UUID,
    user_id: uuid.UUID,
    discovery_method: Literal["scouter", "manual", "pool"] = "scouter",
) -> DeduplicationOutcome:
    """Run the global dedup pipeline and save to shared pool.

    Args:
        db: Async database session (caller manages transaction).
        job_data: Job posting data dict with keys:
            - source_id (UUID, required)
            - job_title (str, required)
            - company_name (str, required)
            - description (str, required)
            - description_hash (str, required)
            - first_seen_date (date, optional — defaults to today)
            - external_id (str, optional)
            - Plus optional fields (location, salary_min, etc.)
        persona_id: UUID of the discovering persona.
        user_id: UUID of the authenticated user (ownership check).
        discovery_method: How the job was discovered.

    Returns:
        DeduplicationOutcome with action, job posting, persona link,
        and match confidence.
    """
    source_id: uuid.UUID = job_data["source_id"]
    external_id: str | None = job_data.get("external_id")

    # Step 1: source_id + external_id match → UPDATE existing
    if external_id is not None:
        existing = await JobPostingRepository.get_by_source_and_external_id(
            db, source_id=source_id, external_id=external_id
        )
        if existing is not None:
            update_fields = _extract_source_update_fields(job_data)
            update_fields["last_verified_at"] = datetime.now(UTC)
            await JobPostingRepository.update(db, existing.id, **update_fields)
            await db.refresh(existing)

            persona_job = await _create_or_get_link(
                db, persona_id, existing.id, user_id, discovery_method
            )
            return DeduplicationOutcome(
                action="update_existing",
                job_posting=existing,
                persona_job=persona_job,
                confidence="High",
                matched_job_id=existing.id,
            )

    # Step 2: description_hash match → ADD to also_found_on
    description_hash: str = job_data["description_hash"]
    existing = await JobPostingRepository.get_by_description_hash(db, description_hash)
    if existing is not None:
        new_also_found_on = _build_updated_also_found_on(existing, job_data)
        await JobPostingRepository.update(
            db, existing.id, also_found_on=new_also_found_on
        )
        await db.refresh(existing)

        persona_job = await _create_or_get_link(
            db, persona_id, existing.id, user_id, discovery_method
        )
        return DeduplicationOutcome(
            action="add_to_also_found_on",
            job_posting=existing,
            persona_job=persona_job,
            confidence="High",
            matched_job_id=existing.id,
        )

    # Step 3: company + title + description similarity → LINK as repost
    company_name: str = job_data["company_name"]
    candidates = await JobPostingRepository.get_by_company_for_similarity(
        db, company_name
    )
    repost_result = _find_similarity_match(job_data, candidates)
    if repost_result is not None:
        matched_job, confidence = repost_result
        repost_jp = await _create_repost(db, job_data, matched_job)

        persona_job = await _create_or_get_link(
            db, persona_id, repost_jp.id, user_id, discovery_method
        )
        return DeduplicationOutcome(
            action="create_linked_repost",
            job_posting=repost_jp,
            persona_job=persona_job,
            confidence=confidence,
            matched_job_id=matched_job.id,
        )

    # Step 4: No match → CREATE new in shared pool
    job_posting = await _create_with_conflict_recovery(db, job_data)

    persona_job = await _create_or_get_link(
        db, persona_id, job_posting.id, user_id, discovery_method
    )
    return DeduplicationOutcome(
        action="create_new",
        job_posting=job_posting,
        persona_job=persona_job,
        confidence=None,
        matched_job_id=None,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_source_update_fields(job_data: dict[str, Any]) -> dict[str, Any]:
    """Extract source-provided fields for updating an existing job."""
    return {k: v for k, v in job_data.items() if k in _SOURCE_UPDATE_FIELDS}


def _extract_create_fields(
    job_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract fields for JobPostingRepository.create() from job_data."""
    required = {
        "source_id": job_data["source_id"],
        "job_title": job_data["job_title"],
        "company_name": job_data["company_name"],
        "description": job_data["description"],
        "description_hash": job_data["description_hash"],
        "first_seen_date": job_data.get("first_seen_date", date.today()),
    }
    optional = {
        k: v
        for k, v in job_data.items()
        if k in CREATABLE_OPTIONAL_FIELDS and v is not None
    }
    return {**required, **optional}


def _build_updated_also_found_on(
    existing: JobPosting, job_data: dict[str, Any]
) -> dict[str, Any]:
    """Build a new also_found_on dict with the new source added.

    Returns a NEW dict (not in-place mutation) so SQLAlchemy's JSONB
    change detection works correctly.
    """
    old = existing.also_found_on or {"sources": []}
    sources: list[dict[str, Any]] = list(old.get("sources", []))

    new_source_id = str(job_data["source_id"])
    existing_source_ids = {s.get("source_id") for s in sources}

    if new_source_id not in existing_source_ids:
        sources.append(
            {
                "source_id": new_source_id,
                "external_id": job_data.get("external_id"),
                "source_url": job_data.get("source_url"),
                "found_at": datetime.now(UTC).isoformat(),
            }
        )

    return {"sources": sources}


def _find_similarity_match(
    job_data: dict[str, Any],
    candidates: list[JobPosting],
) -> tuple[JobPosting, Literal["High", "Medium"]] | None:
    """Find the best similarity match among candidates.

    Returns (matched_job, confidence) or None.
    Descriptions are truncated to _MAX_SIMILARITY_DESC_LENGTH to bound
    SequenceMatcher O(n²) comparison time.
    """
    new_title = job_data.get("job_title", "")
    new_description = job_data.get("description", "")[:_MAX_SIMILARITY_DESC_LENGTH]

    best_medium: tuple[JobPosting | None, float] = (None, 0.0)

    for candidate in candidates:
        if not is_similar_title(new_title, candidate.job_title):
            continue

        candidate_desc = candidate.description[:_MAX_SIMILARITY_DESC_LENGTH]
        similarity = calculate_description_similarity(new_description, candidate_desc)
        if similarity > DESCRIPTION_SIMILARITY_THRESHOLD_HIGH:
            return (candidate, "High")
        if (
            similarity > DESCRIPTION_SIMILARITY_THRESHOLD_MEDIUM
            and similarity > best_medium[1]
        ):
            best_medium = (candidate, similarity)

    if best_medium[0] is not None:
        return (best_medium[0], "Medium")
    return None


async def _create_repost(
    db: AsyncSession,
    job_data: dict[str, Any],
    matched_job: JobPosting,
) -> JobPosting:
    """Create a new job posting linked as a repost of the matched job."""
    create_fields = _extract_create_fields(job_data)

    # Build repost chain
    matched_id = str(matched_job.id)
    prior_chain = matched_job.previous_posting_ids or []
    previous_posting_ids = [matched_id, *list(prior_chain)]
    repost_count = (matched_job.repost_count or 0) + 1

    job_posting = await JobPostingRepository.create(
        db,
        **create_fields,
    )
    # Set repost fields via update (not in create's optional fields)
    await JobPostingRepository.update(
        db,
        job_posting.id,
        previous_posting_ids=previous_posting_ids,
        repost_count=repost_count,
    )
    await db.refresh(job_posting)
    return job_posting


async def _create_with_conflict_recovery(
    db: AsyncSession,
    job_data: dict[str, Any],
) -> JobPosting:
    """Create a job posting, recovering from UNIQUE constraint conflicts.

    Uses a savepoint so IntegrityError doesn't invalidate the outer
    transaction. On conflict, looks up the existing record.
    """
    create_fields = _extract_create_fields(job_data)

    try:
        async with db.begin_nested():
            job_posting = await JobPostingRepository.create(db, **create_fields)
        return job_posting
    except IntegrityError:
        # Race condition: another process created the same job.
        # Savepoint was rolled back; session is still usable.
        source_id = job_data["source_id"]
        external_id = job_data.get("external_id")
        if external_id is not None:
            existing = await JobPostingRepository.get_by_source_and_external_id(
                db, source_id=source_id, external_id=external_id
            )
            if existing is not None:
                return existing
        # Fallback: description_hash lookup
        existing = await JobPostingRepository.get_by_description_hash(
            db, job_data["description_hash"]
        )
        if existing is not None:
            return existing
        raise  # Can't recover — re-raise


async def _create_or_get_link(
    db: AsyncSession,
    persona_id: uuid.UUID,
    job_posting_id: uuid.UUID,
    user_id: uuid.UUID,
    discovery_method: Literal["scouter", "manual", "pool"],
) -> PersonaJob:
    """Create persona_jobs link, or return existing if already linked.

    Uses savepoint for IntegrityError recovery on UNIQUE constraint
    (persona_id, job_posting_id).
    """
    # Check existing first (common path, avoids savepoint overhead)
    existing = await PersonaJobRepository.get_by_persona_and_job(
        db,
        persona_id=persona_id,
        job_posting_id=job_posting_id,
        user_id=user_id,
    )
    if existing is not None:
        return existing

    try:
        async with db.begin_nested():
            persona_job = await PersonaJobRepository.create(
                db,
                persona_id=persona_id,
                job_posting_id=job_posting_id,
                discovery_method=discovery_method,
                user_id=user_id,
            )
        if persona_job is None:
            logger.warning("Persona %s not owned by user %s", persona_id, user_id)
            msg = "Persona not owned by authenticated user"
            raise ValueError(msg)
        return persona_job
    except IntegrityError:
        # Race condition: link created by another process
        existing = await PersonaJobRepository.get_by_persona_and_job(
            db,
            persona_id=persona_id,
            job_posting_id=job_posting_id,
            user_id=user_id,
        )
        if existing is not None:
            return existing
        raise  # Can't recover
