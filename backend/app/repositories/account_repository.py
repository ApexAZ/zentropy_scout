"""Repository for Account CRUD operations.

REQ-013 §5, §6.2: Provides database access for the accounts table.
Follows the repository pattern established by UserRepository.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account


class AccountRepository:
    """Stateless repository for Account table operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        type: str,
        provider: str,
        provider_account_id: str,
        refresh_token: str | None = None,
        access_token: str | None = None,
        expires_at: int | None = None,
        token_type: str | None = None,
        scope: str | None = None,
        id_token: str | None = None,
        session_state: str | None = None,
    ) -> Account:
        """Create a new account record linking a provider to a user.

        Args:
            db: Async database session.
            user_id: FK to users table.
            type: Account type ("oauth", "email", "credentials").
            provider: Provider name ("google", "linkedin", etc.).
            provider_account_id: Provider's unique user identifier.
            refresh_token: OAuth refresh token.
            access_token: OAuth access token.
            expires_at: Token expiry (Unix timestamp).
            token_type: Token type (e.g., "bearer").
            scope: OAuth scopes granted.
            id_token: OIDC ID token.
            session_state: Provider session state.

        Returns:
            Created Account with database-generated fields populated.

        Raises:
            sqlalchemy.exc.IntegrityError: If provider+account_id already exists.
        """
        account = Account(
            user_id=user_id,
            type=type,
            provider=provider,
            provider_account_id=provider_account_id,
            refresh_token=refresh_token,
            access_token=access_token,
            expires_at=expires_at,
            token_type=token_type,
            scope=scope,
            id_token=id_token,
            session_state=session_state,
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)
        return account

    @staticmethod
    async def get_by_provider_and_account_id(
        db: AsyncSession,
        provider: str,
        provider_account_id: str,
    ) -> Account | None:
        """Find an account by provider name and provider's user ID.

        Used to identify returning users: if the provider + account ID
        already exists, we know which user this is (regardless of email).

        Args:
            db: Async database session.
            provider: Provider name (e.g., "google").
            provider_account_id: Provider's unique user identifier.

        Returns:
            Account if found, None otherwise.
        """
        stmt = select(Account).where(
            Account.provider == provider,
            Account.provider_account_id == provider_account_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_accounts_by_user_id(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[Account]:
        """List all accounts linked to a user.

        Args:
            db: Async database session.
            user_id: UUID of the user.

        Returns:
            List of Account records (may be empty).
        """
        stmt = select(Account).where(Account.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())
