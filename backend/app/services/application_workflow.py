"""Application workflow — persist Ghostwriter output into database entities.

REQ-002 §6.2: After the Ghostwriter agent finishes generating materials,
this service bridges the agent output (GhostwriterState) to database
entities (JobVariant, CoverLetter, Application).

Three public functions matching the application lifecycle:

1. persist_draft_materials — Creates draft JobVariant + CoverLetter
2. approve_materials — Approves materials with snapshot population
3. create_application — Creates Application + TimelineEvent
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, InvalidStateError, NotFoundError
from app.models.application import Application, TimelineEvent
from app.models.cover_letter import CoverLetter
from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.resume import BaseResume, JobVariant

# WHY object not Any: ghostwriter_output keys are accessed via .get() with
# defaults, and each code path explicitly extracts and validates the types it
# needs. The top-level dict is typed as dict[str, object] for safety, matching
# the onboarding_workflow.py pattern.

_MAX_STORIES_USED = 5
"""Safety bound on achievement stories referenced in a cover letter."""


# =============================================================================
# Result Dataclasses
# =============================================================================


@dataclass(frozen=True)
class DraftMaterialsResult:
    """Summary of entities created during draft persistence."""

    job_variant_id: uuid.UUID
    cover_letter_id: uuid.UUID | None
    tailoring_applied: bool


@dataclass(frozen=True)
class ApproveMaterialsResult:
    """Summary of approval outcome."""

    job_variant_id: uuid.UUID
    job_variant_status: str
    cover_letter_id: uuid.UUID | None
    cover_letter_status: str | None
    approved_at: datetime


@dataclass(frozen=True)
class CreateApplicationResult:
    """Summary of application creation."""

    application_id: uuid.UUID
    timeline_event_id: uuid.UUID
    status: str


# =============================================================================
# Helpers
# =============================================================================


def _build_job_snapshot(job_posting: JobPosting) -> dict[str, object]:
    """Freeze JobPosting fields into a snapshot dict.

    Args:
        job_posting: The JobPosting to snapshot.

    Returns:
        Dict of frozen fields for Application.job_snapshot.
    """
    first_seen = job_posting.first_seen_date
    return {
        "title": job_posting.job_title,
        "company_name": job_posting.company_name,
        "company_url": job_posting.company_url,
        "description": job_posting.description,
        "requirements": job_posting.requirements,
        "salary_min": job_posting.salary_min,
        "salary_max": job_posting.salary_max,
        "salary_currency": job_posting.salary_currency,
        "location": job_posting.location,
        "work_model": job_posting.work_model,
        "source_url": job_posting.source_url,
        "first_seen_date": first_seen.isoformat() if first_seen else None,
    }


# =============================================================================
# Public API
# =============================================================================


async def persist_draft_materials(
    ghostwriter_output: dict[str, object],
    persona_id: uuid.UUID,
    job_posting_id: uuid.UUID,
    db: AsyncSession,
) -> DraftMaterialsResult:
    """Persist Ghostwriter output as draft database entities.

    Called after Ghostwriter graph completes (before HITL approval).

    - Tailored case (tailoring_needed=True): Draft JobVariant + Draft CoverLetter
    - Pass-through case (tailoring_needed=False): Approved JobVariant + Draft CoverLetter

    Args:
        ghostwriter_output: Dict matching GhostwriterState output fields.
        persona_id: Target persona ID.
        job_posting_id: Target job posting ID.
        db: Database session.

    Returns:
        DraftMaterialsResult with created entity IDs.

    Raises:
        NotFoundError: Persona, JobPosting, or BaseResume not found.
        InvalidStateError: Persona onboarding not complete.
        ConflictError: Active variant already exists for this base+job.
    """
    # --- Validation guards ---
    persona = await db.get(Persona, persona_id)
    if persona is None:
        raise NotFoundError("Persona", str(persona_id))

    if not persona.onboarding_complete:
        raise InvalidStateError(
            "Onboarding must be complete before creating materials."
        )

    job_posting = await db.get(JobPosting, job_posting_id)
    if job_posting is None:
        raise NotFoundError("JobPosting", str(job_posting_id))

    base_resume_id = uuid.UUID(str(ghostwriter_output["selected_base_resume_id"]))
    base_resume = await db.get(BaseResume, base_resume_id)
    if base_resume is None:
        raise NotFoundError("BaseResume", str(base_resume_id))

    # Check for duplicate active variant (not archived)
    existing_result = await db.execute(
        select(JobVariant).where(
            and_(
                JobVariant.base_resume_id == base_resume_id,
                JobVariant.job_posting_id == job_posting_id,
                JobVariant.archived_at.is_(None),
            )
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise ConflictError(
            "DUPLICATE_VARIANT",
            f"Active variant already exists for base resume '{base_resume_id}' "
            f"and job posting '{job_posting_id}'.",
        )

    # --- Create JobVariant ---
    tailoring_needed = bool(ghostwriter_output.get("tailoring_needed", False))
    raw_resume = ghostwriter_output.get("generated_resume", {})
    generated_resume = raw_resume if isinstance(raw_resume, dict) else {}
    now = datetime.now(UTC)

    variant = JobVariant(
        base_resume_id=base_resume_id,
        job_posting_id=job_posting_id,
        summary=str(generated_resume.get("content", "")),
        job_bullet_order=generated_resume.get("bullet_order", {}),
        modifications_description=ghostwriter_output.get("modifications_description"),
    )

    if tailoring_needed:
        variant.status = "Draft"
    else:
        # Pass-through: approve immediately with snapshots
        variant.status = "Approved"
        variant.approved_at = now
        # WHY type: ignore — snapshot_* model fields are typed as dict|None
        # but JSONB columns actually store lists. This is a pre-existing model
        # annotation issue; the runtime values are correct JSON arrays.
        variant.snapshot_included_jobs = base_resume.included_jobs  # type: ignore[assignment]
        variant.snapshot_included_education = base_resume.included_education  # type: ignore[assignment]
        variant.snapshot_included_certifications = base_resume.included_certifications  # type: ignore[assignment]
        variant.snapshot_skills_emphasis = base_resume.skills_emphasis  # type: ignore[assignment]
        variant.snapshot_job_bullet_selections = base_resume.job_bullet_selections

    db.add(variant)
    await db.flush()

    # --- Create CoverLetter (if not skipped) ---
    cover_letter_id: uuid.UUID | None = None
    raw_cl = ghostwriter_output.get("generated_cover_letter")
    generated_cl = raw_cl if isinstance(raw_cl, dict) else None
    skip_cl = ghostwriter_output.get("skip_cover_letter", False)

    if generated_cl is not None and not skip_cl:
        stories_used = list(generated_cl.get("stories_used", []))[:_MAX_STORIES_USED]
        cover_letter = CoverLetter(
            persona_id=persona_id,
            job_posting_id=job_posting_id,
            draft_text=str(generated_cl.get("content", "")),
            agent_reasoning=str(generated_cl.get("reasoning", "")),
            achievement_stories_used=stories_used,
            status="Draft",
        )
        db.add(cover_letter)
        await db.flush()
        cover_letter_id = cover_letter.id

    await db.commit()

    return DraftMaterialsResult(
        job_variant_id=variant.id,
        cover_letter_id=cover_letter_id,
        tailoring_applied=tailoring_needed,
    )


async def approve_materials(
    job_variant_id: uuid.UUID,
    cover_letter_id: uuid.UUID | None,
    final_cover_letter_text: str | None,
    db: AsyncSession,
) -> ApproveMaterialsResult:
    """Approve draft materials after user review.

    Updates JobVariant and CoverLetter to Approved status.
    Populates snapshot fields on JobVariant from its BaseResume.
    Handles already-approved variant gracefully (pass-through case).

    Args:
        job_variant_id: The JobVariant to approve.
        cover_letter_id: The CoverLetter to approve (None if no cover letter).
        final_cover_letter_text: User-edited text (None promotes draft_text).
        db: Database session.

    Returns:
        ApproveMaterialsResult with approval details.

    Raises:
        NotFoundError: JobVariant or CoverLetter not found.
        InvalidStateError: Entity is archived.
    """
    now = datetime.now(UTC)

    # --- Approve JobVariant ---
    variant = await db.get(JobVariant, job_variant_id)
    if variant is None:
        raise NotFoundError("JobVariant", str(job_variant_id))

    if variant.is_archived:
        raise InvalidStateError("Cannot approve an archived variant.")

    if variant.status != "Approved":
        # Populate snapshots from BaseResume
        base_resume = await db.get(BaseResume, variant.base_resume_id)
        if base_resume is not None:
            variant.snapshot_included_jobs = base_resume.included_jobs  # type: ignore[assignment]
            variant.snapshot_included_education = base_resume.included_education  # type: ignore[assignment]
            variant.snapshot_included_certifications = (
                base_resume.included_certifications  # type: ignore[assignment]
            )
            variant.snapshot_skills_emphasis = base_resume.skills_emphasis  # type: ignore[assignment]
            variant.snapshot_job_bullet_selections = base_resume.job_bullet_selections

        variant.status = "Approved"
        variant.approved_at = now

    # --- Approve CoverLetter (if provided) ---
    cl_status: str | None = None
    cl_id: uuid.UUID | None = None

    if cover_letter_id is not None:
        cover_letter = await db.get(CoverLetter, cover_letter_id)
        if cover_letter is None:
            raise NotFoundError("CoverLetter", str(cover_letter_id))

        if cover_letter.is_archived:
            raise InvalidStateError("Cannot approve an archived cover letter.")

        cover_letter.status = "Approved"
        cover_letter.approved_at = now
        cover_letter.final_text = (
            final_cover_letter_text
            if final_cover_letter_text is not None
            else cover_letter.draft_text
        )
        cl_status = cover_letter.status
        cl_id = cover_letter.id

    await db.commit()

    return ApproveMaterialsResult(
        job_variant_id=variant.id,
        job_variant_status=variant.status,
        cover_letter_id=cl_id,
        cover_letter_status=cl_status,
        approved_at=now,
    )


async def create_application(
    persona_id: uuid.UUID,
    job_posting_id: uuid.UUID,
    job_variant_id: uuid.UUID,
    cover_letter_id: uuid.UUID | None,
    db: AsyncSession,
) -> CreateApplicationResult:
    """Create an Application record when user marks 'Applied'.

    Creates Application with frozen job snapshot, initial TimelineEvent,
    and links CoverLetter.application_id to the new Application.

    Args:
        persona_id: The applying persona.
        job_posting_id: The target job posting.
        job_variant_id: The approved JobVariant.
        cover_letter_id: The approved CoverLetter (None if no cover letter).
        db: Database session.

    Returns:
        CreateApplicationResult with created entity IDs.

    Raises:
        NotFoundError: Persona, JobPosting, or JobVariant not found.
        InvalidStateError: JobVariant or CoverLetter not approved.
        ConflictError: Application already exists for this persona+job.
    """
    # --- Validation guards ---
    persona = await db.get(Persona, persona_id)
    if persona is None:
        raise NotFoundError("Persona", str(persona_id))

    job_posting = await db.get(JobPosting, job_posting_id)
    if job_posting is None:
        raise NotFoundError("JobPosting", str(job_posting_id))

    variant = await db.get(JobVariant, job_variant_id)
    if variant is None:
        raise NotFoundError("JobVariant", str(job_variant_id))

    if variant.status != "Approved":
        raise InvalidStateError(
            f"JobVariant must be Approved before creating application. "
            f"Current status: '{variant.status}'."
        )

    cover_letter: CoverLetter | None = None
    if cover_letter_id is not None:
        cover_letter = await db.get(CoverLetter, cover_letter_id)
        if cover_letter is None:
            raise NotFoundError("CoverLetter", str(cover_letter_id))

        if cover_letter.status != "Approved":
            raise InvalidStateError(
                f"CoverLetter must be Approved before creating application. "
                f"Current status: '{cover_letter.status}'."
            )

    # Check for duplicate application
    existing = await db.execute(
        select(Application).where(
            and_(
                Application.persona_id == persona_id,
                Application.job_posting_id == job_posting_id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(
            "DUPLICATE_APPLICATION",
            f"Application already exists for persona '{persona_id}' "
            f"and job posting '{job_posting_id}'.",
        )

    # --- Create Application ---
    now = datetime.now(UTC)
    job_snapshot = _build_job_snapshot(job_posting)

    application = Application(
        persona_id=persona_id,
        job_posting_id=job_posting_id,
        job_variant_id=job_variant_id,
        cover_letter_id=cover_letter_id,
        job_snapshot=job_snapshot,
        status="Applied",
    )
    db.add(application)
    await db.flush()

    # --- Create TimelineEvent ---
    timeline_event = TimelineEvent(
        application_id=application.id,
        event_type="applied",
        event_date=now,
        description="Application submitted.",
    )
    db.add(timeline_event)
    await db.flush()

    # --- Link CoverLetter to Application ---
    if cover_letter is not None:
        cover_letter.application_id = application.id

    await db.commit()

    return CreateApplicationResult(
        application_id=application.id,
        timeline_event_id=timeline_event.id,
        status="Applied",
    )
