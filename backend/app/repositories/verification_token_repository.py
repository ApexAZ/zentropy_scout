"""Repository for VerificationToken CRUD operations.

REQ-013 §4.4, §6.4: Single-use magic link tokens stored as hashed values
with composite key (identifier, token) and time-limited expiry.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_token import VerificationToken


class VerificationTokenRepository:
    """Stateless repository for VerificationToken table operations.

    All methods are static — no instance state.
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        identifier: str,
        token_hash: str,
        expires: datetime,
    ) -> VerificationToken:
        """Store a new verification token.

        Args:
            db: Async database session.
            identifier: Email address.
            token_hash: SHA-256 hash of the plain token.
            expires: Token expiry timestamp.

        Returns:
            Created VerificationToken.
        """
        vt = VerificationToken(
            identifier=identifier,
            token=token_hash,
            expires=expires,
        )
        db.add(vt)
        await db.flush()
        # No server-generated fields to refresh (no UUID, no timestamps)
        return vt

    @staticmethod
    async def get(
        db: AsyncSession,
        *,
        identifier: str,
        token_hash: str,
    ) -> VerificationToken | None:
        """Look up a token by composite key.

        Args:
            db: Async database session.
            identifier: Email address.
            token_hash: SHA-256 hash of the plain token.

        Returns:
            VerificationToken if found, None otherwise.
        """
        stmt = select(VerificationToken).where(
            VerificationToken.identifier == identifier,
            VerificationToken.token == token_hash,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(
        db: AsyncSession,
        *,
        identifier: str,
        token_hash: str,
    ) -> None:
        """Delete a token (single-use cleanup).

        Args:
            db: Async database session.
            identifier: Email address.
            token_hash: SHA-256 hash of the plain token.
        """
        stmt = delete(VerificationToken).where(
            VerificationToken.identifier == identifier,
            VerificationToken.token == token_hash,
        )
        await db.execute(stmt)

    @staticmethod
    async def delete_all_for_identifier(
        db: AsyncSession,
        *,
        identifier: str,
    ) -> None:
        """Delete all tokens for an identifier (cleanup on successful verify).

        Args:
            db: Async database session.
            identifier: Email address.
        """
        stmt = delete(VerificationToken).where(
            VerificationToken.identifier == identifier,
        )
        await db.execute(stmt)

    @staticmethod
    async def delete_expired(db: AsyncSession) -> int:
        """Delete all expired tokens (periodic cleanup).

        Args:
            db: Async database session.

        Returns:
            Number of deleted rows.
        """
        stmt = delete(VerificationToken).where(
            VerificationToken.expires < datetime.now(UTC),
        )
        result = await db.execute(stmt)
        row_count: int = result.rowcount  # type: ignore[attr-defined]
        return row_count
