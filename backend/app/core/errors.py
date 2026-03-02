"""API error classes.

REQ-006 §8.1-8.2: HTTP status codes and error codes.
REQ-020 §7.2: InsufficientBalanceError (402).

WHY CUSTOM ERROR CLASSES:
- Consistent error response format across all endpoints
- Easy to map to HTTP status codes in exception handlers
- Type-safe error handling in services/repositories
"""

from decimal import Decimal


class APIError(Exception):
    """Base class for API errors.

    All API errors have a code, message, and HTTP status.
    Subclasses set default status_code.

    Attributes:
        code: Machine-readable error code (e.g., "NOT_FOUND").
        message: Human-readable error message.
        status_code: HTTP status code to return.
        details: Optional list of additional error details.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: list[dict] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class ValidationError(APIError):
    """Field validation failed (400).

    Use for request body validation errors, query param errors, etc.
    """

    def __init__(
        self,
        message: str,
        details: list[dict] | None = None,
    ) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details,
        )


class UnauthorizedError(APIError):
    """Authentication required (401).

    Use when no valid auth credentials provided.
    """

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=401,
        )


class ForbiddenError(APIError):
    """Not allowed to access resource (403).

    Use when auth is valid but user lacks permission.
    """

    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=403,
        )


class NotFoundError(APIError):
    """Resource not found (404).

    Use when requested resource doesn't exist OR doesn't belong to user.

    WHY NOT SEPARATE "FORBIDDEN" FOR WRONG OWNERSHIP:
    - Revealing "exists but not yours" leaks information
    - From user perspective, resource simply doesn't exist
    """

    def __init__(self, resource: str, resource_id: str | None = None) -> None:
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        else:
            message = f"{resource} not found"
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=404,
        )


class ContentSecurityError(APIError):
    """Content security violation (400).

    REQ-015 §8.4: Rejected due to detected prompt injection patterns
    or other content security policy violations in shared pool content.
    """

    def __init__(
        self,
        message: str,
        details: list[dict] | None = None,
    ) -> None:
        super().__init__(
            code="CONTENT_SECURITY_VIOLATION",
            message=message,
            status_code=400,
            details=details,
        )


class ConflictError(APIError):
    """Duplicate or conflicting resource (409).

    Use for duplicate entries, conflicting state, etc.
    Accepts custom code for specific conflict types.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: list[dict] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details=details,
        )


class InvalidStateError(APIError):
    """Business rule violation (422).

    Use when request is syntactically valid but violates business rules.
    E.g., trying to approve an already-approved document.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            code="INVALID_STATE_TRANSITION",
            message=message,
            status_code=422,
        )


class InsufficientBalanceError(APIError):
    """Insufficient balance for LLM calls (402).

    REQ-020 §7.2: Raised when user's balance is too low.
    Details include current balance and minimum required threshold.

    Args:
        balance: Current user balance in USD.
        minimum_required: Minimum balance threshold from config.
    """

    def __init__(
        self,
        balance: Decimal,
        minimum_required: Decimal,
    ) -> None:
        super().__init__(
            code="INSUFFICIENT_BALANCE",
            message=f"Your balance is ${balance:.2f}. Please add funds to continue.",
            status_code=402,
            details=[
                {
                    "balance_usd": f"{balance:.6f}",
                    "minimum_required": f"{minimum_required:.6f}",
                }
            ],
        )


class AdminRequiredError(ForbiddenError):
    """Admin access required (403).

    REQ-022 §5.3: Raised by require_admin dependency when user lacks admin flag.
    """

    def __init__(self) -> None:
        APIError.__init__(
            self,
            code="ADMIN_REQUIRED",
            message="Admin access required",
            status_code=403,
        )


class UnregisteredModelError(APIError):
    """LLM model not in model registry or inactive (503).

    REQ-022 §7.3: Raised when MeteringService encounters an unregistered model.

    Security: Provider/model names are intentionally included in the message.
    These are operational config errors (not auth errors), only reachable by
    authenticated users, and admins need the detail to fix misconfiguration.

    Args:
        provider: LLM provider identifier (e.g., "claude").
        model: Model identifier (e.g., "claude-3-5-haiku-20241022").
    """

    def __init__(self, provider: str, model: str) -> None:
        super().__init__(
            code="UNREGISTERED_MODEL",
            message=f"Model '{model}' from provider '{provider}' is not registered or is inactive",
            status_code=503,
        )


class NoPricingConfigError(APIError):
    """No effective pricing config for model (503).

    REQ-022 §7.3: Raised when no pricing_config row has effective_date <= today.

    Security: Same rationale as UnregisteredModelError — operational error
    with detail needed for admin debugging.

    Args:
        provider: LLM provider identifier.
        model: Model identifier.
    """

    def __init__(self, provider: str, model: str) -> None:
        super().__init__(
            code="NO_PRICING_CONFIG",
            message=f"No pricing configuration found for '{model}' from provider '{provider}'",
            status_code=503,
        )


class InternalError(APIError):
    """Unexpected server error (500).

    Use for unhandled exceptions. Never expose stack traces to clients.
    """

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        super().__init__(
            code="INTERNAL_ERROR",
            message=message,
            status_code=500,
        )
