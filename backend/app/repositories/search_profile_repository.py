"""Repository for SearchProfile CRUD operations.

REQ-034 §4.2: One profile per persona. Provides get_by_persona_id, create,
update, and upsert methods. All methods are static — callers control
transaction boundaries via the AsyncSession they pass.

Coordinates with:
  - models/search_profile.py: SearchProfile ORM model

Called by / Used by:
  - services/discovery/search_profile_service.py: fingerprint, staleness, AI generation
  - api/v1/search_profiles.py: GET/POST/PATCH endpoints
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_profile import SearchProfile
from app.schemas.search_profile import SearchProfileCreate, SearchProfileUpdate

# Fields that can be set on an existing profile via update() or upsert().
# Immutable fields (id, persona_id, created_at) are intentionally excluded.
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "fit_searches",
        "stretch_searches",
        "persona_fingerprint",
        "is_stale",
        "generated_at",
        "approved_at",
    }
)


class SearchProfileRepository:
    """Stateless repository for SearchProfile CRUD.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.
    """

    @staticmethod
    async def get_by_persona_id(
        db: AsyncSession, persona_id: uuid.UUID
    ) -> SearchProfile | None:
        """Fetch the SearchProfile for a given persona.

        REQ-034 §4.2: One profile per persona (UNIQUE FK).

        Args:
            db: Async database session.
            persona_id: UUID of the owning persona.

        Returns:
            SearchProfile if the persona has one, None otherwise.
        """
        stmt = select(SearchProfile).where(SearchProfile.persona_id == persona_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        data: SearchProfileCreate,
    ) -> SearchProfile:
        """Create a new SearchProfile record.

        Serializes SearchBucketSchema objects in fit_searches and
        stretch_searches to plain dicts before storing in JSONB columns.

        Args:
            db: Async database session.
            data: Validated creation data including persona_id.

        Returns:
            Newly created SearchProfile with database-generated fields (id,
            created_at, updated_at) populated after flush.

        Raises:
            sqlalchemy.exc.IntegrityError: If a profile already exists for
                data.persona_id (UNIQUE constraint violation).
        """
        profile = SearchProfile(**data.model_dump())
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def update(
        db: AsyncSession,
        profile_id: uuid.UUID,
        data: SearchProfileUpdate,
    ) -> SearchProfile | None:
        """Partially update a SearchProfile by primary key.

        Only fields explicitly set in data (i.e., not None) are updated.
        Immutable fields (id, persona_id, created_at) are never modified.

        Args:
            db: Async database session.
            profile_id: UUID primary key of the profile to update.
            data: Partial update data — only non-None fields are applied.

        Returns:
            Updated SearchProfile if found, None if profile_id does not exist.
        """
        profile = await db.get(SearchProfile, profile_id)
        if profile is None:
            return None

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(profile, field, value)

        await db.flush()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def upsert(
        db: AsyncSession,
        persona_id: uuid.UUID,
        data: SearchProfileCreate,
    ) -> SearchProfile:
        """Insert or update a SearchProfile for a persona.

        If no profile exists for persona_id, creates one from data.
        If a profile already exists, replaces all updatable fields from data.

        Handles the TOCTOU race condition: if two concurrent requests both see
        no existing profile and both attempt to create, the second insert raises
        IntegrityError. A savepoint is used so only the conflicting insert rolls
        back; the outer transaction remains intact and the race winner's row is
        returned.

        Used by SearchProfileService after AI generation to persist the new
        fit/stretch buckets and updated fingerprint.

        Args:
            db: Async database session.
            persona_id: UUID of the owning persona (must equal data.persona_id).
            data: Full profile data including buckets and fingerprint.

        Returns:
            Created or updated SearchProfile with all fields populated.

        Raises:
            AssertionError: If persona_id does not match data.persona_id.
        """
        assert data.persona_id == persona_id, (
            f"persona_id mismatch: argument={persona_id}, data.persona_id={data.persona_id}"
        )

        existing = await SearchProfileRepository.get_by_persona_id(db, persona_id)
        if existing is None:
            try:
                async with db.begin_nested():
                    return await SearchProfileRepository.create(db, data)
            except IntegrityError:
                # Concurrent insert won the race — fetch the row they created.
                existing = await SearchProfileRepository.get_by_persona_id(
                    db, persona_id
                )
                if existing is None:
                    raise  # Genuine constraint error, not a race condition

        # Replace all updatable fields from the new data (all fields, including
        # those that may be set to None such as generated_at on a reset).
        updates = data.model_dump(exclude={"persona_id"})
        for field, value in updates.items():
            if field in _UPDATABLE_FIELDS:
                setattr(existing, field, value)

        await db.flush()
        await db.refresh(existing)
        return existing
