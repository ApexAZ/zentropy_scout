"""Repository for PersonaJob per-user operations.

REQ-015 §8, §9: Per-user job relationship management.
All read/write operations are scoped to user_id via Persona JOIN.
"""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.persona import Persona
from app.models.persona_job import PersonaJob

# Fields that may be updated via PersonaJobRepository.update().
# Security: Never allow updating id, persona_id, job_posting_id, or timestamps.
# - id: primary key, immutable
# - persona_id: FK, set at creation (changing would break ownership)
# - job_posting_id: FK, set at creation (changing would break the link)
# - created_at/updated_at: server-managed timestamps
# - discovered_at: set at creation, immutable
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "status",
        "is_favorite",
        "dismissed_at",
        "fit_score",
        "stretch_score",
        "failed_non_negotiables",
        "score_details",
        "scored_at",
    }
)


class PersonaJobRepository:
    """Stateless repository for PersonaJob per-user operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.

    All query methods that accept user_id JOIN through Persona to
    verify ownership. This prevents cross-tenant data access.
    """

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        persona_job_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> PersonaJob | None:
        """Fetch a PersonaJob by ID, scoped to user.

        Args:
            db: Async database session.
            persona_job_id: UUID primary key.
            user_id: Authenticated user's UUID (ownership check).

        Returns:
            PersonaJob if found and owned by user, None otherwise.
        """
        stmt = (
            select(PersonaJob)
            .join(Persona, PersonaJob.persona_id == Persona.id)
            .where(PersonaJob.id == persona_job_id, Persona.user_id == user_id)
            .options(selectinload(PersonaJob.job_posting))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_for_user(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> list[PersonaJob]:
        """Fetch all PersonaJob records for a user across all personas.

        Args:
            db: Async database session.
            user_id: Authenticated user's UUID.

        Returns:
            List of PersonaJob records with job_posting eagerly loaded.
            Ordered by discovered_at descending.
        """
        stmt = (
            select(PersonaJob)
            .join(Persona, PersonaJob.persona_id == Persona.id)
            .where(Persona.user_id == user_id)
            .options(selectinload(PersonaJob.job_posting))
            .order_by(PersonaJob.discovered_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_for_persona(
        db: AsyncSession,
        *,
        persona_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[PersonaJob]:
        """Fetch all PersonaJob records for a persona, scoped to user.

        Args:
            db: Async database session.
            persona_id: UUID of the persona.
            user_id: Authenticated user's UUID (ownership check).

        Returns:
            List of PersonaJob records. Empty if persona not owned by user.
        """
        stmt = (
            select(PersonaJob)
            .join(Persona, PersonaJob.persona_id == Persona.id)
            .where(PersonaJob.persona_id == persona_id, Persona.user_id == user_id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_persona_and_job(
        db: AsyncSession,
        *,
        persona_id: uuid.UUID,
        job_posting_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> PersonaJob | None:
        """Fetch a PersonaJob by persona + job posting pair.

        Used for dedup link checks. When called from user-facing code,
        pass user_id to enforce ownership. System-level callers (dedup,
        surfacing worker) pass user_id=None.

        Args:
            db: Async database session.
            persona_id: UUID of the persona.
            job_posting_id: UUID of the job posting.
            user_id: Optional user UUID for ownership verification.
                Pass None for system-level operations only.

        Returns:
            PersonaJob if link exists (and owned, if user_id given),
            None otherwise.
        """
        stmt = select(PersonaJob).where(
            PersonaJob.persona_id == persona_id,
            PersonaJob.job_posting_id == job_posting_id,
        )
        if user_id is not None:
            stmt = stmt.join(Persona, PersonaJob.persona_id == Persona.id).where(
                Persona.user_id == user_id
            )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        persona_id: uuid.UUID,
        job_posting_id: uuid.UUID,
        discovery_method: str,
        user_id: uuid.UUID | None = None,
        status: str = "Discovered",
        is_favorite: bool = False,
        fit_score: int | None = None,
        stretch_score: int | None = None,
        failed_non_negotiables: list | None = None,
        score_details: dict | None = None,
    ) -> PersonaJob | None:
        """Create a new PersonaJob link.

        When called from user-facing code, pass user_id to verify
        persona ownership. System-level callers (surfacing worker)
        pass user_id=None.

        Args:
            db: Async database session.
            persona_id: FK to personas.
            job_posting_id: FK to job_postings.
            discovery_method: How the job was discovered (scouter/manual/pool).
            user_id: Optional user UUID for ownership verification.
                Pass None for system-level operations only.
            status: Initial status. Defaults to Discovered.
            is_favorite: Whether the user favorited this job.
            fit_score: Initial fit score (0-100 or None).
            stretch_score: Initial stretch score (0-100 or None).
            failed_non_negotiables: List of failed non-negotiable criteria.
            score_details: Detailed scoring breakdown.

        Returns:
            Created PersonaJob with database-generated fields populated,
            or None if user_id is given and persona is not owned.

        Raises:
            sqlalchemy.exc.IntegrityError: If (persona_id, job_posting_id)
                already exists (UNIQUE constraint).
        """
        if user_id is not None:
            ownership = await db.execute(
                select(Persona.id).where(
                    Persona.id == persona_id, Persona.user_id == user_id
                )
            )
            if ownership.scalar_one_or_none() is None:
                return None

        persona_job = PersonaJob(
            persona_id=persona_id,
            job_posting_id=job_posting_id,
            discovery_method=discovery_method,
            status=status,
            is_favorite=is_favorite,
            fit_score=fit_score,
            stretch_score=stretch_score,
            failed_non_negotiables=failed_non_negotiables,
            score_details=score_details,
        )
        db.add(persona_job)
        await db.flush()
        await db.refresh(persona_job)
        return persona_job

    @staticmethod
    async def update(
        db: AsyncSession,
        persona_job_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        **kwargs: str | int | bool | datetime | dict | list | None,
    ) -> PersonaJob | None:
        """Update PersonaJob fields, scoped to user.

        Only fields in _UPDATABLE_FIELDS are allowed. Unknown field names
        raise ValueError.

        Args:
            db: Async database session.
            persona_job_id: UUID of the PersonaJob to update.
            user_id: Authenticated user's UUID (ownership check).
            **kwargs: Field names and values to update.

        Returns:
            Updated PersonaJob if found and owned, None otherwise.

        Raises:
            ValueError: If an unknown field name is passed.
        """
        unknown = set(kwargs) - _UPDATABLE_FIELDS
        if unknown:
            msg = f"Unknown fields: {', '.join(sorted(unknown))}"
            raise ValueError(msg)

        # Fetch with ownership check
        stmt = (
            select(PersonaJob)
            .join(Persona, PersonaJob.persona_id == Persona.id)
            .where(PersonaJob.id == persona_job_id, Persona.user_id == user_id)
            .options(selectinload(PersonaJob.job_posting))
        )
        result = await db.execute(stmt)
        persona_job = result.scalar_one_or_none()
        if persona_job is None:
            return None

        for field, value in kwargs.items():
            setattr(persona_job, field, value)

        await db.flush()
        await db.refresh(persona_job)
        return persona_job

    @staticmethod
    async def bulk_update_status(
        db: AsyncSession,
        *,
        persona_job_ids: list[uuid.UUID],
        user_id: uuid.UUID,
        status: str,
        dismissed_at: datetime | None = None,
    ) -> int:
        """Bulk update status for multiple PersonaJob records.

        Only updates records owned by the authenticated user.

        Args:
            db: Async database session.
            persona_job_ids: List of PersonaJob UUIDs to update.
            user_id: Authenticated user's UUID (ownership filter).
            status: New status value.
            dismissed_at: Timestamp for dismissal (auto-set by caller
                when status is Dismissed).

        Returns:
            Number of records updated.
        """
        if not persona_job_ids:
            return 0

        # Subquery: persona IDs owned by this user
        owned_persona_ids = select(Persona.id).where(Persona.user_id == user_id)

        values: dict[str, str | datetime] = {"status": status}
        if dismissed_at is not None:
            values["dismissed_at"] = dismissed_at

        stmt = (
            update(PersonaJob)
            .where(
                PersonaJob.id.in_(persona_job_ids),
                PersonaJob.persona_id.in_(owned_persona_ids),
            )
            .values(**values)
        )
        result = cast(CursorResult[Any], await db.execute(stmt))
        row_count: int = result.rowcount
        return row_count

    @staticmethod
    async def bulk_update_favorite(
        db: AsyncSession,
        *,
        persona_job_ids: list[uuid.UUID],
        user_id: uuid.UUID,
        is_favorite: bool,
    ) -> int:
        """Bulk update is_favorite for multiple PersonaJob records.

        Only updates records owned by the authenticated user.

        Args:
            db: Async database session.
            persona_job_ids: List of PersonaJob UUIDs to update.
            user_id: Authenticated user's UUID (ownership filter).
            is_favorite: New favorite value.

        Returns:
            Number of records updated.
        """
        if not persona_job_ids:
            return 0

        # Subquery: persona IDs owned by this user
        owned_persona_ids = select(Persona.id).where(Persona.user_id == user_id)

        stmt = (
            update(PersonaJob)
            .where(
                PersonaJob.id.in_(persona_job_ids),
                PersonaJob.persona_id.in_(owned_persona_ids),
            )
            .values(is_favorite=is_favorite)
        )
        result = cast(CursorResult[Any], await db.execute(stmt))
        row_count: int = result.rowcount
        return row_count
