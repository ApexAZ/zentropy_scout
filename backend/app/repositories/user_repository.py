"""Repository for User CRUD operations.

REQ-013 §7.5, REQ-005 §4.0: Provides database access for the users table.
First repository class — establishes the pattern for all future repositories.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

# Fields that may be updated via UserRepository.update().
# Security: Never add 'id', 'email', 'created_at', or 'updated_at'.
# - id: primary key, immutable
# - email: unique identity, requires dedicated flow with re-verification
# - created_at/updated_at: server-managed timestamps
# Security: is_admin is excluded to prevent mass-assignment privilege escalation.
# Use set_admin() for explicit admin promotion (REQ-022 §5.1).
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "email_verified",
        "image",
        "password_hash",
        "token_invalidated_before",
    }
)


class UserRepository:
    """Stateless repository for User table operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.
    """

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key.

        Args:
            db: Async database session.
            user_id: UUID primary key.

        Returns:
            User if found, None otherwise.
        """
        return await db.get(User, user_id)

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """Fetch a user by email address (case-insensitive).

        Args:
            db: Async database session.
            email: Email address to look up.

        Returns:
            User if found, None otherwise.
        """
        stmt = select(User).where(User.email == email.lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        email: str,
        name: str | None = None,
        password_hash: str | None = None,
        email_verified: datetime | None = None,
        image: str | None = None,
    ) -> User:
        """Create a new user.

        Email is normalized to lowercase before storage.

        Args:
            db: Async database session.
            email: User email address.
            name: Display name.
            password_hash: bcrypt hash (None for OAuth-only users).
            email_verified: Timestamp when email was verified.
            image: Profile picture URL.

        Returns:
            Created User with database-generated fields populated.

        Raises:
            sqlalchemy.exc.IntegrityError: If email already exists.
        """
        user = User(
            email=email.lower(),
            name=name,
            password_hash=password_hash,
            email_verified=email_verified,
            image=image,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def update(
        db: AsyncSession,
        user_id: uuid.UUID,
        **kwargs: str | datetime | bool | None,
    ) -> User | None:
        """Update user fields.

        Only fields in _UPDATABLE_FIELDS are allowed. Unknown field names
        raise ValueError.

        Args:
            db: Async database session.
            user_id: UUID of the user to update.
            **kwargs: Field names and values to update.

        Returns:
            Updated User if found, None if user does not exist.

        Raises:
            ValueError: If an unknown field name is passed.
        """
        unknown = set(kwargs) - _UPDATABLE_FIELDS
        if unknown:
            msg = f"Unknown fields: {', '.join(sorted(unknown))}"
            raise ValueError(msg)

        user = await db.get(User, user_id)
        if user is None:
            return None

        for field, value in kwargs.items():
            setattr(user, field, value)

        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_admin(
        db: AsyncSession, user_id: uuid.UUID, *, is_admin: bool
    ) -> User | None:
        """Set admin status for a user.

        REQ-022 §5.1: Separated from update() to prevent mass-assignment
        privilege escalation. Only call from explicit admin promotion paths.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            is_admin: New admin status.

        Returns:
            Updated User if found, None if user does not exist.
        """
        user = await db.get(User, user_id)
        if user is None:
            return None
        user.is_admin = is_admin
        await db.flush()
        await db.refresh(user)
        return user
