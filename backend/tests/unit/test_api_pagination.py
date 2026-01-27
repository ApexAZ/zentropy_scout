"""Tests for pagination utilities.

REQ-006 §7.3: Pagination query parameters.
"""

from app.core.pagination import PaginationParams, pagination_params


class TestPaginationParams:
    """Tests for PaginationParams dataclass."""

    def test_pagination_params_stores_values(self):
        """PaginationParams should store page and per_page."""
        params = PaginationParams(page=3, per_page=25)
        assert params.page == 3
        assert params.per_page == 25

    def test_offset_page_one(self):
        """Page 1 should have offset 0."""
        params = PaginationParams(page=1, per_page=20)
        assert params.offset == 0

    def test_offset_page_two(self):
        """Page 2 should have offset equal to per_page."""
        params = PaginationParams(page=2, per_page=20)
        assert params.offset == 20

    def test_offset_calculation(self):
        """Offset should be (page - 1) * per_page."""
        params = PaginationParams(page=5, per_page=10)
        assert params.offset == 40  # (5 - 1) * 10

    def test_limit_equals_per_page(self):
        """Limit should equal per_page."""
        params = PaginationParams(page=1, per_page=50)
        assert params.limit == 50

    def test_limit_different_per_page(self):
        """Limit should vary with per_page."""
        params = PaginationParams(page=1, per_page=15)
        assert params.limit == 15


class TestPaginationParamsDependency:
    """Tests for pagination_params FastAPI dependency.

    Note: Query defaults only resolve through FastAPI's dependency injection.
    These tests verify the function accepts and returns correct values.
    Integration tests should verify FastAPI default behavior.
    """

    def test_accepts_page_and_per_page(self):
        """pagination_params should accept page and per_page args."""
        params = pagination_params(page=3, per_page=25)
        assert params.page == 3
        assert params.per_page == 25

    def test_returns_pagination_params_instance(self):
        """pagination_params should return PaginationParams instance."""
        params = pagination_params(page=1, per_page=20)
        assert isinstance(params, PaginationParams)

    def test_offset_and_limit_work_on_result(self):
        """Result should have working offset and limit properties."""
        params = pagination_params(page=5, per_page=10)
        assert params.offset == 40
        assert params.limit == 10
