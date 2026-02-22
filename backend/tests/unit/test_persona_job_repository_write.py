"""Tests for PersonaJobRepository — update and bulk operations.

REQ-015 §8, §9: Per-user job relationship management scoped to user_id.
Fixtures: user_a, other_user, persona_a, other_persona, job_source,
shared_job, shared_job_2, pj_a, pj_other from tests/unit/conftest.py.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.persona_job import PersonaJob
from app.models.user import User
from app.repositories.persona_job_repository import PersonaJobRepository

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class TestUpdate:
    """Test PersonaJobRepository.update()."""

    async def test_updates_status(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Status can be changed."""
        result = await PersonaJobRepository.update(
            db_session, pj_a.id, user_id=user_a.id, status="Dismissed"
        )
        assert result is not None
        assert result.status == "Dismissed"

    async def test_updates_is_favorite(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """is_favorite can be toggled."""
        result = await PersonaJobRepository.update(
            db_session, pj_a.id, user_id=user_a.id, is_favorite=True
        )
        assert result is not None
        assert result.is_favorite is True

    async def test_updates_scores(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Scoring fields can be updated."""
        result = await PersonaJobRepository.update(
            db_session,
            pj_a.id,
            user_id=user_a.id,
            fit_score=85,
            stretch_score=40,
            score_details={"match": 0.85},
        )
        assert result is not None
        assert result.fit_score == 85
        assert result.stretch_score == 40

    async def test_returns_none_for_wrong_user(
        self, db_session: AsyncSession, pj_a: PersonaJob, other_user: User
    ):
        """Update scoped to user — wrong user gets None."""
        result = await PersonaJobRepository.update(
            db_session, pj_a.id, user_id=other_user.id, status="Dismissed"
        )
        assert result is None

    async def test_returns_none_for_nonexistent(
        self, db_session: AsyncSession, user_a: User
    ):
        """Update on non-existent ID returns None."""
        result = await PersonaJobRepository.update(
            db_session, _MISSING_UUID, user_id=user_a.id, status="Dismissed"
        )
        assert result is None

    async def test_rejects_unknown_fields(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Unknown field names raise ValueError."""
        with pytest.raises(ValueError, match="bad_field"):
            await PersonaJobRepository.update(
                db_session, pj_a.id, user_id=user_a.id, bad_field="nope"
            )

    async def test_rejects_persona_id_update(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """persona_id cannot be changed."""
        with pytest.raises(ValueError, match="persona_id"):
            await PersonaJobRepository.update(
                db_session,
                pj_a.id,
                user_id=user_a.id,
                persona_id=uuid.uuid4(),
            )

    async def test_rejects_job_posting_id_update(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """job_posting_id cannot be changed."""
        with pytest.raises(ValueError, match="job_posting_id"):
            await PersonaJobRepository.update(
                db_session,
                pj_a.id,
                user_id=user_a.id,
                job_posting_id=uuid.uuid4(),
            )

    async def test_preserves_unmodified_fields(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Fields not passed to update remain unchanged."""
        await PersonaJobRepository.update(
            db_session, pj_a.id, user_id=user_a.id, is_favorite=True
        )
        result = await PersonaJobRepository.get_by_id(
            db_session, pj_a.id, user_id=user_a.id
        )
        assert result is not None
        assert result.is_favorite is True
        assert result.status == "Discovered"


class TestBulkUpdateStatus:
    """Test PersonaJobRepository.bulk_update_status()."""

    async def test_updates_multiple(
        self,
        db_session: AsyncSession,
        persona_a: Persona,
        user_a: User,
        shared_job: JobPosting,
        shared_job_2: JobPosting,
    ):
        """Updates status for multiple persona_job IDs."""
        pj1 = PersonaJob(
            persona_id=persona_a.id,
            job_posting_id=shared_job.id,
            status="Discovered",
            discovery_method="scouter",
        )
        pj2 = PersonaJob(
            persona_id=persona_a.id,
            job_posting_id=shared_job_2.id,
            status="Discovered",
            discovery_method="pool",
        )
        db_session.add_all([pj1, pj2])
        await db_session.flush()
        await db_session.refresh(pj1)
        await db_session.refresh(pj2)

        count = await PersonaJobRepository.bulk_update_status(
            db_session,
            persona_job_ids=[pj1.id, pj2.id],
            user_id=user_a.id,
            status="Dismissed",
        )
        assert count == 2

    async def test_skips_wrong_user(
        self, db_session: AsyncSession, pj_a: PersonaJob, other_user: User
    ):
        """Bulk update ignores IDs not owned by user."""
        count = await PersonaJobRepository.bulk_update_status(
            db_session,
            persona_job_ids=[pj_a.id],
            user_id=other_user.id,
            status="Dismissed",
        )
        assert count == 0

    async def test_empty_ids_returns_zero(self, db_session: AsyncSession, user_a: User):
        """Empty ID list returns 0."""
        count = await PersonaJobRepository.bulk_update_status(
            db_session,
            persona_job_ids=[],
            user_id=user_a.id,
            status="Dismissed",
        )
        assert count == 0


class TestBulkUpdateFavorite:
    """Test PersonaJobRepository.bulk_update_favorite()."""

    async def test_sets_favorite_true(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Bulk favorite sets is_favorite=True."""
        count = await PersonaJobRepository.bulk_update_favorite(
            db_session,
            persona_job_ids=[pj_a.id],
            user_id=user_a.id,
            is_favorite=True,
        )
        assert count == 1
        await db_session.refresh(pj_a)
        assert pj_a.is_favorite is True

    async def test_sets_favorite_false(
        self, db_session: AsyncSession, pj_a: PersonaJob, user_a: User
    ):
        """Bulk unfavorite sets is_favorite=False."""
        pj_a.is_favorite = True
        await db_session.flush()

        count = await PersonaJobRepository.bulk_update_favorite(
            db_session,
            persona_job_ids=[pj_a.id],
            user_id=user_a.id,
            is_favorite=False,
        )
        assert count == 1
        await db_session.refresh(pj_a)
        assert pj_a.is_favorite is False

    async def test_skips_wrong_user(
        self, db_session: AsyncSession, pj_a: PersonaJob, other_user: User
    ):
        """Bulk favorite ignores IDs not owned by user."""
        count = await PersonaJobRepository.bulk_update_favorite(
            db_session,
            persona_job_ids=[pj_a.id],
            user_id=other_user.id,
            is_favorite=True,
        )
        assert count == 0
