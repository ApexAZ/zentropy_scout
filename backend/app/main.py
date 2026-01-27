"""FastAPI application entry point.

REQ-006 §2.1: REST API with versioned routing and consistent error handling.

This module creates and configures the FastAPI application, including:
- Exception handlers for API errors
- API v1 router mounting
- Health check endpoint
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.errors import APIError
from app.core.responses import ErrorDetail, ErrorResponse

logger = structlog.get_logger()


async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
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


async def validation_error_handler(
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


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
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

    # Register exception handlers
    # Order matters: specific handlers first, then catch-all
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    # Include v1 router at /api/v1
    app.include_router(v1_router, prefix="/api/v1")

    # Health check endpoint (outside versioned API)
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint for monitoring.

        Returns:
            {"status": "healthy"} if service is running.
        """
        return {"status": "healthy"}

    return app


# Create the application instance
# Used by uvicorn: uvicorn app.main:app
app = create_app()
