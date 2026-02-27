"""Tests for onboarding workflow service.

REQ-002 §6.1: Onboarding flow — persist gathered data from onboarding agent
into Persona, Tier 2 content entities, and BaseResume entries.

Tests verify:
- Persona contact fields updated from basic_info
- Persona preferences updated from non_negotiables and growth_targets
- WorkHistory + Bullet entries created from work_history
- Skill entries created from skills
- Education entries created (or skipped)
- Certification entries created (or skipped)
- AchievementStory entries created from achievement_stories
- VoiceProfile created from voice_profile
- BaseResume entries created from base_resume_setup
- persona.onboarding_complete set to True
- Idempotency guard: repeated calls raise InvalidStateError
- Not-found guard: non-existent persona raises NotFoundError
"""

import uuid
from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError
from app.models.persona import Persona
from app.models.persona_content import (
    AchievementStory,
    Bullet,
    Certification,
    Education,
    Skill,
    WorkHistory,
)
from app.models.persona_settings import VoiceProfile
from app.models.resume import BaseResume
from app.services.onboarding_workflow import finalize_onboarding
from tests.conftest import TEST_PERSONA_ID, TEST_USER_ID


def _make_gathered_data(
    *,
    include_education: bool = True,
    include_certifications: bool = True,
    role_count: int = 1,
) -> dict[str, Any]:
    """Build a complete gathered_data dict matching onboarding agent output.

    Args:
        include_education: If False, marks education as skipped.
        include_certifications: If False, marks certifications as skipped.
        role_count: Number of base resume entries to generate.

    Returns:
        Dict matching the onboarding agent's gathered_data structure.
    """
    data: dict[str, Any] = {
        "basic_info": {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-9876",
            "location": "Austin, TX",
        },
        "work_history": {
            "entries": [
                {
                    "job_title": "Senior Engineer",
                    "company": "Acme Corp",
                    "start_date": "2020-01",
                    "end_date": "2024-06",
                    "bullets": [
                        "Led migration to microservices",
                        "Reduced deployment time by 40%",
                    ],
                },
                {
                    "job_title": "Software Engineer",
                    "company": "StartupCo",
                    "start_date": "2018-03",
                    "end_date": "2020-01",
                    "bullets": ["Built REST API serving 10k RPM"],
                },
            ],
        },
        "skills": {
            "entries": [
                {
                    "skill_name": "Python",
                    "category": "Hard",
                    "proficiency": "Expert",
                },
                {
                    "skill_name": "Leadership",
                    "category": "Soft",
                    "proficiency": "Proficient",
                },
            ],
        },
        "achievement_stories": {
            "entries": [
                {
                    "situation": "Legacy system was unreliable",
                    "actions": "Designed and led migration",
                    "outcome": "99.9% uptime achieved",
                    "skills": "Python, Architecture",
                },
            ],
        },
        "non_negotiables": {
            "remote_preference": "Remote Only",
            "commutable_cities": "Austin, Denver",
            "minimum_base_salary": "120000",
            "visa_sponsorship": "no",
            "industry_exclusions": "tobacco, gambling",
            "custom_filters": "none",
        },
        "growth_targets": {
            "target_roles": "Staff Engineer, Engineering Manager",
            "target_skills": "System Design, Team Leadership",
        },
        "voice_profile": {
            "tone": "direct and confident",
            "sentence_style": "short and punchy",
            "vocabulary": "technical jargon",
            "things_to_avoid": "buzzwords, synergy",
        },
        "base_resume_setup": {
            "entries": [
                {"role_type": "Senior Software Engineer", "is_primary": True},
            ],
        },
    }

    if not include_education:
        data["education"] = {"skipped": True}
    else:
        data["education"] = {
            "entries": [
                {
                    "degree": "BS Computer Science",
                    "institution": "MIT",
                    "graduation_year": "2018",
                },
            ],
        }

    if not include_certifications:
        data["certifications"] = {"skipped": True}
    else:
        data["certifications"] = {
            "entries": [
                {
                    "name": "AWS Solutions Architect",
                    "issuing_organization": "Amazon",
                    "obtained_date": "2022-05",
                },
            ],
        }

    # Add additional role entries if requested
    if role_count > 1:
        for i in range(1, role_count):
            data["base_resume_setup"]["entries"].append(
                {"role_type": f"Role Variant {i}", "is_primary": False}
            )

    return data


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def persona_for_onboarding(db_session: AsyncSession):
    """Create a persona that has NOT completed onboarding."""
    from app.models import User

    user = User(id=TEST_USER_ID, email="test@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        id=TEST_PERSONA_ID,
        user_id=user.id,
        email="placeholder@example.com",
        full_name="Placeholder",
        phone="000-0000",
        home_city="Unknown",
        home_state="Unknown",
        home_country="USA",
        onboarding_complete=False,
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return persona


# =============================================================================
# Core Finalization
# =============================================================================


class TestFinalizeOnboarding:
    """finalize_onboarding() — persist all gathered data."""

    @pytest.mark.asyncio
    async def test_updates_persona_contact_fields(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """basic_info fields update Persona contact info."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Persona).where(Persona.id == TEST_PERSONA_ID)
        )
        persona = result.scalar_one()
        assert persona.full_name == "Jane Doe"
        assert persona.email == "jane@example.com"
        assert persona.phone == "555-9876"

    @pytest.mark.asyncio
    async def test_updates_persona_preferences(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """non_negotiables and growth_targets update Persona preferences."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Persona).where(Persona.id == TEST_PERSONA_ID)
        )
        persona = result.scalar_one()
        assert persona.remote_preference == "Remote Only"
        assert persona.minimum_base_salary == 120000
        assert persona.visa_sponsorship_required is False
        assert "Staff Engineer" in persona.target_roles
        assert "System Design" in persona.target_skills

    @pytest.mark.asyncio
    async def test_marks_onboarding_complete(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Sets persona.onboarding_complete = True."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Persona).where(Persona.id == TEST_PERSONA_ID)
        )
        persona = result.scalar_one()
        assert persona.onboarding_complete is True
        assert persona.onboarding_step is None

    @pytest.mark.asyncio
    async def test_creates_work_history_entries(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates WorkHistory rows from gathered work_history data."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(WorkHistory)
            .where(WorkHistory.persona_id == TEST_PERSONA_ID)
            .order_by(WorkHistory.display_order)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 2
        assert jobs[0].job_title == "Senior Engineer"
        assert jobs[0].company_name == "Acme Corp"
        assert jobs[1].job_title == "Software Engineer"

    @pytest.mark.asyncio
    async def test_creates_bullets_for_work_history(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates Bullet rows linked to WorkHistory entries."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(WorkHistory)
            .where(WorkHistory.persona_id == TEST_PERSONA_ID)
            .order_by(WorkHistory.display_order)
        )
        jobs = result.scalars().all()

        bullet_result = await db_session.execute(
            select(Bullet)
            .where(Bullet.work_history_id == jobs[0].id)
            .order_by(Bullet.display_order)
        )
        bullets = bullet_result.scalars().all()
        assert len(bullets) == 2
        assert bullets[0].text == "Led migration to microservices"

    @pytest.mark.asyncio
    async def test_creates_skill_entries(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates Skill rows from gathered skills data."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Skill).where(Skill.persona_id == TEST_PERSONA_ID)
        )
        skills = result.scalars().all()
        assert len(skills) == 2
        names = {s.skill_name for s in skills}
        assert names == {"Python", "Leadership"}

    @pytest.mark.asyncio
    async def test_creates_education_entries(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates Education rows from gathered education data."""
        gathered = _make_gathered_data(include_education=True)
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Education).where(Education.persona_id == TEST_PERSONA_ID)
        )
        entries = result.scalars().all()
        assert len(entries) == 1
        assert entries[0].institution == "MIT"
        assert entries[0].degree == "BS Computer Science"

    @pytest.mark.asyncio
    async def test_skips_education_when_flagged(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Skipped education creates no Education rows."""
        gathered = _make_gathered_data(include_education=False)
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Education).where(Education.persona_id == TEST_PERSONA_ID)
        )
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_creates_certification_entries(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates Certification rows from gathered certifications data."""
        gathered = _make_gathered_data(include_certifications=True)
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Certification).where(Certification.persona_id == TEST_PERSONA_ID)
        )
        entries = result.scalars().all()
        assert len(entries) == 1
        assert entries[0].certification_name == "AWS Solutions Architect"

    @pytest.mark.asyncio
    async def test_skips_certifications_when_flagged(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Skipped certifications creates no Certification rows."""
        gathered = _make_gathered_data(include_certifications=False)
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Certification).where(Certification.persona_id == TEST_PERSONA_ID)
        )
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_creates_achievement_stories(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates AchievementStory rows from gathered stories."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(AchievementStory).where(
                AchievementStory.persona_id == TEST_PERSONA_ID
            )
        )
        stories = result.scalars().all()
        assert len(stories) == 1
        assert stories[0].context == "Legacy system was unreliable"
        assert stories[0].outcome == "99.9% uptime achieved"

    @pytest.mark.asyncio
    async def test_creates_voice_profile(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates VoiceProfile from gathered voice_profile data."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(VoiceProfile).where(VoiceProfile.persona_id == TEST_PERSONA_ID)
        )
        vp = result.scalar_one()
        assert vp.tone == "direct and confident"
        assert vp.sentence_style == "short and punchy"

    @pytest.mark.asyncio
    async def test_creates_base_resume_entries(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Creates BaseResume entries from base_resume_setup."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(BaseResume).where(BaseResume.persona_id == TEST_PERSONA_ID)
        )
        resumes = result.scalars().all()
        assert len(resumes) == 1
        assert resumes[0].role_type == "Senior Software Engineer"
        assert resumes[0].is_primary is True
        assert resumes[0].status == "Active"

    @pytest.mark.asyncio
    async def test_creates_multiple_base_resumes(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Multiple role entries create multiple BaseResume rows."""
        gathered = _make_gathered_data(role_count=3)
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(BaseResume)
            .where(BaseResume.persona_id == TEST_PERSONA_ID)
            .order_by(BaseResume.display_order)
        )
        resumes = result.scalars().all()
        assert len(resumes) == 3
        primary = [r for r in resumes if r.is_primary]
        assert len(primary) == 1

    @pytest.mark.asyncio
    async def test_base_resume_includes_job_and_skill_ids(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """BaseResume included_jobs and skills_emphasis populated from gathered data."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(BaseResume).where(BaseResume.persona_id == TEST_PERSONA_ID)
        )
        resume = result.scalar_one()
        assert len(resume.included_jobs) == 2
        assert len(resume.skills_emphasis) == 2

    @pytest.mark.asyncio
    async def test_returns_result_summary(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Returns OnboardingResult with entity counts."""
        gathered = _make_gathered_data()
        result = await finalize_onboarding(
            gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session
        )

        assert result.work_history_count == 2
        assert result.skill_count == 2
        assert result.education_count == 1
        assert result.certification_count == 1
        assert result.story_count == 1
        assert result.base_resume_count == 1

    @pytest.mark.asyncio
    async def test_result_with_skipped_sections(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Skipped sections show zero counts in result."""
        gathered = _make_gathered_data(
            include_education=False, include_certifications=False
        )
        result = await finalize_onboarding(
            gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session
        )

        assert result.education_count == 0
        assert result.certification_count == 0
        assert result.work_history_count == 2


# =============================================================================
# Edge Cases
# =============================================================================


class TestFinalizeOnboardingEdgeCases:
    """Edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_work_history(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Empty work_history entries list creates no WorkHistory rows."""
        gathered = _make_gathered_data()
        gathered["work_history"]["entries"] = []
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(WorkHistory).where(WorkHistory.persona_id == TEST_PERSONA_ID)
        )
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_missing_optional_sections(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Missing sections in gathered_data are gracefully skipped."""
        gathered = _make_gathered_data()
        del gathered["education"]
        del gathered["certifications"]
        result = await finalize_onboarding(
            gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session
        )

        assert result.education_count == 0
        assert result.certification_count == 0

    @pytest.mark.asyncio
    async def test_location_parsed_into_city_state(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Location string 'City, State' parsed into home_city and home_state."""
        gathered = _make_gathered_data()
        gathered["basic_info"]["location"] = "Denver, Colorado"
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Persona).where(Persona.id == TEST_PERSONA_ID)
        )
        persona = result.scalar_one()
        assert persona.home_city == "Denver"
        assert persona.home_state == "Colorado"

    @pytest.mark.asyncio
    async def test_location_single_value_sets_city(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Location string without comma sets home_city only."""
        gathered = _make_gathered_data()
        gathered["basic_info"]["location"] = "Remote"
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Persona).where(Persona.id == TEST_PERSONA_ID)
        )
        persona = result.scalar_one()
        assert persona.home_city == "Remote"

    @pytest.mark.asyncio
    async def test_salary_parsed_from_string(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Salary string with formatting is parsed to integer."""
        gathered = _make_gathered_data()
        gathered["non_negotiables"]["minimum_base_salary"] = "$150,000"
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(Persona).where(Persona.id == TEST_PERSONA_ID)
        )
        persona = result.scalar_one()
        assert persona.minimum_base_salary == 150000

    @pytest.mark.asyncio
    async def test_work_history_date_parsing(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Work history dates like '2020-01' parsed to date objects."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        result = await db_session.execute(
            select(WorkHistory)
            .where(WorkHistory.persona_id == TEST_PERSONA_ID)
            .order_by(WorkHistory.display_order)
        )
        jobs = result.scalars().all()
        assert jobs[0].start_date == date(2020, 1, 1)
        assert jobs[0].end_date == date(2024, 6, 1)


# =============================================================================
# Error Guards
# =============================================================================


class TestFinalizeOnboardingGuards:
    """Error handling and idempotency guards."""

    @pytest.mark.asyncio
    async def test_nonexistent_persona_raises_not_found(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Non-existent persona_id raises NotFoundError."""
        gathered = _make_gathered_data()
        fake_id = uuid.uuid4()

        with pytest.raises(NotFoundError):
            await finalize_onboarding(gathered, fake_id, TEST_USER_ID, db_session)

    @pytest.mark.asyncio
    async def test_already_complete_raises_invalid_state(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Calling finalize twice raises InvalidStateError (idempotency guard)."""
        gathered = _make_gathered_data()
        await finalize_onboarding(gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session)

        with pytest.raises(InvalidStateError):
            await finalize_onboarding(
                gathered, TEST_PERSONA_ID, TEST_USER_ID, db_session
            )

    @pytest.mark.asyncio
    async def test_wrong_user_id_raises_not_found(
        self,
        db_session: AsyncSession,
        persona_for_onboarding,  # noqa: ARG002
    ) -> None:
        """Persona owned by different user raises NotFoundError (tenant isolation)."""
        gathered = _make_gathered_data()
        wrong_user_id = uuid.uuid4()

        with pytest.raises(NotFoundError):
            await finalize_onboarding(
                gathered, TEST_PERSONA_ID, wrong_user_id, db_session
            )
