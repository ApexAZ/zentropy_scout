"""Tests for response envelope models.

REQ-006 §7.2: Response envelope pattern.
"""

from app.core.responses import (
    DataResponse,
    ErrorDetail,
    ErrorResponse,
    PaginationMeta,
)


class TestPaginationMeta:
    """Tests for PaginationMeta model."""

    def test_total_pages_exact_division(self):
        """Total pages should be total / per_page when evenly divisible."""
        meta = PaginationMeta(total=100, page=1, per_page=20)
        assert meta.total_pages == 5

    def test_total_pages_rounds_up(self):
        """Total pages should round up when not evenly divisible."""
        meta = PaginationMeta(total=101, page=1, per_page=20)
        assert meta.total_pages == 6

    def test_total_pages_zero_items(self):
        """Total pages should be 0 when no items."""
        meta = PaginationMeta(total=0, page=1, per_page=20)
        assert meta.total_pages == 0

    def test_total_pages_fewer_than_per_page(self):
        """Total pages should be 1 when fewer items than per_page."""
        meta = PaginationMeta(total=5, page=1, per_page=20)
        assert meta.total_pages == 1


class TestDataResponse:
    """Tests for DataResponse model (single resource)."""

    def test_data_response_serializes_with_data_key(self):
        """DataResponse should serialize with 'data' key."""
        response = DataResponse(data={"id": "123", "name": "Test"})
        result = response.model_dump()
        assert "data" in result
        assert result["data"]["id"] == "123"
        assert result["data"]["name"] == "Test"


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_serializes_with_error_key(self):
        """ErrorResponse should serialize with 'error' key."""
        detail = ErrorDetail(code="NOT_FOUND", message="User not found")
        response = ErrorResponse(error=detail)
        result = response.model_dump()
        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert result["error"]["message"] == "User not found"
