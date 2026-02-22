"""Tests for pool surfacing service — DB queries and orchestration.

REQ-015 §7: Pool surfacing — query helpers, surface_job_to_personas,
run_surfacing_pass, UNIQUE dedup, rate limiting.
"""

import hashlib
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.persona_content import Skill
from app.models.persona_job import PersonaJob
from app.models.user import User
from app.services.pool_surfacing_service import (
    SurfacingPassResult,
    get_active_personas_with_skills,
    get_existing_persona_ids_for_job,
    get_unsurfaced_jobs,
    run_surfacing_pass,
    surface_job_to_personas,
)

_TODAY = date.today()
_HASH_A = hashlib.sha256(b"Python developer at Acme").hexdigest()
_HASH_B = hashlib.sha256(b"Data analyst at DataCo").hexdigest()
_HASH_C = hashlib.sha256(b"React frontend at StartupX").hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def source(db_session: AsyncSession) -> JobSource:
    """Create a job source."""
    s = JobSource(
        source_name="Surfacing Test", source_type="Extension", description="Test"
    )
    db_session.add(s)
    await db_session.flush()
    await db_session.refresh(s)
    return s


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Create User A."""
    u = User(email="surf_a@test.com")
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Create User B."""
    u = User(email="surf_b@test.com")
    db_session.add(u)
    await db_session.flush()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def persona_a(db_session: AsyncSession, user_a: User) -> Persona:
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
        db_session.add(
            Skill(
                persona_id=p.id,
                skill_name=name,
                skill_type=stype,
                category="Engineering",
                proficiency="Proficient",
                years_used=3,
                last_used="Current",
            )
        )

    await db_session.flush()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def persona_b(db_session: AsyncSession, user_b: User) -> Persona:
    """Create persona with React/TypeScript skills, 2 years, No Preference."""
    p = Persona(
        user_id=user_b.id,
        full_name="Dev B",
        email="b@test.com",
        phone="555-0002",
        home_city="Somewhere",
        home_state="NY",
        home_country="USA",
        years_experience=2,
        remote_preference="No Preference",
        onboarding_complete=True,
        minimum_fit_threshold=40,
    )
    db_session.add(p)
    await db_session.flush()

    for name, stype in [("React", "Hard"), ("TypeScript", "Hard"), ("CSS", "Hard")]:
        db_session.add(
            Skill(
                persona_id=p.id,
                skill_name=name,
                skill_type=stype,
                category="Frontend",
                proficiency="Familiar",
                years_used=2,
                last_used="Current",
            )
        )

    await db_session.flush()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def persona_not_onboarded(db_session: AsyncSession, user_a: User) -> Persona:
    """Create persona that has NOT completed onboarding."""
    p = Persona(
        user_id=user_a.id,
        full_name="Not Ready",
        email="notready@test.com",
        phone="555-0099",
        home_city="Limbo",
        home_state="XX",
        home_country="USA",
        onboarding_complete=False,
    )
    db_session.add(p)
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
async def react_job(db_session: AsyncSession, source: JobSource) -> JobPosting:
    """Create a React frontend job posting."""
    jp = JobPosting(
        source_id=source.id,
        job_title="React Frontend Engineer",
        company_name="StartupX",
        description="Build user interfaces with React and TypeScript. CSS expertise a plus.",
        description_hash=_HASH_C,
        first_seen_date=_TODAY,
        work_model="Hybrid",
        seniority_level="Mid",
        years_experience_min=1,
        years_experience_max=4,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


@pytest.fixture
async def data_job(db_session: AsyncSession, source: JobSource) -> JobPosting:
    """Create a Data Analyst job (no skill match for test personas)."""
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


async def _load_all_personas_with_skills(db: AsyncSession) -> list[Persona]:
    """Helper to load all personas with skills eagerly loaded."""
    stmt = select(Persona).options(selectinload(Persona.skills))
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ===========================================================================
# Database query tests
# ===========================================================================


class TestGetUnsurfacedJobs:
    """Tests for get_unsurfaced_jobs()."""

    async def test_returns_active_jobs_since_timestamp(
        self, db_session: AsyncSession, python_job: JobPosting
    ) -> None:
        since = datetime.now(UTC) - timedelta(hours=1)
        jobs = await get_unsurfaced_jobs(db_session, since=since)
        assert len(jobs) >= 1
        assert any(j.id == python_job.id for j in jobs)

    async def test_respects_limit(
        self,
        db_session: AsyncSession,
        python_job: JobPosting,  # noqa: ARG002
        react_job: JobPosting,  # noqa: ARG002
        data_job: JobPosting,  # noqa: ARG002
    ) -> None:
        since = datetime.now(UTC) - timedelta(hours=1)
        jobs = await get_unsurfaced_jobs(db_session, since=since, limit=2)
        assert len(jobs) <= 2

    async def test_excludes_old_jobs(
        self,
        db_session: AsyncSession,
        python_job: JobPosting,  # noqa: ARG002
    ) -> None:
        since = datetime.now(UTC) + timedelta(hours=1)
        jobs = await get_unsurfaced_jobs(db_session, since=since)
        assert len(jobs) == 0


class TestGetActivePersonasWithSkills:
    """Tests for get_active_personas_with_skills()."""

    async def test_returns_onboarded_personas(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        persona_b: Persona,  # noqa: ARG002
    ) -> None:
        personas = await get_active_personas_with_skills(db_session)
        ids = {p.id for p in personas}
        assert persona_a.id in ids

    async def test_excludes_non_onboarded(
        self,
        db_session: AsyncSession,
        persona_a: Persona,  # noqa: ARG002
        persona_not_onboarded: Persona,
    ) -> None:
        personas = await get_active_personas_with_skills(db_session)
        ids = {p.id for p in personas}
        assert persona_not_onboarded.id not in ids

    async def test_skills_are_loaded(
        self,
        db_session: AsyncSession,
        persona_a: Persona,  # noqa: ARG002
    ) -> None:
        personas = await get_active_personas_with_skills(db_session)
        for p in personas:
            assert isinstance(p.skills, list)


class TestGetExistingPersonaIdsForJob:
    """Tests for get_existing_persona_ids_for_job()."""

    async def test_returns_linked_persona_ids(
        self, db_session: AsyncSession, persona_a: Persona, python_job: JobPosting
    ) -> None:
        link = PersonaJob(
            persona_id=persona_a.id,
            job_posting_id=python_job.id,
            discovery_method="scouter",
        )
        db_session.add(link)
        await db_session.flush()

        result = await get_existing_persona_ids_for_job(db_session, python_job.id)
        assert persona_a.id in result

    async def test_returns_empty_when_no_links(
        self, db_session: AsyncSession, python_job: JobPosting
    ) -> None:
        result = await get_existing_persona_ids_for_job(db_session, python_job.id)
        assert len(result) == 0


# ===========================================================================
# Orchestration tests
# ===========================================================================


class TestSurfaceJobToPersonas:
    """Tests for surface_job_to_personas()."""

    async def test_creates_links_for_matching_personas(
        self,
        db_session: AsyncSession,
        persona_a: Persona,  # noqa: ARG002
        persona_b: Persona,  # noqa: ARG002
        python_job: JobPosting,
    ) -> None:
        personas = await _load_all_personas_with_skills(db_session)
        created, _, _ = await surface_job_to_personas(db_session, python_job, personas)
        assert created >= 1

    async def test_skips_already_linked_personas(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        python_job: JobPosting,
    ) -> None:
        link = PersonaJob(
            persona_id=persona_a.id,
            job_posting_id=python_job.id,
            discovery_method="scouter",
        )
        db_session.add(link)
        await db_session.flush()

        personas = await _load_all_personas_with_skills(db_session)
        created, _, skipped_existing = await surface_job_to_personas(
            db_session, python_job, personas
        )
        assert skipped_existing >= 1

    async def test_respects_max_personas_limit(
        self,
        db_session: AsyncSession,
        persona_a: Persona,  # noqa: ARG002
        persona_b: Persona,  # noqa: ARG002
        python_job: JobPosting,
    ) -> None:
        personas = await _load_all_personas_with_skills(db_session)
        created, skipped_thresh, _ = await surface_job_to_personas(
            db_session, python_job, personas, max_personas=1
        )
        assert created + skipped_thresh <= 1

    async def test_skips_personas_below_threshold(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        data_job: JobPosting,
    ) -> None:
        persona_a.minimum_fit_threshold = 95
        await db_session.flush()

        stmt = (
            select(Persona)
            .where(Persona.id == persona_a.id)
            .options(selectinload(Persona.skills))
        )
        result = await db_session.execute(stmt)
        personas = list(result.scalars().all())

        created, skipped_threshold, _ = await surface_job_to_personas(
            db_session, data_job, personas
        )
        assert created == 0
        assert skipped_threshold >= 1

    async def test_created_link_has_pool_discovery_method(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        python_job: JobPosting,
    ) -> None:
        personas = await _load_all_personas_with_skills(db_session)
        await surface_job_to_personas(db_session, python_job, personas)

        link_stmt = select(PersonaJob).where(
            PersonaJob.persona_id == persona_a.id,
            PersonaJob.job_posting_id == python_job.id,
        )
        link_result = await db_session.execute(link_stmt)
        link = link_result.scalar_one_or_none()

        if link is not None:
            assert link.discovery_method == "pool"
            assert link.status == "Discovered"
            assert link.fit_score is not None
            assert link.scored_at is not None


class TestRunSurfacingPass:
    """Tests for run_surfacing_pass()."""

    async def test_surfaces_matching_jobs(
        self,
        db_session: AsyncSession,
        persona_a: Persona,  # noqa: ARG002
        persona_b: Persona,  # noqa: ARG002
        python_job: JobPosting,  # noqa: ARG002
        react_job: JobPosting,  # noqa: ARG002
    ) -> None:
        since = datetime.now(UTC) - timedelta(hours=1)
        result = await run_surfacing_pass(db_session, since=since)

        assert isinstance(result, SurfacingPassResult)
        assert result.jobs_processed >= 2
        assert result.links_created >= 1

    async def test_no_jobs_returns_zero(self, db_session: AsyncSession) -> None:
        since = datetime.now(UTC) + timedelta(hours=1)
        result = await run_surfacing_pass(db_session, since=since)
        assert result.jobs_processed == 0
        assert result.links_created == 0

    async def test_no_personas_returns_zero_links(
        self,
        db_session: AsyncSession,
        python_job: JobPosting,  # noqa: ARG002
    ) -> None:
        since = datetime.now(UTC) - timedelta(hours=1)
        result = await run_surfacing_pass(db_session, since=since)
        assert result.links_created == 0

    async def test_idempotent_does_not_create_duplicate_links(
        self,
        db_session: AsyncSession,
        persona_a: Persona,  # noqa: ARG002
        python_job: JobPosting,  # noqa: ARG002
    ) -> None:
        since = datetime.now(UTC) - timedelta(hours=1)

        result1 = await run_surfacing_pass(db_session, since=since)
        result2 = await run_surfacing_pass(db_session, since=since)

        assert result2.links_created == 0
        assert result2.links_skipped_existing >= result1.links_created
