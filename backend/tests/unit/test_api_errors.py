"""Tests for API error classes.

REQ-006 §8.1-8.2: HTTP status codes and error codes.
"""

import pytest

from app.core.errors import (
    APIError,
    ConflictError,
    ForbiddenError,
    InternalError,
    InvalidStateError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


class TestAPIError:
    """Tests for base APIError class."""

    def test_api_error_has_required_attributes(self):
        """APIError should have code, message, status_code, details."""
        error = APIError(
            code="TEST_ERROR",
            message="Test message",
            status_code=418,
            details=[{"field": "test"}],
        )
        assert error.code == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.status_code == 418
        assert error.details == [{"field": "test"}]

    def test_api_error_defaults_to_500(self):
        """APIError should default to 500 status code."""
        error = APIError(code="TEST", message="Test")
        assert error.status_code == 500

    def test_api_error_details_default_to_none(self):
        """APIError details should default to None."""
        error = APIError(code="TEST", message="Test")
        assert error.details is None

    def test_api_error_is_exception(self):
        """APIError should be an Exception subclass."""
        error = APIError(code="TEST", message="Test")
        assert str(error) == "Test"


class TestErrorCodeAndStatus:
    """Hardcoded code + status_code for each error subclass."""

    @pytest.mark.parametrize(
        ("error", "expected_code", "expected_status"),
        [
            (ValidationError("msg"), "VALIDATION_ERROR", 400),
            (UnauthorizedError(), "UNAUTHORIZED", 401),
            (ForbiddenError(), "FORBIDDEN", 403),
            (NotFoundError("X"), "NOT_FOUND", 404),
            (InvalidStateError("msg"), "INVALID_STATE_TRANSITION", 422),
            (InternalError(), "INTERNAL_ERROR", 500),
        ],
    )
    def test_error_has_correct_code_and_status(
        self, error, expected_code, expected_status
    ):
        """Each error subclass has the correct code and status_code."""
        assert error.code == expected_code
        assert error.status_code == expected_status


class TestValidationError:
    """Tests for ValidationError (400)."""

    def test_validation_error_with_details(self):
        """ValidationError should pass through details."""
        details = [{"loc": ["body", "email"], "msg": "invalid email"}]
        error = ValidationError("Validation failed", details=details)
        assert error.details == details


class TestUnauthorizedError:
    """Tests for UnauthorizedError (401)."""

    def test_unauthorized_error_default_message(self):
        """UnauthorizedError should have default message."""
        error = UnauthorizedError()
        assert error.message == "Authentication required"

    def test_unauthorized_error_custom_message(self):
        """UnauthorizedError should accept custom message."""
        error = UnauthorizedError("Token expired")
        assert error.message == "Token expired"


class TestForbiddenError:
    """Tests for ForbiddenError (403)."""

    def test_forbidden_error_default_message(self):
        """ForbiddenError should have default message."""
        error = ForbiddenError()
        assert error.message == "Access denied"

    def test_forbidden_error_custom_message(self):
        """ForbiddenError should accept custom message."""
        error = ForbiddenError("Not your resource")
        assert error.message == "Not your resource"


class TestNotFoundError:
    """Tests for NotFoundError (404)."""

    def test_not_found_with_resource_only(self):
        """NotFoundError should format message with resource name."""
        error = NotFoundError("User")
        assert error.message == "User not found"

    def test_not_found_with_resource_and_id(self):
        """NotFoundError should include resource id in message."""
        error = NotFoundError("Persona", "abc-123")
        assert "Persona" in error.message
        assert "abc-123" in error.message


class TestConflictError:
    """Tests for ConflictError (409)."""

    def test_conflict_error_has_409_status(self):
        """ConflictError should have 409 status code."""
        error = ConflictError(
            code="DUPLICATE_APPLICATION",
            message="Already applied",
        )
        assert error.status_code == 409

    def test_conflict_error_accepts_custom_code(self):
        """ConflictError should accept custom error code."""
        error = ConflictError(
            code="DUPLICATE_APPLICATION",
            message="Already applied to this job",
        )
        assert error.code == "DUPLICATE_APPLICATION"
        assert error.message == "Already applied to this job"

    def test_conflict_error_with_details(self):
        """ConflictError should pass through details."""
        details = [{"existing_id": "123"}]
        error = ConflictError(
            code="DUPLICATE",
            message="Duplicate found",
            details=details,
        )
        assert error.details == details


class TestInternalError:
    """Tests for InternalError (500)."""

    def test_internal_error_default_message(self):
        """InternalError should have default message."""
        error = InternalError()
        assert error.message == "An unexpected error occurred"

    def test_internal_error_custom_message(self):
        """InternalError should accept custom message."""
        error = InternalError("Database connection failed")
        assert error.message == "Database connection failed"
