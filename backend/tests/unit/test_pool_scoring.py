"""Tests for pool scoring pure functions.

REQ-015 §7.2, REQ-008 §4: Keyword pre-screen, experience alignment,
work model alignment, seniority alignment, keyword overlap, lightweight fit.
"""

import hashlib
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.persona_content import Skill
from app.models.user import User
from app.services.pool_scoring import (
    calculate_lightweight_fit,
    keyword_pre_screen,
    score_experience_alignment,
    score_keyword_overlap,
    score_seniority_alignment,
    score_work_model_alignment,
)

_TODAY = date.today()
_HASH_A = hashlib.sha256(b"Python developer at Acme").hexdigest()
_HASH_B = hashlib.sha256(b"Data analyst at DataCo").hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def source(db_session: AsyncSession) -> JobSource:
    """Create a job source."""
    s = JobSource(
        source_name="Scoring Test", source_type="Extension", description="Test"
    )
    db_session.add(s)
    await db_session.flush()
    await db_session.refresh(s)
    return s


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Create User A."""
    u = User(email="score_a@test.com")
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def persona_with_skills(db_session: AsyncSession, user_a: User) -> Persona:
    """Create persona with Python/FastAPI skills, 5 years, Remote Only."""
    p = Persona(
        user_id=user_a.id,
        full_name="Dev A",
        email="a@test.com",
        phone="555-0001",
        home_city="Remote City",
        home_state="CA",
        home_country="USA",
        years_experience=5,
        remote_preference="Remote Only",
        onboarding_complete=True,
        minimum_fit_threshold=50,
    )
    db_session.add(p)
    await db_session.flush()

    for name, stype in [
        ("Python", "Hard"),
        ("FastAPI", "Hard"),
        ("PostgreSQL", "Hard"),
        ("Communication", "Soft"),
    ]:
        skill = Skill(
            persona_id=p.id,
            skill_name=name,
            skill_type=stype,
            category="Engineering",
            proficiency="Proficient",
            years_used=3,
            last_used="Current",
        )
        db_session.add(skill)

    await db_session.flush()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def python_job(db_session: AsyncSession, source: JobSource) -> JobPosting:
    """Create a Python backend job posting."""
    jp = JobPosting(
        source_id=source.id,
        job_title="Senior Python Developer",
        company_name="Acme Corp",
        description="Build great software using Python, FastAPI, and PostgreSQL.",
        description_hash=_HASH_A,
        first_seen_date=_TODAY,
        work_model="Remote",
        seniority_level="Senior",
        years_experience_min=3,
        years_experience_max=8,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


@pytest.fixture
async def data_job(db_session: AsyncSession, source: JobSource) -> JobPosting:
    """Create a Data Analyst job (no skill match for test persona)."""
    jp = JobPosting(
        source_id=source.id,
        job_title="Data Analyst",
        company_name="DataCo",
        description="Analyze business data trends using Excel and Tableau.",
        description_hash=_HASH_B,
        first_seen_date=_TODAY,
        work_model="Onsite",
        seniority_level="Entry",
        years_experience_min=0,
        years_experience_max=2,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


async def _load_persona_with_skills(
    db: AsyncSession,
    persona_id: "uuid.UUID",  # noqa: F821
) -> Persona:
    """Helper to reload a persona with skills eagerly loaded."""
    stmt = (
        select(Persona)
        .where(Persona.id == persona_id)
        .options(selectinload(Persona.skills))
    )
    result = await db.execute(stmt)
    return result.scalar_one()


# ===========================================================================
# Pure function tests
# ===========================================================================


class TestKeywordPreScreen:
    """Tests for keyword_pre_screen()."""

    def test_match_in_title(self) -> None:
        assert keyword_pre_screen("Python Developer", "", ["Python"]) is True

    def test_match_in_description(self) -> None:
        assert keyword_pre_screen("SWE", "We use Python daily", ["Python"]) is True

    def test_no_match(self) -> None:
        assert keyword_pre_screen("Java Developer", "Java Spring", ["Python"]) is False

    def test_case_insensitive(self) -> None:
        assert keyword_pre_screen("PYTHON DEVELOPER", "", ["python"]) is True

    def test_empty_skills_returns_false(self) -> None:
        assert keyword_pre_screen("Python Developer", "code", []) is False

    def test_multi_word_skill_match(self) -> None:
        assert (
            keyword_pre_screen(
                "ML Engineer", "experience with machine learning", ["Machine Learning"]
            )
            is True
        )

    def test_partial_overlap_still_matches(self) -> None:
        """At least one skill matches → True, even if others don't."""
        assert (
            keyword_pre_screen("Python Developer", "", ["Python", "Rust", "Go"]) is True
        )


class TestScoreExperienceAlignment:
    """Tests for score_experience_alignment()."""

    def test_within_range(self) -> None:
        assert score_experience_alignment(5, 3, 8) == 100.0

    def test_below_minimum(self) -> None:
        assert score_experience_alignment(1, 3, 8) == 60.0

    def test_above_maximum(self) -> None:
        assert score_experience_alignment(10, 3, 8) == 90.0

    def test_far_below_minimum_floors_at_zero(self) -> None:
        assert score_experience_alignment(0, 10, 15) == 0.0

    def test_persona_years_none_returns_neutral(self) -> None:
        assert score_experience_alignment(None, 3, 8) == 70.0

    def test_job_range_none_returns_neutral(self) -> None:
        assert score_experience_alignment(5, None, None) == 70.0

    def test_only_min_specified(self) -> None:
        assert score_experience_alignment(5, 3, None) == 100.0

    def test_only_max_specified(self) -> None:
        assert score_experience_alignment(5, None, 10) == 100.0

    def test_exactly_at_minimum(self) -> None:
        assert score_experience_alignment(3, 3, 8) == 100.0

    def test_exactly_at_maximum(self) -> None:
        assert score_experience_alignment(8, 3, 8) == 100.0


class TestScoreWorkModelAlignment:
    """Tests for score_work_model_alignment()."""

    def test_remote_match(self) -> None:
        assert score_work_model_alignment("Remote Only", "Remote") == 100.0

    def test_remote_vs_onsite(self) -> None:
        assert score_work_model_alignment("Remote Only", "Onsite") == 0.0

    def test_remote_vs_hybrid(self) -> None:
        assert score_work_model_alignment("Remote Only", "Hybrid") == 30.0

    def test_hybrid_ok_vs_hybrid(self) -> None:
        assert score_work_model_alignment("Hybrid OK", "Hybrid") == 100.0

    def test_no_preference_always_100(self) -> None:
        assert score_work_model_alignment("No Preference", "Onsite") == 100.0

    def test_none_preference_returns_100(self) -> None:
        assert score_work_model_alignment(None, "Onsite") == 100.0

    def test_none_work_model_returns_neutral(self) -> None:
        assert score_work_model_alignment("Remote Only", None) == 70.0

    def test_onsite_ok_vs_onsite(self) -> None:
        assert score_work_model_alignment("Onsite OK", "Onsite") == 100.0


class TestScoreSeniorityAlignment:
    """Tests for score_seniority_alignment()."""

    def test_exact_match(self) -> None:
        assert score_seniority_alignment(6, "Senior") == 100.0

    def test_one_level_off(self) -> None:
        assert score_seniority_alignment(4, "Senior") == 75.0

    def test_two_levels_off(self) -> None:
        assert score_seniority_alignment(1, "Senior") == 50.0

    def test_four_levels_off(self) -> None:
        assert score_seniority_alignment(0, "Executive") == 0.0

    def test_missing_persona_years(self) -> None:
        assert score_seniority_alignment(None, "Senior") == 70.0

    def test_missing_job_seniority(self) -> None:
        assert score_seniority_alignment(5, None) == 70.0

    def test_unknown_seniority_value(self) -> None:
        assert score_seniority_alignment(5, "Intern") == 70.0


class TestScoreKeywordOverlap:
    """Tests for score_keyword_overlap()."""

    def test_all_skills_match(self) -> None:
        score = score_keyword_overlap(
            "Python Developer",
            "Build with Python, FastAPI, and PostgreSQL",
            ["Python", "FastAPI", "PostgreSQL"],
        )
        assert score == 100.0

    def test_one_of_three_match(self) -> None:
        score = score_keyword_overlap(
            "Python Developer", "Build stuff", ["Python", "Rust", "Go"]
        )
        assert score == 100.0

    def test_no_match(self) -> None:
        score = score_keyword_overlap(
            "Java Developer", "Spring Boot framework", ["Python", "FastAPI"]
        )
        assert score == 0.0

    def test_empty_skills_returns_neutral(self) -> None:
        assert score_keyword_overlap("Python Dev", "Python code", []) == 70.0

    def test_partial_overlap_below_30_percent(self) -> None:
        score = score_keyword_overlap(
            "Python Developer",
            "Python code",
            ["Python", "Rust", "Go", "C++", "Haskell"],
        )
        assert 60.0 <= score <= 70.0


class TestCalculateLightweightFit:
    """Tests for calculate_lightweight_fit() — uses real model objects."""

    async def test_good_match_python_job(
        self,
        db_session: AsyncSession,
        persona_with_skills: Persona,
        python_job: JobPosting,
    ) -> None:
        persona = await _load_persona_with_skills(db_session, persona_with_skills.id)
        fit = calculate_lightweight_fit(python_job, persona, persona.skills)
        assert fit.total >= 70

    async def test_poor_match_data_job(
        self,
        db_session: AsyncSession,
        persona_with_skills: Persona,
        data_job: JobPosting,
    ) -> None:
        persona = await _load_persona_with_skills(db_session, persona_with_skills.id)
        fit = calculate_lightweight_fit(data_job, persona, persona.skills)
        assert fit.total < 50
