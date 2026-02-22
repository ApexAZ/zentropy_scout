"""Shared fixtures for unit tests requiring multi-user + shared pool data.

These fixtures support PersonaJob and JobPosting repository tests.
Names chosen to avoid shadowing top-level conftest fixtures
(test_user, user_b, persona_user_b, test_job_source, etc.).
"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.persona_job import PersonaJob
from app.models.user import User

_TODAY = date.today()


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Create User A for repository tests."""
    user = User(email="usera@test.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create a second user for cross-tenant repository tests.

    Named 'other_user' to avoid shadowing top-level conftest 'user_b'
    which uses a fixed UUID (USER_B_ID) for API-level tests.
    """
    user = User(email="other@test.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def persona_a(db_session: AsyncSession, user_a: User) -> Persona:
    """Create Persona for User A."""
    persona = Persona(
        user_id=user_a.id,
        full_name="User A",
        email="persona_a@test.com",
        phone="555-0001",
        home_city="City A",
        home_state="State A",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.flush()
    await db_session.refresh(persona)
    return persona


@pytest.fixture
async def other_persona(db_session: AsyncSession, other_user: User) -> Persona:
    """Create Persona for the other user (cross-tenant tests)."""
    persona = Persona(
        user_id=other_user.id,
        full_name="Other User",
        email="other_persona@test.com",
        phone="555-0002",
        home_city="City B",
        home_state="State B",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.flush()
    await db_session.refresh(persona)
    return persona


@pytest.fixture
async def job_source(db_session: AsyncSession) -> JobSource:
    """Create a job source for shared pool tests."""
    source = JobSource(
        source_name="TestSource",
        source_type="Extension",
        description="Test job source",
    )
    db_session.add(source)
    await db_session.flush()
    await db_session.refresh(source)
    return source


@pytest.fixture
async def shared_job(db_session: AsyncSession, job_source: JobSource) -> JobPosting:
    """Create a shared pool job posting."""
    jp = JobPosting(
        source_id=job_source.id,
        job_title="Software Engineer",
        company_name="Acme Corp",
        description="Build great things",
        description_hash="a" * 64,
        first_seen_date=_TODAY,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


@pytest.fixture
async def shared_job_2(db_session: AsyncSession, job_source: JobSource) -> JobPosting:
    """Create a second shared pool job posting."""
    jp = JobPosting(
        source_id=job_source.id,
        job_title="Data Scientist",
        company_name="DataCo",
        description="Analyze data",
        description_hash="b" * 64,
        first_seen_date=_TODAY,
    )
    db_session.add(jp)
    await db_session.flush()
    await db_session.refresh(jp)
    return jp


@pytest.fixture
async def pj_a(
    db_session: AsyncSession, persona_a: Persona, shared_job: JobPosting
) -> PersonaJob:
    """Create a PersonaJob link for User A."""
    pj = PersonaJob(
        persona_id=persona_a.id,
        job_posting_id=shared_job.id,
        status="Discovered",
        discovery_method="scouter",
    )
    db_session.add(pj)
    await db_session.flush()
    await db_session.refresh(pj)
    return pj


@pytest.fixture
async def pj_other(
    db_session: AsyncSession, other_persona: Persona, shared_job: JobPosting
) -> PersonaJob:
    """Create a PersonaJob link for the other user (same shared job)."""
    pj = PersonaJob(
        persona_id=other_persona.id,
        job_posting_id=shared_job.id,
        status="Discovered",
        discovery_method="pool",
    )
    db_session.add(pj)
    await db_session.flush()
    await db_session.refresh(pj)
    return pj
