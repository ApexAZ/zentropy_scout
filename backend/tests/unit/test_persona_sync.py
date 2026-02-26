"""Tests for persona → base resume sync service.

REQ-002 §6.3: When user adds new items to Persona, Base Resumes need
to stay current via a flag-for-review mechanism.

Tests cover:
1. raise_change_flag — creates PersonaChangeFlag when persona data changes
2. resolve_change_flag — applies resolution to BaseResumes
3. get_pending_flags — retrieves pending flags for a persona
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError, ValidationError
from app.models.persona import Persona
from app.models.persona_content import Bullet, WorkHistory
from app.models.resume import BaseResume
from app.services.persona_sync import (
    ResolveFlagResult,
    get_pending_flags,
    raise_change_flag,
    resolve_change_flag,
)

# =============================================================================
# Fixtures
# =============================================================================

_PERSONA_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_USER_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000099")
_RESUME_A_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
_RESUME_B_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
_JOB_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
_BULLET_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000001")
_SKILL_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")
_EDUCATION_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000002")
_CERT_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000003")


@pytest_asyncio.fixture
async def sync_persona(db_session: AsyncSession):
    """Create a Persona with onboarding complete for sync tests."""
    from app.models import User

    user = User(id=_USER_ID, email="sync@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        id=_PERSONA_ID,
        user_id=_USER_ID,
        email="sync@example.com",
        full_name="Sync User",
        phone="555-9999",
        home_city="Test City",
        home_state="TS",
        home_country="USA",
        onboarding_complete=True,
    )
    db_session.add(persona)
    await db_session.commit()
    return persona


@pytest_asyncio.fixture
async def two_resumes(
    db_session: AsyncSession,
    sync_persona,  # noqa: ARG001 -ensures persona exists
):
    """Create two active BaseResumes with a job included."""
    resume_a = BaseResume(
        id=_RESUME_A_ID,
        persona_id=_PERSONA_ID,
        name="Backend Resume",
        role_type="Backend Engineer",
        summary="Backend engineer resume.",
        included_jobs=[str(_JOB_ID)],
        skills_emphasis=[],
        included_education=[],
        included_certifications=[],
        job_bullet_selections={str(_JOB_ID): []},
        job_bullet_order={},
        status="Active",
    )
    resume_b = BaseResume(
        id=_RESUME_B_ID,
        persona_id=_PERSONA_ID,
        name="Frontend Resume",
        role_type="Frontend Engineer",
        summary="Frontend engineer resume.",
        included_jobs=[str(_JOB_ID)],
        skills_emphasis=[],
        included_education=[],
        included_certifications=[],
        job_bullet_selections={str(_JOB_ID): []},
        job_bullet_order={},
        status="Active",
    )
    db_session.add_all([resume_a, resume_b])
    await db_session.commit()
    return resume_a, resume_b


@pytest_asyncio.fixture
async def work_history_with_bullet(
    db_session: AsyncSession,
    sync_persona,  # noqa: ARG001 -ensures persona exists
):
    """Create a WorkHistory entry with a Bullet for bullet_added tests."""
    from datetime import date

    job = WorkHistory(
        id=_JOB_ID,
        persona_id=_PERSONA_ID,
        company_name="Test Corp",
        job_title="Engineer",
        start_date=date(2020, 1, 1),
        location="Remote",
        work_model="Remote",
    )
    db_session.add(job)
    await db_session.flush()

    bullet = Bullet(
        id=_BULLET_ID,
        work_history_id=_JOB_ID,
        text="Increased throughput by 40%",
    )
    db_session.add(bullet)
    await db_session.commit()
    return job, bullet


# =============================================================================
# TestRaiseChangeFlag
# =============================================================================


class TestRaiseChangeFlag:
    """Tests for raise_change_flag — creating PersonaChangeFlags."""

    async def test_creates_flag_with_correct_fields(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Flag is created with all provided fields."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Added skill: Kubernetes",
        )

        assert flag.persona_id == _PERSONA_ID
        assert flag.change_type == "skill_added"
        assert flag.item_id == _SKILL_ID
        assert flag.item_description == "Added skill: Kubernetes"

    async def test_flag_defaults_to_pending(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """New flags default to Pending status."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="job_added",
            item_id=_JOB_ID,
            item_description="Added job: Engineer at TestCorp",
        )

        assert flag.status == "Pending"
        assert flag.resolution is None
        assert flag.resolved_at is None

    async def test_flag_has_created_at(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Flag has a created_at timestamp."""
        before = datetime.now(UTC)
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Added skill: Docker",
        )

        assert flag.created_at is not None
        assert flag.created_at >= before

    async def test_persona_not_found(self, db_session: AsyncSession):
        """Raises NotFoundError for nonexistent persona."""
        missing_id = uuid.uuid4()
        with pytest.raises(NotFoundError, match="Persona"):
            await raise_change_flag(
                db=db_session,
                persona_id=missing_id,
                change_type="skill_added",
                item_id=_SKILL_ID,
                item_description="Added skill: Go",
            )

    async def test_invalid_change_type(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Raises ValidationError for unknown change_type."""
        with pytest.raises(ValidationError):
            await raise_change_flag(
                db=db_session,
                persona_id=_PERSONA_ID,
                change_type="invalid_type",
                item_id=_SKILL_ID,
                item_description="Bad type",
            )

    async def test_all_valid_change_types(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """All five change types are accepted."""
        valid_types = [
            "job_added",
            "bullet_added",
            "skill_added",
            "education_added",
            "certification_added",
        ]
        for change_type in valid_types:
            flag = await raise_change_flag(
                db=db_session,
                persona_id=_PERSONA_ID,
                change_type=change_type,
                item_id=uuid.uuid4(),
                item_description=f"Test {change_type}",
            )
            assert flag.change_type == change_type


# =============================================================================
# TestResolveFlagSkipped
# =============================================================================


class TestResolveFlagSkipped:
    """Tests for resolve_change_flag with resolution='skipped'."""

    async def test_marks_flag_resolved(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Skipped resolution marks flag as Resolved without updating resumes."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Added skill: Kubernetes",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="skipped",
        )

        assert isinstance(result, ResolveFlagResult)
        assert result.resolution == "skipped"
        assert result.resumes_updated == 0

    async def test_flag_fields_updated(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Flag status, resolution, and resolved_at are set."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Skipped skill",
        )

        await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="skipped",
        )

        await db_session.refresh(flag)
        assert flag.status == "Resolved"
        assert flag.resolution == "skipped"
        assert flag.resolved_at is not None

    async def test_no_resume_changes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """BaseResumes are unchanged after skipped resolution."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Skipped",
        )

        await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="skipped",
        )

        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        assert resume_a.skills_emphasis == []


# =============================================================================
# TestResolveFlagAddedToAll
# =============================================================================


class TestResolveFlagAddedToAll:
    """Tests for resolve_change_flag with resolution='added_to_all'."""

    async def test_job_added_updates_all_resumes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """job_added appends to included_jobs on all active BaseResumes."""
        new_job_id = uuid.uuid4()
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="job_added",
            item_id=new_job_id,
            item_description="Added job: Senior Engineer",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        assert result.resumes_updated == 2

        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        resume_b = await db_session.get(BaseResume, _RESUME_B_ID)
        assert str(new_job_id) in resume_a.included_jobs
        assert str(new_job_id) in resume_b.included_jobs

    async def test_skill_added_updates_all_resumes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """skill_added appends to skills_emphasis on all active BaseResumes."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Added skill: Kubernetes",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        assert result.resumes_updated == 2

        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        assert str(_SKILL_ID) in resume_a.skills_emphasis

    async def test_education_added_updates_all_resumes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """education_added appends to included_education on all active BaseResumes."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="education_added",
            item_id=_EDUCATION_ID,
            item_description="Added education: MS CS",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        assert result.resumes_updated == 2

        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        assert str(_EDUCATION_ID) in resume_a.included_education

    async def test_certification_added_updates_all_resumes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """certification_added appends to included_certifications."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="certification_added",
            item_id=_CERT_ID,
            item_description="Added cert: AWS Solutions Architect",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        assert result.resumes_updated == 2

        resume_b = await db_session.get(BaseResume, _RESUME_B_ID)
        assert str(_CERT_ID) in resume_b.included_certifications

    async def test_bullet_added_updates_job_bullet_selections(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        work_history_with_bullet,  # noqa: ARG002 -ensures job+bullet exist
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """bullet_added appends bullet to job_bullet_selections for resumes that include the job."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="bullet_added",
            item_id=_BULLET_ID,
            item_description="New accomplishment at Test Corp",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        assert result.resumes_updated == 2

        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        job_key = str(_JOB_ID)
        assert job_key in resume_a.job_bullet_selections
        assert str(_BULLET_ID) in resume_a.job_bullet_selections[job_key]

    async def test_bullet_added_skips_resumes_without_job(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        work_history_with_bullet,  # noqa: ARG002 -ensures job+bullet exist
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """bullet_added only updates resumes that include the bullet's parent job."""
        # Remove the job from resume_b
        resume_b = await db_session.get(BaseResume, _RESUME_B_ID)
        resume_b.included_jobs = []
        resume_b.job_bullet_selections = {}
        await db_session.commit()

        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="bullet_added",
            item_id=_BULLET_ID,
            item_description="Bullet for job not in resume_b",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        # Only resume_a includes the job
        assert result.resumes_updated == 1

        resume_b_refreshed = await db_session.get(BaseResume, _RESUME_B_ID)
        assert resume_b_refreshed.job_bullet_selections == {}

    async def test_skips_archived_resumes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Archived BaseResumes are not updated."""
        resume_b = await db_session.get(BaseResume, _RESUME_B_ID)
        resume_b.status = "Archived"
        resume_b.archived_at = datetime.now(UTC)
        await db_session.commit()

        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Skill for active only",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        assert result.resumes_updated == 1

        resume_b_refreshed = await db_session.get(BaseResume, _RESUME_B_ID)
        assert resume_b_refreshed.skills_emphasis == []

    async def test_idempotent_no_duplicate_entries(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Adding the same item twice does not create duplicates in the list."""
        # Pre-add the skill to resume_a
        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        resume_a.skills_emphasis = [str(_SKILL_ID)]
        await db_session.commit()

        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Duplicate skill",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_all",
        )

        # resume_a already had it (no update), resume_b gets it (1 update)
        assert result.resumes_updated == 1

        resume_a_refreshed = await db_session.get(BaseResume, _RESUME_A_ID)
        assert resume_a_refreshed.skills_emphasis.count(str(_SKILL_ID)) == 1


# =============================================================================
# TestResolveFlagAddedToSome
# =============================================================================


class TestResolveFlagAddedToSome:
    """Tests for resolve_change_flag with resolution='added_to_some'."""

    async def test_updates_only_specified_resumes(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Only target_resume_ids are updated."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Skill for one resume only",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_some",
            target_resume_ids=[_RESUME_A_ID],
        )

        assert result.resumes_updated == 1

        resume_a = await db_session.get(BaseResume, _RESUME_A_ID)
        resume_b = await db_session.get(BaseResume, _RESUME_B_ID)
        assert str(_SKILL_ID) in resume_a.skills_emphasis
        assert str(_SKILL_ID) not in resume_b.skills_emphasis

    async def test_requires_target_resume_ids(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Raises ValidationError when target_resume_ids not provided for added_to_some."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Missing targets",
        )

        with pytest.raises(ValidationError, match="target_resume_ids"):
            await resolve_change_flag(
                db=db_session,
                flag_id=flag.id,
                resolution="added_to_some",
            )

    async def test_ignores_nonexistent_resume_ids(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Nonexistent resume IDs in target list are silently ignored."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="With bad ID",
        )

        result = await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="added_to_some",
            target_resume_ids=[_RESUME_A_ID, uuid.uuid4()],
        )

        # Only resume_a was updated (the nonexistent one is ignored)
        assert result.resumes_updated == 1


# =============================================================================
# TestResolveFlagGuards
# =============================================================================


class TestResolveFlagGuards:
    """Error cases for resolve_change_flag."""

    async def test_flag_not_found(self, db_session: AsyncSession):
        """Raises NotFoundError for nonexistent flag."""
        with pytest.raises(NotFoundError, match="PersonaChangeFlag"):
            await resolve_change_flag(
                db=db_session,
                flag_id=uuid.uuid4(),
                resolution="skipped",
            )

    async def test_already_resolved(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Raises InvalidStateError for already-resolved flag."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Already resolved",
        )

        await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="skipped",
        )

        with pytest.raises(InvalidStateError, match="already resolved"):
            await resolve_change_flag(
                db=db_session,
                flag_id=flag.id,
                resolution="skipped",
            )

    async def test_invalid_resolution(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Raises ValidationError for invalid resolution value."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=_SKILL_ID,
            item_description="Bad resolution",
        )

        with pytest.raises(ValidationError):
            await resolve_change_flag(
                db=db_session,
                flag_id=flag.id,
                resolution="invalid_resolution",
            )

    async def test_bullet_not_found(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
        two_resumes,  # noqa: ARG002 -ensures resumes exist
    ):
        """Raises NotFoundError when bullet_added references missing bullet."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="bullet_added",
            item_id=uuid.uuid4(),  # nonexistent bullet
            item_description="Ghost bullet",
        )

        with pytest.raises(NotFoundError, match="Bullet"):
            await resolve_change_flag(
                db=db_session,
                flag_id=flag.id,
                resolution="added_to_all",
            )


# =============================================================================
# TestGetPendingFlags
# =============================================================================


class TestGetPendingFlags:
    """Tests for get_pending_flags."""

    async def test_returns_pending_flags(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Returns all Pending flags for the persona."""
        await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=uuid.uuid4(),
            item_description="Skill 1",
        )
        await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="job_added",
            item_id=uuid.uuid4(),
            item_description="Job 1",
        )

        flags = await get_pending_flags(db=db_session, persona_id=_PERSONA_ID)
        assert len(flags) == 2
        assert all(f.status == "Pending" for f in flags)

    async def test_excludes_resolved_flags(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Resolved flags are not returned."""
        flag = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=uuid.uuid4(),
            item_description="Will resolve",
        )
        await resolve_change_flag(
            db=db_session,
            flag_id=flag.id,
            resolution="skipped",
        )
        await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="job_added",
            item_id=uuid.uuid4(),
            item_description="Still pending",
        )

        flags = await get_pending_flags(db=db_session, persona_id=_PERSONA_ID)
        assert len(flags) == 1
        assert flags[0].item_description == "Still pending"

    async def test_returns_empty_if_none(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Returns empty list when no pending flags exist."""
        flags = await get_pending_flags(db=db_session, persona_id=_PERSONA_ID)
        assert flags == []

    async def test_sorted_by_created_at(
        self,
        db_session: AsyncSession,
        sync_persona,  # noqa: ARG002 -ensures persona exists
    ):
        """Flags are returned sorted by created_at ascending."""
        flag1 = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="skill_added",
            item_id=uuid.uuid4(),
            item_description="First",
        )
        flag2 = await raise_change_flag(
            db=db_session,
            persona_id=_PERSONA_ID,
            change_type="job_added",
            item_id=uuid.uuid4(),
            item_description="Second",
        )

        flags = await get_pending_flags(db=db_session, persona_id=_PERSONA_ID)
        assert len(flags) == 2
        assert flags[0].id == flag1.id
        assert flags[1].id == flag2.id
