"""FastAPI application entry point.

REQ-006 §2.1: REST API with versioned routing and consistent error handling.

This module creates and configures the FastAPI application, including:
- Exception handlers for API errors
- API v1 router mounting
- Health check endpoint
"""

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.errors import APIError
from app.core.rate_limiting import limiter, rate_limit_exceeded_handler
from app.core.responses import ErrorDetail, ErrorResponse

logger = structlog.get_logger()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Headers added:
    - X-Frame-Options: Prevents clickjacking attacks
    - X-Content-Type-Options: Prevents MIME sniffing
    - X-XSS-Protection: Enables XSS filtering in older browsers
    - Referrer-Policy: Controls referrer information leakage
    - Cache-Control: Prevents caching of sensitive data on API responses
    - Content-Security-Policy: Restricts resource loading (API returns no HTML)
    - Cross-Origin-Opener-Policy: Isolates browsing context (Spectre mitigation)
    - Cross-Origin-Embedder-Policy: Requires CORP for cross-origin resources (Spectre)
    - Cross-Origin-Resource-Policy: Restricts resource sharing to same-origin (Spectre)
    - Strict-Transport-Security: Forces HTTPS (production only)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection for older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Prevent caching of API responses (may contain sensitive data)
        # Exception: static files should be cached (not applicable to this API)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"

        # Content Security Policy for API-only backend
        # default-src 'none': API responses should not load any resources
        # frame-ancestors 'none': Modern replacement for X-Frame-Options
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        # Spectre vulnerability mitigation (ZAP alert 90004)
        # COOP isolates the browsing context group so cross-origin documents
        # cannot access the window object. COEP ensures all cross-origin
        # resources opt in via CORP headers. CORP restricts which origins
        # can load this resource.
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # HSTS only in production (assumes HTTPS via reverse proxy)
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors.

    REQ-006 §7.2: Return consistent error envelope.

    Args:
        request: The incoming request.
        exc: The APIError that was raised.

    Returns:
        JSONResponse with error envelope and appropriate status code.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        ).model_dump(),
    )


def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors from FastAPI.

    REQ-006 §8.2: Converts FastAPI's validation errors to our standard format.

    Args:
        request: The incoming request.
        exc: The RequestValidationError from Pydantic.

    Returns:
        JSONResponse with VALIDATION_ERROR code and field-level details.
    """
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details=[
                    {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ],
            )
        ).model_dump(),
    )


def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions.

    REQ-006 §8.1: Returns 500 INTERNAL_ERROR without exposing stack traces.

    WHY: Never expose internal error details to clients. Log for debugging.

    Args:
        request: The incoming request.
        exc: The unhandled exception.

    Returns:
        JSONResponse with generic error message (500).
    """
    logger.exception("Unhandled exception", exc_info=exc, path=str(request.url.path))

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
            )
        ).model_dump(),
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    REQ-006 §2.1: REST API with path versioning.

    WHY FACTORY FUNCTION:
    - Enables testing with different configurations
    - Clear separation between app creation and startup
    - Standard FastAPI pattern

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Zentropy Scout API",
        version="1.0.0",
        description="AI-powered job application assistant",
    )

    # Middleware order: Starlette uses LIFO, so the LAST added runs FIRST.
    # CORS must run first to handle preflight requests, so add it last.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "Authorization", "X-Request-ID"],
    )

    # Register exception handlers
    # Order matters: specific handlers first, then catch-all
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    # Rate limiting (Security)
    # Prevents API abuse and LLM cost explosion
    app.state.limiter = limiter

    # Include v1 router at /api/v1
    app.include_router(v1_router, prefix="/api/v1")

    # Health check endpoint (outside versioned API)
    @app.get("/health")
    def health_check() -> dict:
        """Health check endpoint for monitoring.

        Returns:
            {"status": "healthy"} if service is running.
        """
        return {"status": "healthy"}

    return app


# Create the application instance
# Used by uvicorn: uvicorn app.main:app
app = create_app()
