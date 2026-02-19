"""Tests for AccountRepository.

REQ-013 §5, §6.2: Tests cover Account CRUD operations,
unique constraint, and provider lookup.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.account_repository import AccountRepository

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")


class TestCreate:
    """Test AccountRepository.create()."""

    async def test_creates_account_with_required_fields(
        self, db_session: AsyncSession, test_user
    ):
        """Minimal creation with required fields."""
        account = await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="google",
            provider_account_id="google-sub-123",
        )
        assert account.id is not None
        assert account.user_id == test_user.id
        assert account.type == "oauth"
        assert account.provider == "google"
        assert account.provider_account_id == "google-sub-123"

    async def test_creates_account_with_optional_fields(
        self, db_session: AsyncSession, test_user
    ):
        """Creation with OAuth tokens populated."""
        account = await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="google",
            provider_account_id="google-sub-456",
            refresh_token="refresh-tok",
            access_token="access-tok",
            expires_at=1700000000,
            token_type="bearer",
            scope="openid email profile",
            id_token="id-tok-jwt",
        )
        assert account.refresh_token == "refresh-tok"
        assert account.access_token == "access-tok"
        assert account.expires_at == 1700000000
        assert account.token_type == "bearer"
        assert account.scope == "openid email profile"
        assert account.id_token == "id-tok-jwt"

    async def test_rejects_duplicate_provider_account(
        self, db_session: AsyncSession, test_user
    ):
        """UNIQUE(provider, provider_account_id) prevents duplicate links."""
        await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="google",
            provider_account_id="same-id",
        )
        await db_session.flush()

        with pytest.raises(IntegrityError):
            await AccountRepository.create(
                db_session,
                user_id=test_user.id,
                type="oauth",
                provider="google",
                provider_account_id="same-id",
            )

    async def test_allows_same_account_id_different_provider(
        self, db_session: AsyncSession, test_user
    ):
        """Same provider_account_id on different providers is allowed."""
        await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="google",
            provider_account_id="shared-id",
        )
        await db_session.flush()

        account = await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="linkedin",
            provider_account_id="shared-id",
        )
        assert account.provider == "linkedin"


class TestGetByProviderAndAccountId:
    """Test AccountRepository.get_by_provider_and_account_id()."""

    async def test_returns_account_when_found(
        self, db_session: AsyncSession, test_user
    ):
        """Existing account is returned by provider + account ID."""
        created = await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="google",
            provider_account_id="find-me-123",
        )
        await db_session.flush()

        found = await AccountRepository.get_by_provider_and_account_id(
            db_session, "google", "find-me-123"
        )
        assert found is not None
        assert found.id == created.id
        assert found.user_id == test_user.id

    async def test_returns_none_when_not_found(self, db_session: AsyncSession):
        """Non-existent provider + account ID returns None."""
        found = await AccountRepository.get_by_provider_and_account_id(
            db_session, "google", "does-not-exist"
        )
        assert found is None


class TestGetAccountsByUserId:
    """Test AccountRepository.get_accounts_by_user_id()."""

    async def test_returns_all_accounts_for_user(
        self, db_session: AsyncSession, test_user
    ):
        """All accounts linked to a user are returned."""
        await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="google",
            provider_account_id="g-123",
        )
        await AccountRepository.create(
            db_session,
            user_id=test_user.id,
            type="oauth",
            provider="linkedin",
            provider_account_id="li-456",
        )
        await db_session.flush()

        accounts = await AccountRepository.get_accounts_by_user_id(
            db_session, test_user.id
        )
        assert len(accounts) == 2
        providers = {a.provider for a in accounts}
        assert providers == {"google", "linkedin"}

    async def test_returns_empty_list_for_no_accounts(self, db_session: AsyncSession):
        """User with no accounts returns empty list."""
        accounts = await AccountRepository.get_accounts_by_user_id(
            db_session, _MISSING_UUID
        )
        assert accounts == []
