"""Tenant-scoped database session wrapper.

REQ-014 §7.3: TenantScopedSession wraps AsyncSession with automatic
user_id filtering for defense-in-depth tenant isolation.

Architecture:
    Agents currently use the API-mediated pattern (AgentAPIClient) and
    do NOT access the database directly. This wrapper exists for any
    future code that needs scoped DB access outside the API layer.

    All queries automatically filter by the user_id set at construction.
    This prevents accidental cross-tenant data access.

Usage:
    scoped = TenantScopedSession(db, user_id)
    persona = await scoped.get_persona(persona_id)  # Ownership verified
    personas = await scoped.list_personas()  # Only user's personas
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.persona import Persona


class TenantScopedSession:
    """Database session that automatically scopes queries to a user.

    Wraps an AsyncSession with a fixed user_id. All provided query
    methods include ownership filtering.

    SECURITY: Do not access ``_db`` directly from outside this class.
    All external callers should use the scoped methods which enforce
    ``WHERE persona.user_id = :uid`` filtering automatically.
    """

    __slots__ = ("_db", "_user_id")

    def __init__(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Initialize with a database session and user ID.

        Args:
            db: The async database session.
            user_id: The authenticated user's UUID for tenant scoping.
        """
        self._db = db
        self._user_id = user_id

    @property
    def user_id(self) -> uuid.UUID:
        """The authenticated user's UUID (read-only)."""
        return self._user_id

    async def get_persona(self, persona_id: uuid.UUID) -> Persona:
        """Fetch a persona with automatic ownership check (Pattern A).

        Args:
            persona_id: The persona's UUID.

        Returns:
            The Persona model instance.

        Raises:
            NotFoundError: If persona doesn't exist or belongs to another user.
        """
        result = await self._db.execute(
            select(Persona).where(
                Persona.id == persona_id,
                Persona.user_id == self._user_id,
            )
        )
        persona = result.scalar_one_or_none()
        if not persona:
            raise NotFoundError("Persona", str(persona_id))
        return persona

    async def list_personas(self) -> list[Persona]:
        """List all personas belonging to the user.

        Returns:
            List of Persona model instances owned by the user.
        """
        result = await self._db.execute(
            select(Persona)
            .where(Persona.user_id == self._user_id)
            .order_by(Persona.created_at.desc())
        )
        return list(result.scalars().all())

    async def verify_persona_ownership(self, persona_id: uuid.UUID) -> bool:
        """Check if a persona belongs to the user without raising.

        Args:
            persona_id: The persona's UUID to verify.

        Returns:
            True if the persona belongs to the user, False otherwise.
        """
        result = await self._db.execute(
            select(Persona.id).where(
                Persona.id == persona_id,
                Persona.user_id == self._user_id,
            )
        )
        return result.scalar_one_or_none() is not None
