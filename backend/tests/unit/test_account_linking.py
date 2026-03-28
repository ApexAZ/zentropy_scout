"""Tests for OAuth account linking logic.

REQ-013 §5: Account linking by verified email with pre-hijack defense.
Shared logic used by OAuth callback and magic link verification.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_linking import (
    AccountLinkingBlockedError,
    find_or_create_user_for_oauth,
)
from app.repositories.account_repository import AccountRepository
from app.repositories.user_repository import UserRepository


class TestNewUserCreation:
    """Test user creation when no matching email exists."""

    async def test_creates_new_user_when_no_existing_email(
        self, db_session: AsyncSession
    ):
        """New email creates a new user + account record."""
        user, created = await find_or_create_user_for_oauth(
            db=db_session,
            email="newuser@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="google-new-123",
            name="New User",
            image="https://example.com/photo.jpg",
        )
        assert created is True
        assert user.email == "newuser@example.com"
        assert user.name == "New User"
        assert user.image == "https://example.com/photo.jpg"
        assert user.email_verified is not None

    async def test_new_user_has_account_record(self, db_session: AsyncSession):
        """New user creation also creates an account record."""
        user, _ = await find_or_create_user_for_oauth(
            db=db_session,
            email="withaccount@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="google-acc-456",
        )
        account = await AccountRepository.get_by_provider_and_account_id(
            db_session, "google", "google-acc-456"
        )
        assert account is not None
        assert account.user_id == user.id

    async def test_email_verified_set_when_provider_verifies(
        self, db_session: AsyncSession
    ):
        """email_verified is set when provider reports email as verified."""
        user, _ = await find_or_create_user_for_oauth(
            db=db_session,
            email="verified@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="google-ver-789",
        )
        assert user.email_verified is not None

    async def test_email_not_verified_when_provider_does_not_verify(
        self, db_session: AsyncSession
    ):
        """email_verified is NULL when provider does not verify email."""
        user, _ = await find_or_create_user_for_oauth(
            db=db_session,
            email="unverified@example.com",
            email_verified_by_provider=False,
            provider="google",
            provider_account_id="google-unv-101",
        )
        assert user.email_verified is None


class TestAccountLinking:
    """Test linking to existing user with verified email."""

    async def test_links_when_both_sides_verified(self, db_session: AsyncSession):
        """Links to existing user when both provider and user have verified email."""
        # Create existing user with verified email
        existing = await UserRepository.create(
            db_session,
            email="jane@example.com",
            email_verified=datetime.now(UTC),
        )
        await db_session.flush()

        user, created = await find_or_create_user_for_oauth(
            db=db_session,
            email="jane@example.com",
            email_verified_by_provider=True,
            provider="linkedin",
            provider_account_id="li-jane-123",
            name="Jane",
        )
        assert created is False
        assert user.id == existing.id

        # Verify account record was created
        account = await AccountRepository.get_by_provider_and_account_id(
            db_session, "linkedin", "li-jane-123"
        )
        assert account is not None
        assert account.user_id == existing.id


class TestPreHijackDefense:
    """Test pre-hijack defense per REQ-013 §3.5, §5.2.

    When email exists but verification check fails, the login is rejected
    (raises AccountLinkingBlockedError) to prevent account takeover.
    """

    async def test_rejects_when_provider_email_unverified(
        self, db_session: AsyncSession
    ):
        """Unverified provider email blocks linking to existing user."""
        await UserRepository.create(
            db_session,
            email="victim@example.com",
            email_verified=datetime.now(UTC),
        )
        await db_session.flush()

        with pytest.raises(AccountLinkingBlockedError, match="email verification"):
            await find_or_create_user_for_oauth(
                db=db_session,
                email="victim@example.com",
                email_verified_by_provider=False,
                provider="linkedin",
                provider_account_id="li-attacker-1",
            )

    async def test_rejects_when_existing_email_unverified(
        self, db_session: AsyncSession
    ):
        """Unverified existing user email blocks linking."""
        await UserRepository.create(
            db_session,
            email="unver-existing@example.com",
            email_verified=None,
        )
        await db_session.flush()

        with pytest.raises(AccountLinkingBlockedError, match="email verification"):
            await find_or_create_user_for_oauth(
                db=db_session,
                email="unver-existing@example.com",
                email_verified_by_provider=True,
                provider="google",
                provider_account_id="google-attacker-2",
            )

    async def test_creates_new_user_when_unverified_email_not_in_system(
        self, db_session: AsyncSession
    ):
        """Unverified provider email for non-existent user creates new user."""
        user, created = await find_or_create_user_for_oauth(
            db=db_session,
            email="brand-new@example.com",
            email_verified_by_provider=False,
            provider="google",
            provider_account_id="google-new-unv-1",
        )
        assert created is True
        assert user.email_verified is None


class TestAccountLinkingBlockedErrorAttributes:
    """AccountLinkingBlockedError API error attributes."""

    def test_has_api_error_attributes(self) -> None:
        """AccountLinkingBlockedError should have code and status_code for API error handling."""
        error = AccountLinkingBlockedError("email verification failed")
        assert error.code == "ACCOUNT_LINKING_BLOCKED"
        assert error.status_code == 409
        assert error.message == "email verification failed"


class TestReturningUser:
    """Test returning user who already has an account for this provider."""

    async def test_returns_existing_user_when_provider_already_linked(
        self, db_session: AsyncSession
    ):
        """Returning user with existing account link is returned (not created)."""
        # Create user + account
        user, _ = await find_or_create_user_for_oauth(
            db=db_session,
            email="returning@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="google-returning-1",
            name="Returner",
        )
        await db_session.flush()

        # Same provider + account ID = returning user
        user2, created = await find_or_create_user_for_oauth(
            db=db_session,
            email="returning@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="google-returning-1",
        )
        assert created is False
        assert user2.id == user.id

    async def test_returning_user_matched_by_provider_account_id(
        self, db_session: AsyncSession
    ):
        """Returning user is matched by provider_account_id, not email."""
        # Create user with Google
        user, _ = await find_or_create_user_for_oauth(
            db=db_session,
            email="email-might-change@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="stable-google-sub",
        )
        await db_session.flush()

        # User changed their Google email but provider_account_id is stable
        user2, created = await find_or_create_user_for_oauth(
            db=db_session,
            email="changed-email@example.com",
            email_verified_by_provider=True,
            provider="google",
            provider_account_id="stable-google-sub",
        )
        assert created is False
        assert user2.id == user.id
