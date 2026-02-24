"""Authentication endpoints for password-based auth.

REQ-013 §7.5: verify-password, register, change-password endpoints.

Security considerations:
- verify-password: constant-time comparison via DUMMY_HASH prevents user enumeration
- register: bcrypt cost 12, HIBP breach check, email uniqueness, verification email
- change-password: verifies current password, invalidates all sessions
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserId, DbSession, PasswordResetEligible
from app.core.auth import (
    DUMMY_HASH,
    check_password_breached,
    create_jwt,
    set_auth_cookie,
    validate_password_strength,
)
from app.core.config import settings
from app.core.email import send_magic_link_email
from app.core.errors import APIError, ConflictError, UnauthorizedError, ValidationError
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse
from app.repositories.user_repository import UserRepository
from app.repositories.verification_token_repository import VerificationTokenRepository

# bcrypt cost factor for password hashing (REQ-013 §10.8)
_BCRYPT_ROUNDS = 12

_PASSWORD_BREACHED_MSG = (  # nosec B105
    "This password has appeared in a data breach. Please choose a different one."
)

# Verification email token TTL (REQ-013 §10.5)
_VERIFICATION_TOKEN_TTL = timedelta(minutes=10)

router = APIRouter()


# ===================================================================
# Request models
# ===================================================================


class VerifyPasswordRequest(BaseModel):
    """Request body for POST /auth/verify-password."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Request body for POST /auth/change-password."""

    model_config = ConfigDict(extra="forbid")

    current_password: str | None = Field(None, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


# ===================================================================
# POST /auth/verify-password
# ===================================================================


@router.post("/verify-password")
@limiter.limit("5/15minute")
async def verify_password(
    request: Request,  # noqa: ARG001 - required by @limiter.limit()
    body: VerifyPasswordRequest,
    response: Response,
    db: DbSession,
) -> DataResponse[dict]:
    """Verify email + password and issue JWT cookie.

    REQ-013 §7.5: Unauthenticated. Constant-time comparison prevents
    user enumeration via response time differences.

    Rate limit: 5 per 15 minutes per IP.
    """
    user = await UserRepository.get_by_email(db, body.email)

    if not user or not user.password_hash:
        # Security: always perform bcrypt comparison to prevent timing attacks.
        # DUMMY_HASH ensures consistent response time regardless of user existence.
        bcrypt.checkpw(body.password.encode(), DUMMY_HASH)
        raise UnauthorizedError("Invalid email or password")

    if not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise UnauthorizedError("Invalid email or password")

    # Block sign-in until email is verified (REQ-013 §4.3)
    if user.email_verified is None:
        raise APIError(
            code="EMAIL_NOT_VERIFIED",
            message="Please verify your email before signing in. Check your inbox for the verification link.",
            status_code=403,
        )

    # Issue JWT and set cookie
    token = create_jwt(
        user_id=str(user.id),
        secret=settings.auth_secret.get_secret_value(),
    )
    set_auth_cookie(response, token)

    return DataResponse(
        data={"id": str(user.id), "email": user.email, "name": user.name}
    )


# ===================================================================
# POST /auth/register
# ===================================================================


@router.post("/register", status_code=201)
@limiter.limit("3/hour")
async def register(
    request: Request,  # noqa: ARG001 - required by @limiter.limit()
    body: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> DataResponse[dict]:
    """Register a new user with email + password.

    REQ-013 §7.5: Unauthenticated. Validates password strength,
    checks HIBP breach database, creates user with bcrypt hash,
    and sends a verification email (magic link).

    Rate limit: 3 per hour per IP.
    """
    # Validate password strength (format rules)
    validate_password_strength(body.password)

    # Check HIBP breach database (k-anonymity)
    if await check_password_breached(body.password):
        raise APIError(
            code="PASSWORD_BREACHED",
            message=_PASSWORD_BREACHED_MSG,
            status_code=422,
        )

    # Hash password (bcrypt, cost factor 12)
    password_hash = bcrypt.hashpw(
        body.password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    ).decode()

    # Create user
    try:
        user = await UserRepository.create(
            db, email=body.email, password_hash=password_hash
        )
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            code="EMAIL_ALREADY_EXISTS",
            message="Email already registered",
        ) from exc

    # Generate verification token and store hash in DB
    plain_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plain_token.encode()).hexdigest()
    await VerificationTokenRepository.create(
        db,
        identifier=body.email.strip().lower(),
        token_hash=token_hash,
        expires=datetime.now(UTC) + _VERIFICATION_TOKEN_TTL,
    )
    await db.commit()

    # Send verification email as background task
    background_tasks.add_task(
        send_magic_link_email,
        to_email=body.email.strip().lower(),
        token=plain_token,
    )

    return DataResponse(data={"id": str(user.id), "email": user.email})


# ===================================================================
# POST /auth/change-password
# ===================================================================


@router.post("/change-password")
@limiter.limit("5/hour")
async def change_password(
    request: Request,  # noqa: ARG001 - required by @limiter.limit()
    body: ChangePasswordRequest,
    response: Response,
    user_id: CurrentUserId,
    password_reset_eligible: PasswordResetEligible,
    db: DbSession,
) -> DataResponse[dict]:
    """Change password for authenticated user.

    REQ-013 §7.5: Authenticated. Verifies current password if set
    (skipped when JWT has a valid password-reset claim from the
    forgot-password flow). Validates new password strength and
    invalidates all other sessions. Re-issues JWT cookie so the
    current session stays valid.

    Rate limit: 5 per hour per user.
    """
    user = await UserRepository.get_by_id(db, user_id)
    if not user:
        raise UnauthorizedError()

    # If user has existing password, verify current password
    # (skipped when the JWT carries a valid password-reset claim)
    if user.password_hash and not password_reset_eligible:
        if not body.current_password:
            raise ValidationError("Current password required")
        if not bcrypt.checkpw(
            body.current_password.encode(), user.password_hash.encode()
        ):
            raise UnauthorizedError("Current password incorrect")

    # Validate new password strength
    validate_password_strength(body.new_password)

    # Check HIBP breach database
    if await check_password_breached(body.new_password):
        raise APIError(
            code="PASSWORD_BREACHED",
            message=_PASSWORD_BREACHED_MSG,
            status_code=422,
        )

    # Hash new password
    new_hash = bcrypt.hashpw(
        body.new_password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    ).decode()

    # Truncate microseconds: PyJWT encodes iat as integer seconds,
    # so the new JWT's iat must be >= token_invalidated_before.
    invalidation_time = datetime.now(UTC).replace(microsecond=0)

    # Update password and invalidate all prior sessions
    await UserRepository.update(
        db,
        user_id,
        password_hash=new_hash,
        token_invalidated_before=invalidation_time,
    )
    await db.commit()

    # Re-issue JWT so the current session stays valid after invalidation
    token = create_jwt(
        user_id=str(user_id),
        secret=settings.auth_secret.get_secret_value(),
    )
    set_auth_cookie(response, token)

    return DataResponse(data={"message": "Password updated"})
