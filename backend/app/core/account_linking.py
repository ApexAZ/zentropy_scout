"""Account linking logic for OAuth and magic link authentication.

REQ-013 §5: Automatic linking by verified email with pre-hijack defense.
Shared between OAuth callback and magic link verification endpoints.

Rules:
1. If provider+account_id already exists → returning user (no linking needed)
2. If email exists AND both sides verified → link accounts (same user)
3. If email exists but either side unverified → REJECT (pre-hijack defense)
4. If no matching email → create new user
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.account_repository import AccountRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AccountLinkingBlockedError(Exception):
    """Raised when account linking is blocked by email verification rules.

    Pre-hijack defense: an account with the same email exists but one
    or both sides haven't verified the email, so linking is unsafe.
    """


async def find_or_create_user_for_oauth(
    *,
    db: AsyncSession,
    email: str,
    email_verified_by_provider: bool,
    provider: str,
    provider_account_id: str,
    name: str | None = None,
    image: str | None = None,
) -> tuple[User, bool]:
    """Find or create a user for an OAuth/magic-link authentication.

    Implements the account linking logic from REQ-013 §5:
    - Returning users: matched by provider + provider_account_id
    - Account linking: matched by verified email (both sides must be verified)
    - Pre-hijack defense: unverified emails never trigger linking

    Args:
        db: Async database session.
        email: Email address from the identity provider.
        email_verified_by_provider: Whether the provider verified this email.
        provider: Provider name (e.g., "google", "linkedin").
        provider_account_id: Provider's unique user identifier.
        name: Display name from provider (optional).
        image: Profile picture URL from provider (optional).

    Returns:
        Tuple of (User, created) where created is True if a new user was made.
    """
    # Normalize email early for consistent matching
    email = email.strip().lower()

    # Step 1: Check if this provider+account_id already exists (returning user)
    existing_account = await AccountRepository.get_by_provider_and_account_id(
        db, provider, provider_account_id
    )
    if existing_account:
        user = await UserRepository.get_by_id(db, existing_account.user_id)
        if user:
            logger.info(
                "Returning OAuth user",
                extra={"user_id": str(user.id), "provider": provider},
            )
            return user, False

    # Step 2: Check if email exists for potential account linking
    existing_user = await UserRepository.get_by_email(db, email)

    if existing_user:
        # Security: Only link if BOTH the provider AND existing account verify email
        # Pre-hijack defense: prevents attacker from pre-registering with victim's
        # email and having the victim's OAuth login merge into attacker's account
        can_link = (
            email_verified_by_provider and existing_user.email_verified is not None
        )

        if can_link:
            # Link this provider to the existing user
            await AccountRepository.create(
                db,
                user_id=existing_user.id,
                type="oauth",
                provider=provider,
                provider_account_id=provider_account_id,
            )
            logger.info(
                "Linked OAuth account to existing user",
                extra={
                    "user_id": str(existing_user.id),
                    "provider": provider,
                },
            )
            return existing_user, False

        # Cannot link — email verification check failed.
        # Cannot create new user either (email unique constraint).
        # Reject the login to prevent pre-hijack attacks.
        logger.warning(
            "OAuth account linking blocked by email verification",
            extra={
                "provider": provider,
                "provider_verified": email_verified_by_provider,
                "existing_verified": existing_user.email_verified is not None,
            },
        )
        msg = (
            "Account linking blocked by email verification. "
            "Please sign in with your original method first."
        )
        raise AccountLinkingBlockedError(msg)

    # Step 3: Create new user + account
    new_user = await UserRepository.create(
        db,
        email=email,
        name=name,
        image=image,
        email_verified=datetime.now(UTC) if email_verified_by_provider else None,
    )

    await AccountRepository.create(
        db,
        user_id=new_user.id,
        type="oauth",
        provider=provider,
        provider_account_id=provider_account_id,
    )

    logger.info(
        "Created new OAuth user",
        extra={"user_id": str(new_user.id), "provider": provider},
    )
    return new_user, True
