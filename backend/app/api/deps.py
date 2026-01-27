"""Shared dependencies for API endpoints.

REQ-006 §6.1: Authentication dependencies for local-first mode.

WHY DEPENDENCY INJECTION:
- Consistent auth across all endpoints
- Easy to swap implementations (local → hosted)
- Testable with mocked dependencies
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User


async def get_current_user_id() -> uuid.UUID:
    """Get current user ID from auth context.

    REQ-006 §6.1: Local-first mode uses DEFAULT_USER_ID from environment.
    Future: Replace with JWT token extraction for hosted mode.

    WHY SEPARATE FROM USER OBJECT:
    - Most endpoints just need user_id for filtering
    - Avoids unnecessary DB query when only checking ownership
    - Future: Token contains user_id, no DB lookup needed

    Returns:
        UUID of the current authenticated user.

    Raises:
        HTTPException: 401 if no user configured (auth required).
    """
    if not settings.default_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authentication required"},
        )

    return settings.default_user_id


async def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
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
            detail={"code": "UNAUTHORIZED", "message": "User not found"},
        )

    return user
