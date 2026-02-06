"""Rate limiting configuration using slowapi.

Security: Prevents API abuse and LLM cost explosion by limiting
request frequency on expensive endpoints.

Usage in routers:
    from app.core.rate_limiting import limiter

    @router.post("/ingest")
    @limiter.limit(lambda: settings.rate_limit_llm)
    async def ingest_job_posting(request: Request, ...):
        ...
"""

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.core.config import settings


def _rate_limit_key_func(request: Request) -> str:
    """Get rate limit key from request.

    Uses remote address (IP) as the key for rate limiting.
    In production behind a reverse proxy, configure X-Forwarded-For handling.

    Args:
        request: The incoming request.

    Returns:
        The client's IP address as string.
    """
    return get_remote_address(request)


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
