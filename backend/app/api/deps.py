"""Shared dependencies for API endpoints.

REQ-006 §6.1, REQ-013 §7.1: Authentication dependencies.
Local-first mode uses DEFAULT_USER_ID; hosted mode validates JWT from cookie.

WHY DEPENDENCY INJECTION:
- Consistent auth across all endpoints
- Easy to swap implementations (local → hosted)
- Testable with mocked dependencies
"""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User

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


# Reusable type aliases for dependency injection (SonarCloud S8410)
CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
