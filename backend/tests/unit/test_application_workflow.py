"""Tests for application workflow service.

REQ-002 §6.2: Application flow — persist Ghostwriter output into
JobVariant, CoverLetter, and Application entities.

Tests verify:
- Draft JobVariant created (tailored or pass-through)
- Draft CoverLetter created from generated content
- Materials approved with snapshot population
- Application created with frozen job snapshot and timeline event
- Validation guards for missing entities, wrong states, duplicates
"""

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, InvalidStateError, NotFoundError
from app.models.application import Application, TimelineEvent
from app.models.cover_letter import CoverLetter
from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.resume import BaseResume, JobVariant
from app.services.application_workflow import (
    ApproveMaterialsResult,
    CreateApplicationResult,
    DraftMaterialsResult,
    _build_job_snapshot,
    approve_materials,
    create_application,
    persist_draft_materials,
)
from tests.conftest import TEST_USER_ID

# Stable test IDs
_PERSONA_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
_JOB_SOURCE_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
_JOB_POSTING_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")
_BASE_RESUME_ID = uuid.UUID("10000000-0000-0000-0000-000000000004")

_MAX_STORIES_USED = 5
"""Safety bound mirroring the service constant."""


# =============================================================================
# Helpers
# =============================================================================


def _make_ghostwriter_output(
    *,
    tailoring_needed: bool = True,
    include_cover_letter: bool = True,
    resume_summary: str = "Tailored summary for Senior Engineer role.",
    resume_bullet_order: dict[str, Any] | None = None,
    modifications_description: str = "Reordered bullets for relevance.",
    cover_letter_text: str = "Dear Hiring Manager, I am excited...",
    cover_letter_reasoning: str = "Matched story to job requirements.",
    stories_used: list[str] | None = None,
    agent_reasoning: str = "Selected base resume for best fit.",
    selected_base_resume_id: str | None = None,
) -> dict[str, Any]:
    """Build a dict matching ghostwriter output output fields.

    Args:
        tailoring_needed: Whether resume tailoring was applied.
        include_cover_letter: Whether to include generated cover letter.
        resume_summary: Tailored resume summary text.
        resume_bullet_order: Custom bullet ordering dict.
        modifications_description: Description of resume modifications.
        cover_letter_text: Generated cover letter text.
        cover_letter_reasoning: Agent reasoning for cover letter.
        stories_used: Achievement story IDs used in cover letter.
        agent_reasoning: Overall agent reasoning.
        selected_base_resume_id: Base resume ID selected by Ghostwriter.

    Returns:
        Dict matching ghostwriter output output fields.
    """
    output: dict[str, Any] = {
        "selected_base_resume_id": selected_base_resume_id or str(_BASE_RESUME_ID),
        "tailoring_needed": tailoring_needed,
        "generated_resume": {
            "content": resume_summary,
            "reasoning": "Best match for job requirements.",
            "stories_used": [],
        },
        "agent_reasoning": agent_reasoning,
    }

    if resume_bullet_order is not None:
        output["generated_resume"]["bullet_order"] = resume_bullet_order

    if tailoring_needed:
        output["modifications_description"] = modifications_description
    else:
        output["modifications_description"] = None

    if include_cover_letter:
        output["generated_cover_letter"] = {
            "content": cover_letter_text,
            "reasoning": cover_letter_reasoning,
            "stories_used": stories_used or ["story-1", "story-2"],
        }
        output["skip_cover_letter"] = False
    else:
        output["generated_cover_letter"] = None
        output["skip_cover_letter"] = True

    return output


async def _setup_approved_materials(
    db_session: AsyncSession,
    scenario: SimpleNamespace,
    *,
    include_cover_letter: bool = True,
) -> DraftMaterialsResult:
    """Create and approve draft materials for application tests.

    Args:
        db_session: Database session.
        scenario: Application scenario namespace with entity IDs.
        include_cover_letter: Whether to include a cover letter.

    Returns:
        DraftMaterialsResult from persist_draft_materials.
    """
    output = _make_ghostwriter_output(
        tailoring_needed=True,
        include_cover_letter=include_cover_letter,
    )
    draft = await persist_draft_materials(
        output, scenario.persona_id, scenario.job_posting_id, db_session
    )
    final_text = "Final cover letter." if include_cover_letter else None
    await approve_materials(
        draft.job_variant_id, draft.cover_letter_id, final_text, db_session
    )
    return draft


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def application_scenario(
    db_session: AsyncSession,
) -> SimpleNamespace:
    """Create User -> Persona (onboarding_complete) -> BaseResume -> JobSource -> JobPosting.

    Returns SimpleNamespace with all entity IDs for test use.
    """
    from app.models import User
    from app.models.job_source import JobSource

    # User
    user = User(id=TEST_USER_ID, email="test@example.com")
    db_session.add(user)
    await db_session.flush()

    # Persona (onboarding complete)
    persona = Persona(
        id=_PERSONA_ID,
        user_id=user.id,
        email="persona@example.com",
        full_name="Test User",
        phone="555-1234",
        home_city="Austin",
        home_state="TX",
        home_country="USA",
        onboarding_complete=True,
    )
    db_session.add(persona)
    await db_session.flush()

    # BaseResume
    base_resume = BaseResume(
        id=_BASE_RESUME_ID,
        persona_id=_PERSONA_ID,
        name="Senior Engineer Resume",
        role_type="Senior Software Engineer",
        summary="Experienced engineer with 6+ years.",
        is_primary=True,
        included_jobs=["job-id-1", "job-id-2"],
        included_education=["edu-id-1"],
        included_certifications=["cert-id-1"],
        skills_emphasis=["skill-id-1", "skill-id-2"],
        job_bullet_selections={"job-id-1": ["bullet-1", "bullet-2"]},
        job_bullet_order={"job-id-1": ["bullet-2", "bullet-1"]},
    )
    db_session.add(base_resume)
    await db_session.flush()

    # JobSource
    source = JobSource(
        id=_JOB_SOURCE_ID,
        source_name="Extension",
        source_type="Extension",
        description="Chrome extension capture",
    )
    db_session.add(source)
    await db_session.flush()

    # JobPosting
    job_posting = JobPosting(
        id=_JOB_POSTING_ID,
        source_id=_JOB_SOURCE_ID,
        job_title="Senior Software Engineer",
        company_name="TechCorp",
        company_url="https://techcorp.example.com",
        description="We are looking for a Senior Software Engineer.",
        requirements="5+ years Python experience.",
        salary_min=120000,
        salary_max=180000,
        salary_currency="USD",
        location="Austin, TX",
        work_model="Remote",
        source_url="https://jobs.example.com/123",
        first_seen_date=date(2026, 1, 15),
        description_hash="abc123hash",
    )
    db_session.add(job_posting)
    await db_session.commit()

    return SimpleNamespace(
        user_id=TEST_USER_ID,
        persona_id=_PERSONA_ID,
        base_resume_id=_BASE_RESUME_ID,
        job_source_id=_JOB_SOURCE_ID,
        job_posting_id=_JOB_POSTING_ID,
    )


# =============================================================================
# persist_draft_materials — Happy Paths
# =============================================================================


class TestPersistDraftMaterials:
    """persist_draft_materials() — create draft JobVariant + CoverLetter."""

    @pytest.mark.asyncio
    async def test_creates_draft_variant_when_tailoring_needed(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Tailored case creates a Draft JobVariant with tailored summary."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        variant = await db_session.get(JobVariant, result.job_variant_id)
        assert variant is not None
        assert variant.status == "Draft"
        assert variant.summary == "Tailored summary for Senior Engineer role."
        assert variant.base_resume_id == _BASE_RESUME_ID
        assert variant.job_posting_id == _JOB_POSTING_ID
        assert variant.modifications_description == "Reordered bullets for relevance."

    @pytest.mark.asyncio
    async def test_creates_approved_variant_when_pass_through(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Pass-through case creates an Approved JobVariant copying BaseResume content."""
        output = _make_ghostwriter_output(tailoring_needed=False)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        variant = await db_session.get(JobVariant, result.job_variant_id)
        assert variant is not None
        assert variant.status == "Approved"
        assert variant.approved_at is not None
        assert result.tailoring_applied is False
        # Snapshots populated immediately for pass-through
        assert variant.snapshot_included_jobs is not None
        assert variant.snapshot_skills_emphasis is not None

    @pytest.mark.asyncio
    async def test_creates_draft_cover_letter(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Creates a Draft CoverLetter with generated text and stories."""
        output = _make_ghostwriter_output(include_cover_letter=True)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        assert result.cover_letter_id is not None
        cl = await db_session.get(CoverLetter, result.cover_letter_id)
        assert cl is not None
        assert cl.status == "Draft"
        assert cl.draft_text == "Dear Hiring Manager, I am excited..."
        assert cl.agent_reasoning == "Matched story to job requirements."
        assert cl.persona_id == _PERSONA_ID
        assert cl.job_posting_id == _JOB_POSTING_ID

    @pytest.mark.asyncio
    async def test_no_cover_letter_when_skipped(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """skip_cover_letter=True results in no CoverLetter created."""
        output = _make_ghostwriter_output(include_cover_letter=False)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        assert result.cover_letter_id is None

    @pytest.mark.asyncio
    async def test_result_shape(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Returns DraftMaterialsResult with correct fields."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        assert isinstance(result, DraftMaterialsResult)
        assert result.job_variant_id is not None
        assert result.cover_letter_id is not None
        assert result.tailoring_applied is True

    @pytest.mark.asyncio
    async def test_stories_used_truncated(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """achievement_stories_used truncated to safety limit."""
        many_stories = [f"story-{i}" for i in range(_MAX_STORIES_USED + 5)]
        output = _make_ghostwriter_output(stories_used=many_stories)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        cl = await db_session.get(CoverLetter, result.cover_letter_id)
        assert cl is not None
        assert len(cl.achievement_stories_used) == _MAX_STORIES_USED

    @pytest.mark.asyncio
    async def test_variant_bullet_order_from_generated_resume(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """JobVariant.job_bullet_order set from generated resume bullet_order."""
        custom_order = {"job-id-1": ["bullet-3", "bullet-1"]}
        output = _make_ghostwriter_output(resume_bullet_order=custom_order)
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        variant = await db_session.get(JobVariant, result.job_variant_id)
        assert variant is not None
        assert variant.job_bullet_order == custom_order


# =============================================================================
# persist_draft_materials — Guards
# =============================================================================


class TestPersistDraftMaterialsGuards:
    """Error cases for persist_draft_materials()."""

    @pytest.mark.asyncio
    async def test_missing_persona_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,  # noqa: ARG002
    ) -> None:
        """Non-existent persona_id raises NotFoundError."""
        output = _make_ghostwriter_output()
        with pytest.raises(NotFoundError):
            await persist_draft_materials(
                output, uuid.uuid4(), _JOB_POSTING_ID, db_session
            )

    @pytest.mark.asyncio
    async def test_incomplete_onboarding_raises_invalid_state(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Persona without completed onboarding raises InvalidStateError."""
        # Set onboarding_complete to False
        persona = await db_session.get(Persona, application_scenario.persona_id)
        assert persona is not None
        persona.onboarding_complete = False
        await db_session.flush()

        output = _make_ghostwriter_output()
        with pytest.raises(InvalidStateError):
            await persist_draft_materials(
                output,
                application_scenario.persona_id,
                application_scenario.job_posting_id,
                db_session,
            )

    @pytest.mark.asyncio
    async def test_missing_job_posting_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,  # noqa: ARG002
    ) -> None:
        """Non-existent job_posting_id raises NotFoundError."""
        output = _make_ghostwriter_output()
        with pytest.raises(NotFoundError):
            await persist_draft_materials(output, _PERSONA_ID, uuid.uuid4(), db_session)

    @pytest.mark.asyncio
    async def test_missing_base_resume_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,  # noqa: ARG002
    ) -> None:
        """Non-existent selected_base_resume_id raises NotFoundError."""
        output = _make_ghostwriter_output(selected_base_resume_id=str(uuid.uuid4()))
        with pytest.raises(NotFoundError):
            await persist_draft_materials(
                output, _PERSONA_ID, _JOB_POSTING_ID, db_session
            )

    @pytest.mark.asyncio
    async def test_duplicate_active_variant_raises_conflict(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Creating a second active variant for same base+job raises ConflictError."""
        output = _make_ghostwriter_output()
        await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        # Attempt to create another
        output2 = _make_ghostwriter_output()
        with pytest.raises(ConflictError):
            await persist_draft_materials(
                output2,
                application_scenario.persona_id,
                application_scenario.job_posting_id,
                db_session,
            )

    @pytest.mark.asyncio
    async def test_archived_variant_does_not_block_new_draft(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """An archived variant for same base+job does NOT block a new draft."""
        output = _make_ghostwriter_output()
        result = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        # Archive the first variant
        variant = await db_session.get(JobVariant, result.job_variant_id)
        assert variant is not None
        variant.archived_at = datetime.now(UTC)
        await db_session.flush()

        # Creating a new one should succeed
        output2 = _make_ghostwriter_output()
        result2 = await persist_draft_materials(
            output2,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )
        assert result2.job_variant_id != result.job_variant_id


# =============================================================================
# approve_materials — Happy Paths
# =============================================================================


class TestApproveMaterials:
    """approve_materials() — approve JobVariant + CoverLetter."""

    @pytest.mark.asyncio
    async def test_approves_variant_and_cover_letter(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Approves both variant and cover letter, setting statuses."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        result = await approve_materials(
            draft.job_variant_id, draft.cover_letter_id, None, db_session
        )

        assert isinstance(result, ApproveMaterialsResult)
        assert result.job_variant_status == "Approved"
        assert result.cover_letter_status == "Approved"
        assert result.approved_at is not None

    @pytest.mark.asyncio
    async def test_snapshot_fields_populated_on_approval(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """JobVariant snapshot fields copied from BaseResume on approval."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        await approve_materials(
            draft.job_variant_id, draft.cover_letter_id, None, db_session
        )

        variant = await db_session.get(JobVariant, draft.job_variant_id)
        assert variant is not None
        assert variant.snapshot_included_jobs == ["job-id-1", "job-id-2"]
        assert variant.snapshot_included_education == ["edu-id-1"]
        assert variant.snapshot_included_certifications == ["cert-id-1"]
        assert variant.snapshot_skills_emphasis == ["skill-id-1", "skill-id-2"]
        assert variant.snapshot_job_bullet_selections == {
            "job-id-1": ["bullet-1", "bullet-2"]
        }

    @pytest.mark.asyncio
    async def test_draft_text_promoted_to_final_when_no_edits(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """When final_cover_letter_text is None, draft_text promoted to final_text."""
        output = _make_ghostwriter_output()
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        await approve_materials(
            draft.job_variant_id, draft.cover_letter_id, None, db_session
        )

        cl = await db_session.get(CoverLetter, draft.cover_letter_id)
        assert cl is not None
        assert cl.final_text == cl.draft_text

    @pytest.mark.asyncio
    async def test_custom_final_text_overrides_draft(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """When final_cover_letter_text provided, it overrides draft_text."""
        output = _make_ghostwriter_output()
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        custom_text = "My custom edited cover letter."
        await approve_materials(
            draft.job_variant_id, draft.cover_letter_id, custom_text, db_session
        )

        cl = await db_session.get(CoverLetter, draft.cover_letter_id)
        assert cl is not None
        assert cl.final_text == custom_text

    @pytest.mark.asyncio
    async def test_approve_without_cover_letter(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Approving with cover_letter_id=None only approves the variant."""
        output = _make_ghostwriter_output(include_cover_letter=False)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        result = await approve_materials(draft.job_variant_id, None, None, db_session)

        assert result.cover_letter_id is None
        assert result.cover_letter_status is None
        assert result.job_variant_status == "Approved"

    @pytest.mark.asyncio
    async def test_already_approved_variant_is_idempotent(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Pass-through variant (already Approved) is handled gracefully."""
        output = _make_ghostwriter_output(tailoring_needed=False)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        # Variant is already Approved from pass-through
        result = await approve_materials(
            draft.job_variant_id, draft.cover_letter_id, None, db_session
        )

        assert result.job_variant_status == "Approved"

    @pytest.mark.asyncio
    async def test_approved_at_timestamp_set(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """approved_at timestamp set on both variant and cover letter."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        before = datetime.now(UTC)
        result = await approve_materials(
            draft.job_variant_id, draft.cover_letter_id, None, db_session
        )
        after = datetime.now(UTC)

        assert result.approved_at is not None
        assert before <= result.approved_at <= after


# =============================================================================
# approve_materials — Guards
# =============================================================================


class TestApproveMaterialsGuards:
    """Error cases for approve_materials()."""

    @pytest.mark.asyncio
    async def test_missing_variant_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,  # noqa: ARG002
    ) -> None:
        """Non-existent job_variant_id raises NotFoundError."""
        with pytest.raises(NotFoundError):
            await approve_materials(uuid.uuid4(), None, None, db_session)

    @pytest.mark.asyncio
    async def test_missing_cover_letter_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Non-existent cover_letter_id raises NotFoundError."""
        output = _make_ghostwriter_output(include_cover_letter=False)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        with pytest.raises(NotFoundError):
            await approve_materials(
                draft.job_variant_id, uuid.uuid4(), None, db_session
            )

    @pytest.mark.asyncio
    async def test_archived_variant_raises_invalid_state(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Archived variant cannot be approved."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        # Archive the variant
        variant = await db_session.get(JobVariant, draft.job_variant_id)
        assert variant is not None
        variant.archived_at = datetime.now(UTC)
        await db_session.flush()

        with pytest.raises(InvalidStateError):
            await approve_materials(
                draft.job_variant_id, draft.cover_letter_id, None, db_session
            )

    @pytest.mark.asyncio
    async def test_archived_cover_letter_raises_invalid_state(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Archived cover letter cannot be approved."""
        output = _make_ghostwriter_output()
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )

        # Archive the cover letter
        cl = await db_session.get(CoverLetter, draft.cover_letter_id)
        assert cl is not None
        cl.archived_at = datetime.now(UTC)
        await db_session.flush()

        with pytest.raises(InvalidStateError):
            await approve_materials(
                draft.job_variant_id, draft.cover_letter_id, None, db_session
            )


# =============================================================================
# create_application — Happy Paths
# =============================================================================


class TestCreateApplication:
    """create_application() — create Application + TimelineEvent."""

    @pytest.mark.asyncio
    async def test_creates_application_record(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Creates an Application with Applied status."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        assert isinstance(result, CreateApplicationResult)
        assert result.status == "Applied"

        app = await db_session.get(Application, result.application_id)
        assert app is not None
        assert app.persona_id == _PERSONA_ID
        assert app.job_posting_id == _JOB_POSTING_ID
        assert app.job_variant_id == draft.job_variant_id
        assert app.cover_letter_id == draft.cover_letter_id

    @pytest.mark.asyncio
    async def test_creates_timeline_event(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Creates initial TimelineEvent with event_type='applied'."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        assert result.timeline_event_id is not None
        event = await db_session.get(TimelineEvent, result.timeline_event_id)
        assert event is not None
        assert event.event_type == "applied"
        assert event.application_id == result.application_id

    @pytest.mark.asyncio
    async def test_job_snapshot_frozen(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Application.job_snapshot contains frozen JobPosting fields."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        app = await db_session.get(Application, result.application_id)
        assert app is not None
        snapshot = app.job_snapshot
        assert snapshot["title"] == "Senior Software Engineer"
        assert snapshot["company_name"] == "TechCorp"
        assert snapshot["salary_min"] == 120000
        assert snapshot["salary_max"] == 180000
        assert snapshot["work_model"] == "Remote"

    @pytest.mark.asyncio
    async def test_links_cover_letter_to_application(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """CoverLetter.application_id linked to new Application."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        cl = await db_session.get(CoverLetter, draft.cover_letter_id)
        assert cl is not None
        assert cl.application_id == result.application_id

    @pytest.mark.asyncio
    async def test_creates_application_without_cover_letter(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Application created with cover_letter_id=None when no cover letter."""
        draft = await _setup_approved_materials(
            db_session, application_scenario, include_cover_letter=False
        )

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            None,
            db_session,
        )

        app = await db_session.get(Application, result.application_id)
        assert app is not None
        assert app.cover_letter_id is None

    @pytest.mark.asyncio
    async def test_result_shape(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Returns CreateApplicationResult with expected fields."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        assert isinstance(result, CreateApplicationResult)
        assert result.application_id is not None
        assert result.timeline_event_id is not None
        assert result.status == "Applied"

    @pytest.mark.asyncio
    async def test_application_applied_at_timestamp_set(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Application.applied_at is set to approximately now."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        result = await create_application(
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        app = await db_session.get(Application, result.application_id)
        assert app is not None
        assert app.applied_at is not None
        # applied_at set by server_default, so just verify it exists
        assert app.applied_at.tzinfo is not None


# =============================================================================
# create_application — Guards
# =============================================================================


class TestCreateApplicationGuards:
    """Error cases for create_application()."""

    @pytest.mark.asyncio
    async def test_missing_persona_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Non-existent persona_id raises NotFoundError."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        with pytest.raises(NotFoundError):
            await create_application(
                uuid.uuid4(),
                _JOB_POSTING_ID,
                draft.job_variant_id,
                draft.cover_letter_id,
                db_session,
            )

    @pytest.mark.asyncio
    async def test_missing_job_posting_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Non-existent job_posting_id raises NotFoundError."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        with pytest.raises(NotFoundError):
            await create_application(
                _PERSONA_ID,
                uuid.uuid4(),
                draft.job_variant_id,
                draft.cover_letter_id,
                db_session,
            )

    @pytest.mark.asyncio
    async def test_missing_variant_raises_not_found(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,  # noqa: ARG002
    ) -> None:
        """Non-existent job_variant_id raises NotFoundError."""
        with pytest.raises(NotFoundError):
            await create_application(
                _PERSONA_ID, _JOB_POSTING_ID, uuid.uuid4(), None, db_session
            )

    @pytest.mark.asyncio
    async def test_unapproved_variant_raises_invalid_state(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Draft (unapproved) variant raises InvalidStateError."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )
        # Don't approve — variant stays Draft

        with pytest.raises(InvalidStateError):
            await create_application(
                _PERSONA_ID,
                _JOB_POSTING_ID,
                draft.job_variant_id,
                draft.cover_letter_id,
                db_session,
            )

    @pytest.mark.asyncio
    async def test_unapproved_cover_letter_raises_invalid_state(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Draft (unapproved) cover letter raises InvalidStateError."""
        output = _make_ghostwriter_output(tailoring_needed=True)
        draft = await persist_draft_materials(
            output,
            application_scenario.persona_id,
            application_scenario.job_posting_id,
            db_session,
        )
        # Approve variant only, not cover letter
        variant = await db_session.get(JobVariant, draft.job_variant_id)
        assert variant is not None
        variant.status = "Approved"
        variant.approved_at = datetime.now(UTC)
        # Copy snapshots from base resume
        base = await db_session.get(BaseResume, _BASE_RESUME_ID)
        assert base is not None
        variant.snapshot_included_jobs = base.included_jobs
        variant.snapshot_included_education = base.included_education
        variant.snapshot_included_certifications = base.included_certifications
        variant.snapshot_skills_emphasis = base.skills_emphasis
        variant.snapshot_job_bullet_selections = base.job_bullet_selections
        await db_session.flush()

        with pytest.raises(InvalidStateError):
            await create_application(
                _PERSONA_ID,
                _JOB_POSTING_ID,
                draft.job_variant_id,
                draft.cover_letter_id,
                db_session,
            )

    @pytest.mark.asyncio
    async def test_duplicate_application_raises_conflict(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Creating application twice for same persona+job raises ConflictError."""
        draft = await _setup_approved_materials(db_session, application_scenario)

        await create_application(
            _PERSONA_ID,
            _JOB_POSTING_ID,
            draft.job_variant_id,
            draft.cover_letter_id,
            db_session,
        )

        with pytest.raises(ConflictError):
            await create_application(
                _PERSONA_ID,
                _JOB_POSTING_ID,
                draft.job_variant_id,
                draft.cover_letter_id,
                db_session,
            )


# =============================================================================
# _build_job_snapshot
# =============================================================================


class TestBuildJobSnapshot:
    """_build_job_snapshot() — freeze JobPosting fields."""

    @pytest.mark.asyncio
    async def test_snapshot_contains_expected_fields(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Snapshot contains all required fields from JobPosting."""
        job = await db_session.get(JobPosting, application_scenario.job_posting_id)
        assert job is not None
        snapshot = _build_job_snapshot(job)

        expected_keys = {
            "title",
            "company_name",
            "company_url",
            "description",
            "requirements",
            "salary_min",
            "salary_max",
            "salary_currency",
            "location",
            "work_model",
            "source_url",
            "first_seen_date",
        }
        assert set(snapshot.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_snapshot_values_match_job_posting(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Snapshot values match the source JobPosting."""
        job = await db_session.get(JobPosting, application_scenario.job_posting_id)
        assert job is not None
        snapshot = _build_job_snapshot(job)

        assert snapshot["title"] == "Senior Software Engineer"
        assert snapshot["company_name"] == "TechCorp"
        assert snapshot["company_url"] == "https://techcorp.example.com"
        assert snapshot["salary_min"] == 120000
        assert snapshot["salary_max"] == 180000
        assert snapshot["salary_currency"] == "USD"
        assert snapshot["location"] == "Austin, TX"
        assert snapshot["work_model"] == "Remote"

    @pytest.mark.asyncio
    async def test_snapshot_handles_nullable_fields(
        self,
        db_session: AsyncSession,
        application_scenario: SimpleNamespace,
    ) -> None:
        """Nullable fields appear as None in snapshot."""
        job = await db_session.get(JobPosting, application_scenario.job_posting_id)
        assert job is not None
        # Clear nullable fields
        job.company_url = None
        job.requirements = None
        job.salary_min = None
        job.salary_max = None
        job.salary_currency = None
        job.location = None
        job.work_model = None
        job.source_url = None
        await db_session.flush()

        snapshot = _build_job_snapshot(job)
        assert snapshot["company_url"] is None
        assert snapshot["requirements"] is None
        assert snapshot["salary_min"] is None
        assert snapshot["salary_max"] is None
