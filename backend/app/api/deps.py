"""Shared dependencies for API endpoints.

REQ-006 §6.1, REQ-013 §7.1: Authentication dependencies.
REQ-020 §6.2, §6.5: Metered provider dependencies.
Local-first mode uses DEFAULT_USER_ID; hosted mode validates JWT from cookie.

WHY DEPENDENCY INJECTION:
- Consistent auth across all endpoints
- Easy to swap implementations (local → hosted)
- Testable with mocked dependencies
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import InsufficientBalanceError
from app.models import User
from app.providers.embedding.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider, get_llm_provider
from app.providers.llm.base import LLMProvider
from app.providers.metered_provider import MeteredEmbeddingProvider, MeteredLLMProvider
from app.services.metering_service import MeteringService

# Generic 401 detail — intentionally vague to prevent information leakage.
# Security: Never include specifics about WHY auth failed (expired, bad sig, etc.).
_UNAUTHORIZED_DETAIL = {
    "code": "UNAUTHORIZED",
    "message": "Authentication required",
}


async def get_current_user_id(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> uuid.UUID:
    """Get current user ID from auth context.

    REQ-013 §7.1: Validates JWT from httpOnly cookie when auth is enabled.
    REQ-006 §6.1: Falls back to DEFAULT_USER_ID when auth is disabled.

    Validation steps (hosted mode):
    1. Read JWT from cookie
    2. Decode + verify signature (HS256)
    3. Verify exp, aud, iss claims
    4. Extract sub as UUID
    5. Check token_invalidated_before (revocation)

    Args:
        request: HTTP request (injected by FastAPI).
        db: Database session for revocation check (injected).

    Returns:
        UUID of the current authenticated user.

    Raises:
        HTTPException: 401 for any auth failure.
    """
    if not settings.auth_enabled:
        # Local-first mode: use DEFAULT_USER_ID from environment
        if settings.default_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_UNAUTHORIZED_DETAIL,
            )
        return settings.default_user_id

    # Hosted mode: validate JWT from cookie
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_UNAUTHORIZED_DETAIL,
        )

    try:
        payload = jwt.decode(
            token,
            settings.auth_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer=settings.auth_issuer,
        )
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_UNAUTHORIZED_DETAIL,
        ) from exc

    # Security: iat is required for revocation check. A JWT without iat
    # would bypass token_invalidated_before entirely.
    iat = payload.get("iat")
    if iat is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_UNAUTHORIZED_DETAIL,
        )

    # Revocation check: reject JWTs issued before token_invalidated_before
    result = await db.execute(
        select(User.token_invalidated_before).where(User.id == user_id)
    )
    invalidated_before = result.scalar_one_or_none()
    if invalidated_before is not None and iat < invalidated_before.timestamp():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_UNAUTHORIZED_DETAIL,
        )

    return user_id


async def get_current_user(
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get full User object for current user.

    Use this when you need the User object, not just the ID.
    Most endpoints should use get_current_user_id instead.

    Args:
        user_id: Current user ID (injected by get_current_user_id).
        db: Database session (injected).

    Returns:
        User object for the current user.

    Raises:
        HTTPException: 401 if user not found (deleted account, invalid ID).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_UNAUTHORIZED_DETAIL,
        )

    return user


def get_password_reset_eligible(request: Request) -> bool:
    """Check if the current JWT has a valid password-reset claim.

    Returns True when the JWT contains a ``pwr`` (password-reset-until)
    timestamp that is still in the future.  Used by change-password to
    skip the current-password requirement after a forgot-password flow.
    """
    if not settings.auth_enabled:
        return False

    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return False

    try:
        payload = jwt.decode(
            token,
            settings.auth_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="zentropy-scout",
            issuer=settings.auth_issuer,
        )
    except jwt.InvalidTokenError:
        return False

    pwr = payload.get("pwr")
    if pwr is None:
        return False

    return bool(datetime.now(UTC).timestamp() < pwr)


# Reusable type aliases for dependency injection (SonarCloud S8410)
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PasswordResetEligible = Annotated[bool, Depends(get_password_reset_eligible)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_metered_provider(
    user_id: CurrentUserId,
    db: DbSession,
) -> LLMProvider:
    """Get an LLM provider with optional metering wrapper.

    REQ-020 §6.2: When metering is enabled, wraps the factory singleton
    in a MeteredLLMProvider that records usage after each call.

    Args:
        user_id: Current user ID (from auth dependency).
        db: Database session for metering records.

    Returns:
        LLMProvider — raw singleton or metered wrapper.
    """
    if not settings.metering_enabled:
        return get_llm_provider()
    inner = get_llm_provider()
    metering_service = MeteringService(db)
    return MeteredLLMProvider(inner, metering_service, user_id)


def get_metered_embedding_provider(
    user_id: CurrentUserId,
    db: DbSession,
) -> EmbeddingProvider:
    """Get an embedding provider with optional metering wrapper.

    REQ-020 §6.5: When metering is enabled, wraps the factory singleton
    in a MeteredEmbeddingProvider that records usage after each call.

    Args:
        user_id: Current user ID (from auth dependency).
        db: Database session for metering records.

    Returns:
        EmbeddingProvider — raw singleton or metered wrapper.
    """
    if not settings.metering_enabled:
        return get_embedding_provider()
    inner = get_embedding_provider()
    metering_service = MeteringService(db)
    return MeteredEmbeddingProvider(inner, metering_service, user_id)


MeteredProvider = Annotated[LLMProvider, Depends(get_metered_provider)]
MeteredEmbedding = Annotated[EmbeddingProvider, Depends(get_metered_embedding_provider)]


async def require_sufficient_balance(
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Raise 402 if user has insufficient balance for LLM calls.

    REQ-020 §7.1: FastAPI dependency that gates LLM-triggering endpoints.
    Check is ``balance > threshold`` (strict greater-than).

    This is a **soft gate** (read-only check). The hard enforcement is the
    atomic debit in MeteringService.record_and_debit() which prevents
    balance from going negative. Concurrent requests may pass this gate
    simultaneously, but the atomic debit ensures correctness.

    Args:
        user_id: Current user ID (from auth dependency).
        db: Database session (injected).

    Raises:
        InsufficientBalanceError: When balance <= minimum threshold.
    """
    if not settings.metering_enabled:
        return

    result = await db.execute(select(User.balance_usd).where(User.id == user_id))
    balance = result.scalar_one_or_none()
    # balance_usd is NOT NULL with server default 0. A None result means
    # the user row does not exist (deleted account). Treat as zero balance
    # for fail-safe behavior (402 blocks access).
    if balance is None:
        balance = Decimal("0.000000")

    threshold = Decimal(str(settings.metering_minimum_balance))
    if balance <= threshold:
        raise InsufficientBalanceError(
            balance=balance,
            minimum_required=threshold,
        )


BalanceCheck = Annotated[None, Depends(require_sufficient_balance)]
