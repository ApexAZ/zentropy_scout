"""Magic link + session endpoints.

REQ-013 §4.4, §7.5, §8.3a: Passwordless sign-in via email magic links,
logout, current user info, profile update, and session invalidation.

Endpoints:
- POST /auth/magic-link — request magic link email
- GET /auth/verify-magic-link — verify token, issue JWT, redirect
- POST /auth/logout — clear auth cookie
- GET /auth/me — return current user info
- PATCH /auth/profile — update user profile (name)
- POST /auth/invalidate-sessions — sign out all devices
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.responses import Response

from app.api.deps import CurrentUserId, DbSession, PasswordResetEligible
from app.core.auth import create_jwt, set_auth_cookie
from app.core.config import settings
from app.core.email import send_magic_link_email
from app.core.errors import UnauthorizedError, ValidationError
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.verification_token_repository import VerificationTokenRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# Magic link token TTL (REQ-013 §10.5)
_TOKEN_TTL = timedelta(minutes=10)

_INVALID_MAGIC_LINK_MSG = "Invalid or expired magic link"


# ===================================================================
# Request models
# ===================================================================


class MagicLinkRequest(BaseModel):
    """Request body for POST /auth/magic-link."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    purpose: Literal["sign_in", "password_reset"] = "sign_in"


# ===================================================================
# Token helpers
# ===================================================================


def _generate_token() -> tuple[str, str]:
    """Generate a magic link token and its SHA-256 hash.

    Returns:
        (plain_token, token_hash) — plain for email, hash for DB storage.
    """
    plain = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(plain.encode()).hexdigest()
    return plain, hashed


# ===================================================================
# POST /auth/magic-link
# ===================================================================


@router.post("/magic-link")
@limiter.limit("5/hour")
async def request_magic_link(
    request: Request,  # noqa: ARG001
    body: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> DataResponse[dict]:
    """Request a magic link sign-in email.

    REQ-013 §4.4, §7.5: Always returns success regardless of whether
    the email exists (prevents email enumeration).

    Security: Token generation runs in all code paths to avoid timing
    side-channels. Email is sent as a background task so response time
    is consistent regardless of user existence.

    Rate limit: 5 per hour per IP.
    """
    email = body.email.strip().lower()

    # Generate token in all paths (constant-time crypto work)
    plain_token, token_hash = _generate_token()

    # Look up user — only store token and send email if user exists
    user = await UserRepository.get_by_email(db, email)

    if user:
        # Store hashed token in DB (purpose bound to token to prevent escalation)
        await VerificationTokenRepository.create(
            db,
            identifier=email,
            token_hash=token_hash,
            expires=datetime.now(UTC) + _TOKEN_TTL,
            purpose=body.purpose,
        )

    await db.commit()

    if user:
        # Send email as background task — response returns immediately
        background_tasks.add_task(
            send_magic_link_email,
            to_email=email,
            token=plain_token,
            purpose=body.purpose,
        )

    # Always return success (enumeration defense)
    return DataResponse(
        data={"message": "If an account exists, a sign-in link has been sent"}
    )


# ===================================================================
# GET /auth/verify-magic-link
# ===================================================================


@router.get("/verify-magic-link")
@limiter.limit("10/minute")
async def verify_magic_link(
    request: Request,  # noqa: ARG001
    token: Annotated[str, Query(min_length=1, max_length=256)],
    identifier: Annotated[str, Query(min_length=3, max_length=255)],
    purpose: Annotated[Literal["sign_in", "password_reset"], Query()] = "sign_in",
    *,
    db: DbSession,
) -> RedirectResponse:
    """Verify magic link token and issue JWT session.

    REQ-013 §4.4, §7.5: Validates token hash, checks expiry, deletes
    token (single-use), sets email_verified if needed, issues JWT cookie,
    redirects to frontend.

    Rate limit: 10 per minute per IP.
    """
    email = identifier.strip().lower()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Look up hashed token
    vt = await VerificationTokenRepository.get(
        db, identifier=email, token_hash=token_hash
    )

    if vt is None:
        raise ValidationError(_INVALID_MAGIC_LINK_MSG)

    # Security: purpose must match what was stored at creation time.
    # Prevents escalation of a sign_in link to password_reset by URL tampering.
    if vt.purpose != purpose:
        raise ValidationError(_INVALID_MAGIC_LINK_MSG)

    # Check expiry
    if vt.expires < datetime.now(UTC):
        # Clean up expired token
        await VerificationTokenRepository.delete(
            db, identifier=email, token_hash=token_hash
        )
        await db.commit()
        raise ValidationError(_INVALID_MAGIC_LINK_MSG)

    # Delete all tokens for this identifier (single-use cleanup)
    await VerificationTokenRepository.delete_all_for_identifier(db, identifier=email)

    # Find or create user
    user = await UserRepository.get_by_email(db, email)
    if user is None:
        user = await UserRepository.create(
            db,
            email=email,
            email_verified=datetime.now(UTC),
        )
    elif user.email_verified is None:
        await UserRepository.update(
            db,
            user.id,
            email_verified=datetime.now(UTC),
        )

    await db.commit()

    # Issue JWT — include password-reset claim if this was a forgot-password flow
    is_password_reset = purpose == "password_reset"
    pwr_until = datetime.now(UTC) + timedelta(minutes=10) if is_password_reset else None

    jwt_token = create_jwt(
        user_id=str(user.id),
        secret=settings.auth_secret.get_secret_value(),
        password_reset_until=pwr_until,
    )

    # Redirect to /settings for password reset, otherwise to app root
    redirect_url = (
        f"{settings.frontend_url}/settings"
        if is_password_reset
        else settings.frontend_url
    )

    response = RedirectResponse(
        url=redirect_url,
        status_code=307,
    )
    set_auth_cookie(response, jwt_token)
    # Prevent token leakage via Referer header
    response.headers["Referrer-Policy"] = "no-referrer"

    return response


# ===================================================================
# POST /auth/logout
# ===================================================================


@router.post("/logout")
async def logout(response: Response) -> DataResponse[dict]:
    """Clear auth cookie.

    REQ-013 §7.5: No auth required — clears cookie regardless.
    Cookie attributes must match set_auth_cookie() for browser to delete.
    """
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain or None,
    )
    return DataResponse(data={"message": "Signed out"})


# ===================================================================
# GET /auth/me
# ===================================================================


@router.get("/me")
async def get_me(
    user_id: CurrentUserId,
    password_reset_eligible: PasswordResetEligible,
    db: DbSession,
) -> DataResponse[dict]:
    """Return current user info from JWT.

    REQ-013 §7.5, §8.3a: Used by frontend SessionProvider / AuthProvider
    and Account Settings section.

    Returns 401 if no valid JWT.

    Response includes:
    - email_verified: bool (true if email has been verified)
    - has_password: bool (true if user has set a password; false for OAuth-only)
    """
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError()

    data = _user_to_response(user)
    if password_reset_eligible:
        data["can_reset_password"] = True
    return DataResponse(data=data)


# ===================================================================
# PATCH /auth/profile
# ===================================================================


def _user_to_response(user: User) -> dict:
    """Build standard user response payload for /me and /profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "image": user.image,
        "email_verified": user.email_verified is not None,
        "has_password": user.password_hash is not None,
    }


class UpdateProfileRequest(BaseModel):
    """Request body for PATCH /auth/profile."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255)


@router.patch("/profile")
async def update_profile(
    body: UpdateProfileRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update user profile fields.

    REQ-013 §8.3a: Account settings name edit.
    Currently supports updating the display name only.
    """
    trimmed_name = body.name.strip()
    if not trimmed_name:
        raise ValidationError("Name must not be empty")

    await UserRepository.update(db, user_id, name=trimmed_name)
    await db.commit()

    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError()

    return DataResponse(data=_user_to_response(user))


# ===================================================================
# POST /auth/invalidate-sessions
# ===================================================================


@router.post("/invalidate-sessions")
async def invalidate_sessions(
    response: Response,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Invalidate all sessions (sign out all devices).

    REQ-013 §8.3a, §8.9: Sets token_invalidated_before to now(),
    causing all existing JWTs to be rejected. Re-issues a new JWT
    for the current session so the caller stays authenticated.
    """
    invalidation_time = datetime.now(UTC).replace(microsecond=0)

    await UserRepository.update(db, user_id, token_invalidated_before=invalidation_time)
    await db.commit()

    # Re-issue JWT so current session survives
    jwt_token = create_jwt(
        user_id=str(user_id),
        secret=settings.auth_secret.get_secret_value(),
    )
    set_auth_cookie(response, jwt_token)

    return DataResponse(data={"message": "All sessions invalidated"})
