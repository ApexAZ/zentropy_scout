"""Authentication helpers for JWT creation, cookie management, and password validation.

REQ-013 §7.5, §10.8: Shared utilities used by auth endpoints.

Pipeline:
- create_jwt / set_auth_cookie: JWT issuance for successful auth
- validate_password_strength: Format rules (sync, no network)
- check_password_breached: HIBP k-anonymity check (async, network)
- DUMMY_HASH: Timing-safe constant for user enumeration defense
"""

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from fastapi import Response

from app.core.config import settings
from app.core.errors import ValidationError

logger = logging.getLogger(__name__)

# Default JWT expiration: 1 hour
_DEFAULT_EXPIRATION = timedelta(hours=1)

# HIBP API timeout in seconds
_HIBP_TIMEOUT = 5.0

# Pre-computed bcrypt hash for timing-safe comparison on user-not-found.
# Security: prevents user enumeration via response time differences.
# Pre-generated to avoid ~300ms bcrypt computation on every app startup.
DUMMY_HASH = b"$2b$12$ZP2PVB8yI35X.mkRqcUPUuSzJA1CNRt4dZ7X3cyrfJu.2S3w.Qen2"


def create_jwt(
    *,
    user_id: str,
    secret: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT with standard claims.

    Args:
        user_id: User UUID string for the sub claim.
        secret: HMAC signing secret.
        expires_delta: Time until expiration. Defaults to 1 hour.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "aud": "zentropy-scout",
        "iss": settings.auth_issuer,
        "exp": now + (expires_delta or _DEFAULT_EXPIRATION),
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly JWT cookie on response.

    Security: httpOnly prevents XSS cookie theft. Secure flag and SameSite
    are configured via settings for environment-appropriate security.

    Args:
        response: FastAPI response object.
        token: JWT token string.
    """
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
        max_age=int(_DEFAULT_EXPIRATION.total_seconds()),
        domain=settings.auth_cookie_domain or None,
    )


def validate_password_strength(password: str) -> None:
    """Validate password meets strength requirements.

    REQ-013 §10.8: 8-128 chars, letter + number + special character.

    Args:
        password: Plain-text password to validate.

    Raises:
        ValidationError: If password doesn't meet requirements.
    """
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValidationError("Password must be at most 128 characters")
    if not re.search(r"[a-zA-Z]", password):
        raise ValidationError("Password must contain at least one letter")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number")
    if not re.search(r"[^a-zA-Z\d]", password):
        raise ValidationError("Password must contain at least one special character")


async def _fetch_hibp_range(prefix: str) -> str | None:
    """Fetch HIBP range response for a SHA-1 prefix.

    Uses k-anonymity: only the first 5 chars of the SHA-1 hash are sent.
    The API returns all suffixes matching that prefix, and we check locally.

    Args:
        prefix: First 5 chars of SHA-1 hex digest (uppercase).

    Returns:
        Response text or None on error.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true"},
                timeout=_HIBP_TIMEOUT,
            )
            response.raise_for_status()
            return response.text
    except Exception:
        logger.warning("HIBP API request failed")
        return None


async def check_password_breached(password: str) -> bool:
    """Check if password appears in HIBP breach database.

    REQ-013 §10.8: Uses k-anonymity model — only the first 5 characters
    of the SHA-1 hash are sent to HIBP. The full hash never leaves the server.

    Fails open: if HIBP is unavailable, allows the password. This prevents
    HIBP outages from blocking user registration.

    Args:
        password: Plain-text password to check.

    Returns:
        True if password found in breach database, False otherwise.
    """
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()  # nosec B324
    prefix = sha1[:5]
    suffix = sha1[5:]

    text = await _fetch_hibp_range(prefix)
    if text is None:
        return False

    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) == 2 and parts[0] == suffix:
            return True

    return False
