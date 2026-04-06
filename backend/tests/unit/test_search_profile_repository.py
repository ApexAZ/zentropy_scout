"""Tests for SearchProfileRepository CRUD operations.

REQ-034 §4.2: Verifies get_by_persona_id, create, update, and upsert methods
against a live PostgreSQL session. All tests are integration-level — they
exercise the real schema including UNIQUE constraints and JSONB storage.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import (
    SearchBucketSchema,
    SearchProfileCreate,
    SearchProfileUpdate,
)

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")

_FIT_BUCKET = SearchBucketSchema(
    label="Senior Software Engineer",
    keywords=["python", "fastapi"],
    titles=["Senior Software Engineer", "Staff Engineer"],
    remoteok_tags=["python", "senior"],
)
_STRETCH_BUCKET = SearchBucketSchema(
    label="Engineering Manager",
    keywords=["engineering manager", "team lead"],
    titles=["Engineering Manager", "Director of Engineering"],
    remoteok_tags=["manager", "senior"],
)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_create(persona_id: uuid.UUID, **overrides: object) -> SearchProfileCreate:
    """Build a minimal valid SearchProfileCreate for a given persona."""
    defaults: dict[str, Any] = {
        "persona_id": persona_id,
        "fit_searches": [_FIT_BUCKET],
        "stretch_searches": [_STRETCH_BUCKET],
        "persona_fingerprint": "a" * 64,
        "is_stale": False,
    }
    defaults.update(overrides)
    return SearchProfileCreate(**defaults)


# =============================================================================
# get_by_persona_id
# =============================================================================


class TestGetByPersonaId:
    """Tests for SearchProfileRepository.get_by_persona_id()."""

    async def test_returns_profile_when_exists(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """Returns the SearchProfile for a persona that has one."""
        await SearchProfileRepository.create(db_session, _make_create(test_persona.id))
        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, test_persona.id
        )
        assert profile is not None
        assert profile.persona_id == test_persona.id

    async def test_returns_none_when_not_exists(self, db_session: AsyncSession) -> None:
        """Returns None for a persona_id with no associated profile."""
        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, _MISSING_UUID
        )
        assert profile is None


# =============================================================================
# create
# =============================================================================


class TestCreate:
    """Tests for SearchProfileRepository.create()."""

    async def test_creates_profile_with_required_fields(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """create() persists the profile and returns it with a generated id."""
        data = _make_create(test_persona.id)
        profile = await SearchProfileRepository.create(db_session, data)
        assert profile.id is not None
        assert profile.persona_id == test_persona.id

    async def test_stores_fit_searches_buckets(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """fit_searches JSONB list is stored and retrievable."""
        data = _make_create(test_persona.id)
        profile = await SearchProfileRepository.create(db_session, data)
        assert len(profile.fit_searches) == 1
        assert profile.fit_searches[0]["label"] == "Senior Software Engineer"

    async def test_stores_stretch_searches_buckets(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """stretch_searches JSONB list is stored and retrievable."""
        data = _make_create(test_persona.id)
        profile = await SearchProfileRepository.create(db_session, data)
        assert len(profile.stretch_searches) == 1
        assert profile.stretch_searches[0]["label"] == "Engineering Manager"

    async def test_stores_persona_fingerprint(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """persona_fingerprint is stored as provided."""
        data = _make_create(test_persona.id, persona_fingerprint="b" * 64)
        profile = await SearchProfileRepository.create(db_session, data)
        assert profile.persona_fingerprint == "b" * 64

    async def test_stores_is_stale_false(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """is_stale=False is stored correctly."""
        data = _make_create(test_persona.id, is_stale=False)
        profile = await SearchProfileRepository.create(db_session, data)
        assert profile.is_stale is False

    async def test_stores_is_stale_true(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """is_stale=True is stored correctly."""
        data = _make_create(test_persona.id, is_stale=True)
        profile = await SearchProfileRepository.create(db_session, data)
        assert profile.is_stale is True

    async def test_unique_constraint_rejects_duplicate_persona(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """UNIQUE(persona_id) rejects a second profile for the same persona."""
        await SearchProfileRepository.create(db_session, _make_create(test_persona.id))
        await db_session.flush()

        with pytest.raises(IntegrityError):
            await SearchProfileRepository.create(
                db_session, _make_create(test_persona.id)
            )


# =============================================================================
# update
# =============================================================================


class TestUpdate:
    """Tests for SearchProfileRepository.update()."""

    async def test_sets_is_stale_true(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """update() sets is_stale=True on an existing profile."""
        profile = await SearchProfileRepository.create(
            db_session, _make_create(test_persona.id, is_stale=False)
        )
        updated = await SearchProfileRepository.update(
            db_session, profile.id, SearchProfileUpdate(is_stale=True)
        )
        assert updated is not None
        assert updated.is_stale is True

    async def test_sets_approved_at(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """update() sets approved_at to the provided datetime."""
        now = datetime.now(UTC).replace(microsecond=0)
        profile = await SearchProfileRepository.create(
            db_session, _make_create(test_persona.id)
        )
        updated = await SearchProfileRepository.update(
            db_session, profile.id, SearchProfileUpdate(approved_at=now)
        )
        assert updated is not None
        assert updated.approved_at is not None
        assert updated.approved_at.replace(microsecond=0) == now

    async def test_replaces_fit_searches(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """update() replaces fit_searches with the new bucket list."""
        profile = await SearchProfileRepository.create(
            db_session, _make_create(test_persona.id)
        )
        new_buckets = [
            SearchBucketSchema(
                label="New Role",
                keywords=["new"],
                titles=["New"],
                remoteok_tags=["new"],
            )
        ]
        updated = await SearchProfileRepository.update(
            db_session, profile.id, SearchProfileUpdate(fit_searches=new_buckets)
        )
        assert updated is not None
        assert len(updated.fit_searches) == 1
        assert updated.fit_searches[0]["label"] == "New Role"

    async def test_returns_none_for_unknown_profile_id(
        self, db_session: AsyncSession
    ) -> None:
        """update() returns None when the profile_id does not exist."""
        result = await SearchProfileRepository.update(
            db_session, _MISSING_UUID, SearchProfileUpdate(is_stale=True)
        )
        assert result is None

    async def test_partial_update_leaves_other_fields_unchanged(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """Updating one field does not change other fields."""
        data = _make_create(test_persona.id, persona_fingerprint="c" * 64)
        profile = await SearchProfileRepository.create(db_session, data)

        await SearchProfileRepository.update(
            db_session, profile.id, SearchProfileUpdate(is_stale=True)
        )
        refreshed = await SearchProfileRepository.get_by_persona_id(
            db_session, test_persona.id
        )
        assert refreshed is not None
        assert refreshed.persona_fingerprint == "c" * 64
        assert refreshed.is_stale is True


# =============================================================================
# upsert
# =============================================================================


class TestUpsert:
    """Tests for SearchProfileRepository.upsert()."""

    async def test_creates_profile_when_none_exists(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """upsert() creates a new profile when persona has none."""
        data = _make_create(test_persona.id)
        profile = await SearchProfileRepository.upsert(
            db_session, test_persona.id, data
        )
        assert profile.id is not None
        assert profile.persona_id == test_persona.id
        assert profile.persona_fingerprint == "a" * 64

    async def test_updates_existing_profile_on_upsert(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """upsert() updates an existing profile when persona already has one."""
        original = await SearchProfileRepository.create(
            db_session, _make_create(test_persona.id, persona_fingerprint="a" * 64)
        )
        original_id = original.id

        new_data = _make_create(test_persona.id, persona_fingerprint="b" * 64)
        updated = await SearchProfileRepository.upsert(
            db_session, test_persona.id, new_data
        )
        # Same row (same primary key), updated fingerprint
        assert updated.id == original_id
        assert updated.persona_fingerprint == "b" * 64

    async def test_upsert_returns_profile_with_new_fit_searches(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """upsert() with new fit_searches replaces the bucket list."""
        await SearchProfileRepository.create(db_session, _make_create(test_persona.id))
        new_buckets = [
            SearchBucketSchema(
                label="Upserted Role",
                keywords=["upsert"],
                titles=["Upserted Role"],
                remoteok_tags=["upsert"],
            )
        ]
        new_data = _make_create(test_persona.id, fit_searches=new_buckets)
        profile = await SearchProfileRepository.upsert(
            db_session, test_persona.id, new_data
        )
        assert profile.fit_searches[0]["label"] == "Upserted Role"

    async def test_upsert_updates_all_mutable_fields(
        self, db_session: AsyncSession, test_persona
    ) -> None:
        """upsert() updates fit/stretch searches, fingerprint, stale flag, and timestamps."""
        now = datetime.now(UTC).replace(microsecond=0)
        await SearchProfileRepository.create(
            db_session,
            _make_create(test_persona.id, persona_fingerprint="a" * 64, is_stale=False),
        )
        new_buckets = [
            SearchBucketSchema(
                label="New Role", keywords=[], titles=[], remoteok_tags=[]
            )
        ]
        new_data = _make_create(
            test_persona.id,
            fit_searches=new_buckets,
            stretch_searches=new_buckets,
            persona_fingerprint="b" * 64,
            is_stale=True,
            generated_at=now,
            approved_at=now,
        )
        updated = await SearchProfileRepository.upsert(
            db_session, test_persona.id, new_data
        )
        assert updated.fit_searches[0]["label"] == "New Role"
        assert updated.stretch_searches[0]["label"] == "New Role"
        assert updated.persona_fingerprint == "b" * 64
        assert updated.is_stale is True
        assert updated.generated_at is not None
        assert updated.approved_at is not None
