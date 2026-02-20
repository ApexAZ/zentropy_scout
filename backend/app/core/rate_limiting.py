"""Rate limiting configuration using slowapi.

Security: Prevents API abuse and LLM cost explosion by limiting
request frequency on expensive endpoints.

REQ-013 §7.4: When auth is enabled, rate limiting keys on the JWT subject
(per-user) to prevent abuse from shared IP addresses. Unauthenticated
requests fall back to IP-based keying.

Usage in routers:
    from app.core.rate_limiting import limiter

    @router.post("/ingest")
    @limiter.limit(lambda: settings.rate_limit_llm)
    async def ingest_job_posting(request: Request, ...):
        ...
"""

import jwt
from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.core.config import settings


def _rate_limit_key_func(request: Request) -> str:
    """Get rate limit key from request.

    REQ-013 §7.4: When auth is enabled, extracts user ID from JWT cookie
    for per-user rate limiting. Falls back to IP-based keying when auth
    is disabled, no cookie is present, or JWT is invalid.

    Key format:
    - Auth disabled: "{ip}" (local dev mode)
    - Auth enabled + valid JWT: "user:{sub}"
    - Auth enabled + no/invalid JWT: "unauth:{ip}"

    Args:
        request: The incoming request.

    Returns:
        Rate limit key string.
    """
    if not settings.auth_enabled:
        return get_remote_address(request)

    # Note: No iat/revocation check here — rate limiting only needs the sub
    # claim for keying. Full auth validation happens in deps.py.
    # Cookie-stripping is not a bypass concern because authenticated endpoints
    # have auth dependencies that reject unauthenticated requests before
    # reaching business logic.
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.auth_secret.get_secret_value(),
                algorithms=["HS256"],
                audience="zentropy-scout",
                issuer=settings.auth_issuer,
            )
            sub = payload["sub"]
            # Defense-in-depth: validate sub looks like a UUID (36 chars)
            if len(sub) <= 36:
                return f"user:{sub}"
        except (jwt.InvalidTokenError, KeyError):
            pass

    return f"unauth:{get_remote_address(request)}"


# Global limiter instance
# Configured with in-memory storage (suitable for single-instance deployment)
# For multi-instance, configure Redis storage via RATELIMIT_STORAGE_URL
limiter = Limiter(
    key_func=_rate_limit_key_func,
    enabled=settings.rate_limit_enabled,
)


def rate_limit_exceeded_handler(
    _request: Request,
    exc: RateLimitExceeded,
) -> Response:
    """Handle rate limit exceeded errors.

    Security: Returns 429 Too Many Requests with standard error envelope.

    Args:
        request: The incoming request.
        exc: The rate limit exception.

    Returns:
        JSONResponse with 429 status and retry-after header.
    """
    # Parse retry-after from exception detail (e.g., "10 per 1 minute")
    # Fallback to 60 seconds if parsing fails
    try:
        retry_after = str(exc.detail.split()[-1])
        # Validate it looks like a time value
        int(retry_after.rstrip("s"))  # "60" or "60s" -> 60
    except (ValueError, AttributeError, IndexError):
        retry_after = "60"

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": f"Rate limit exceeded: {exc.detail}",
            }
        },
        headers={"Retry-After": retry_after},
    )
