"""Pagination utilities.

REQ-006 §7.3: page (default 1), per_page (default 20, max 100).

WHY PAGINATION:
- Prevents memory issues with large result sets
- Improves response time for list endpoints
- Standard REST API pattern
"""

from dataclasses import dataclass

from fastapi import Query


@dataclass
class PaginationParams:
    """Pagination query parameters.

    REQ-006 §7.3: page (default 1), per_page (default 20, max 100).

    Attributes:
        page: Current page number (1-indexed).
        per_page: Number of items per page.
    """

    page: int
    per_page: int

    @property
    def offset(self) -> int:
        """Calculate SQL OFFSET for database queries.

        Returns:
            Number of items to skip (0 for page 1).
        """
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        """Calculate SQL LIMIT for database queries.

        Returns:
            Maximum number of items to return (same as per_page).
        """
        return self.per_page


def pagination_params(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Items per page (max 100)",
    ),
) -> PaginationParams:
    """FastAPI dependency for pagination query parameters.

    REQ-006 §7.3: Validates page >= 1, per_page between 1 and 100.

    Usage:
        @router.get("/items")
        async def list_items(
            pagination: PaginationParams = Depends(pagination_params)
        ):
            items = await repo.list(
                offset=pagination.offset,
                limit=pagination.limit,
            )
            ...

    Args:
        page: Page number (default 1, must be >= 1).
        per_page: Items per page (default 20, between 1 and 100).

    Returns:
        PaginationParams with validated page and per_page.
    """
    return PaginationParams(page=page, per_page=per_page)
