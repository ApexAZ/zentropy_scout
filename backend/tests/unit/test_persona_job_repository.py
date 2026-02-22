"""Tests for PersonaJobRepository — read and create operations.

REQ-015 §8, §9: Per-user job relationship management scoped to user_id.
Fixtures: user_a, other_user, persona_a, other_persona, job_source,
shared_job, shared_job_2, pj_a, pj_other from tests/unit/conftest.py.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.persona_job import PersonaJob
from app.models.user import User
from app.repositories.persona_job_repository import PersonaJobRepository

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class TestGetById:
    """Test PersonaJobRepository.get_by_id()."""

    async def test_returns_pj_when_found_and_owned(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Returns PersonaJob when ID matches and user owns it."""
        result = await PersonaJobRepository.get_by_id(
            db_session, pj_a.id, user_id=user_a.id
        )
        assert result is not None
        assert result.id == pj_a.id

    async def test_returns_none_for_wrong_user(
        self, db_session: AsyncSession, pj_a: PersonaJob, other_user: User
    ):
        """Returns None when user does not own the PersonaJob."""
        result = await PersonaJobRepository.get_by_id(
            db_session, pj_a.id, user_id=other_user.id
        )
        assert result is None

    async def test_returns_none_when_not_found(
        self, db_session: AsyncSession, user_a: User
    ):
        """Non-existent ID returns None."""
        result = await PersonaJobRepository.get_by_id(
            db_session, _MISSING_UUID, user_id=user_a.id
        )
        assert result is None


class TestGetForPersona:
    """Test PersonaJobRepository.get_for_persona()."""

    async def test_returns_all_for_persona(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        user_a: User,
        shared_job: JobPosting,  # noqa: ARG002
        shared_job_2: JobPosting,
        pj_a: PersonaJob,  # noqa: ARG002
    ):
        """Returns all PersonaJob records for a persona."""
        pj2 = PersonaJob(
            persona_id=persona_a.id,
            job_posting_id=shared_job_2.id,
            status="Discovered",
            discovery_method="pool",
        )
        db_session.add(pj2)
        await db_session.flush()

        results = await PersonaJobRepository.get_for_persona(
            db_session, persona_id=persona_a.id, user_id=user_a.id
        )
        assert len(results) == 2

    async def test_returns_empty_for_no_jobs(
        self, db_session: AsyncSession, persona_a: Persona, user_a: User
    ):
        """Returns empty list when persona has no jobs."""
        results = await PersonaJobRepository.get_for_persona(
            db_session, persona_id=persona_a.id, user_id=user_a.id
        )
        assert results == []

    async def test_returns_empty_for_wrong_user(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        other_user: User,
        pj_a: PersonaJob,  # noqa: ARG002
    ):
        """Returns empty list when user does not own the persona."""
        results = await PersonaJobRepository.get_for_persona(
            db_session, persona_id=persona_a.id, user_id=other_user.id
        )
        assert results == []

    async def test_does_not_return_other_personas_jobs(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        user_a: User,
        pj_a: PersonaJob,  # noqa: ARG002
        pj_other: PersonaJob,  # noqa: ARG002
    ):
        """Only returns jobs for the requested persona, not other users'."""
        results = await PersonaJobRepository.get_for_persona(
            db_session, persona_id=persona_a.id, user_id=user_a.id
        )
        assert len(results) == 1


class TestGetByPersonaAndJob:
    """Test PersonaJobRepository.get_by_persona_and_job()."""

    async def test_returns_pj_when_link_exists(
        self,
        db_session: AsyncSession,
        pj_a: PersonaJob,
        persona_a: Persona,
        shared_job: JobPosting,
    ):
        """Returns PersonaJob when persona-job link exists."""
        result = await PersonaJobRepository.get_by_persona_and_job(
            db_session,
            persona_id=persona_a.id,
            job_posting_id=shared_job.id,
        )
        assert result is not None
        assert result.id == pj_a.id

    async def test_returns_none_when_no_link(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        shared_job: JobPosting,
    ):
        """Returns None when no persona-job link exists."""
        result = await PersonaJobRepository.get_by_persona_and_job(
            db_session,
            persona_id=persona_a.id,
            job_posting_id=shared_job.id,
        )
        assert result is None


class TestCreate:
    """Test PersonaJobRepository.create()."""

    async def test_creates_with_required_fields(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        shared_job: JobPosting,
    ):
        """Minimal creation with required fields."""
        pj = await PersonaJobRepository.create(
            db_session,
            persona_id=persona_a.id,
            job_posting_id=shared_job.id,
            discovery_method="scouter",
        )
        assert pj.id is not None
        assert pj.persona_id == persona_a.id
        assert pj.job_posting_id == shared_job.id
        assert pj.status == "Discovered"
        assert pj.is_favorite is False
        assert pj.discovery_method == "scouter"

    async def test_creates_with_all_fields(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        shared_job: JobPosting,
    ):
        """Creation with all optional fields."""
        pj = await PersonaJobRepository.create(
            db_session,
            persona_id=persona_a.id,
            job_posting_id=shared_job.id,
            discovery_method="manual",
            status="Applied",
            is_favorite=True,
            fit_score=90,
            stretch_score=20,
            failed_non_negotiables=["Remote only"],
            score_details={"overall": 0.9},
        )
        assert pj.status == "Applied"
        assert pj.is_favorite is True
        assert pj.fit_score == 90
        assert pj.stretch_score == 20

    async def test_rejects_duplicate_persona_job(
        self,
        db_session: AsyncSession,
        pj_a: PersonaJob,  # noqa: ARG002
        persona_a: Persona,
        shared_job: JobPosting,
    ):
        """Duplicate (persona_id, job_posting_id) raises IntegrityError."""
        with pytest.raises(IntegrityError):
            await PersonaJobRepository.create(
                db_session,
                persona_id=persona_a.id,
                job_posting_id=shared_job.id,
                discovery_method="pool",
            )

    async def test_timestamps_set(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        shared_job: JobPosting,
    ):
        """created_at, updated_at, and discovered_at are populated."""
        pj = await PersonaJobRepository.create(
            db_session,
            persona_id=persona_a.id,
            job_posting_id=shared_job.id,
            discovery_method="scouter",
        )
        assert pj.created_at is not None
        assert pj.updated_at is not None
        assert pj.discovered_at is not None
