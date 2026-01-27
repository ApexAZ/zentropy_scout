"""Tests for response envelope models.

REQ-006 §7.2: Response envelope pattern.
"""

from app.core.responses import (
    DataResponse,
    ErrorDetail,
    ErrorResponse,
    ListResponse,
    PaginationMeta,
)


class TestPaginationMeta:
    """Tests for PaginationMeta model."""

    def test_pagination_meta_fields(self):
        """PaginationMeta should have total, page, per_page fields."""
        meta = PaginationMeta(total=100, page=2, per_page=20)
        assert meta.total == 100
        assert meta.page == 2
        assert meta.per_page == 20

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

    def test_data_response_with_nested_object(self):
        """DataResponse should handle nested objects."""
        response = DataResponse(
            data={"id": "123", "persona": {"name": "John", "skills": ["Python"]}}
        )
        result = response.model_dump()
        assert result["data"]["persona"]["name"] == "John"

    def test_data_response_with_list_value(self):
        """DataResponse should handle list as data value."""
        # Note: For collections, use ListResponse instead
        # This tests that DataResponse doesn't break with list
        response = DataResponse(data=["item1", "item2"])
        result = response.model_dump()
        assert result["data"] == ["item1", "item2"]


class TestListResponse:
    """Tests for ListResponse model (collection)."""

    def test_list_response_has_data_and_meta(self):
        """ListResponse should have both data and meta keys."""
        meta = PaginationMeta(total=100, page=2, per_page=20)
        response = ListResponse(
            data=[{"id": "1"}, {"id": "2"}],
            meta=meta,
        )
        result = response.model_dump()
        assert "data" in result
        assert "meta" in result

    def test_list_response_data_is_list(self):
        """ListResponse data should be a list."""
        meta = PaginationMeta(total=2, page=1, per_page=20)
        response = ListResponse(
            data=[{"id": "1"}, {"id": "2"}],
            meta=meta,
        )
        result = response.model_dump()
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2

    def test_list_response_meta_includes_pagination(self):
        """ListResponse meta should include pagination info."""
        meta = PaginationMeta(total=100, page=2, per_page=20)
        response = ListResponse(data=[], meta=meta)
        result = response.model_dump()
        assert result["meta"]["total"] == 100
        assert result["meta"]["page"] == 2
        assert result["meta"]["per_page"] == 20

    def test_list_response_empty_data(self):
        """ListResponse should handle empty data list."""
        meta = PaginationMeta(total=0, page=1, per_page=20)
        response = ListResponse(data=[], meta=meta)
        result = response.model_dump()
        assert result["data"] == []
        assert result["meta"]["total"] == 0


class TestErrorDetail:
    """Tests for ErrorDetail model."""

    def test_error_detail_required_fields(self):
        """ErrorDetail should require code and message."""
        detail = ErrorDetail(code="NOT_FOUND", message="Resource not found")
        assert detail.code == "NOT_FOUND"
        assert detail.message == "Resource not found"

    def test_error_detail_optional_details(self):
        """ErrorDetail details should default to None."""
        detail = ErrorDetail(code="TEST", message="Test")
        assert detail.details is None

    def test_error_detail_with_details(self):
        """ErrorDetail should accept details list."""
        validation_details = [
            {"loc": ["body", "email"], "msg": "invalid email"},
            {"loc": ["body", "name"], "msg": "required"},
        ]
        detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Validation failed",
            details=validation_details,
        )
        assert detail.details == validation_details


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

    def test_error_response_with_details(self):
        """ErrorResponse should include details when present."""
        detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Validation failed",
            details=[{"loc": ["body", "email"], "msg": "invalid"}],
        )
        response = ErrorResponse(error=detail)
        result = response.model_dump()
        assert result["error"]["details"] is not None
        assert len(result["error"]["details"]) == 1

    def test_error_response_null_details_when_none(self):
        """ErrorResponse should have null details when not provided."""
        detail = ErrorDetail(code="NOT_FOUND", message="Not found")
        response = ErrorResponse(error=detail)
        result = response.model_dump()
        assert result["error"]["details"] is None
