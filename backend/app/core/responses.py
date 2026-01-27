"""Response envelope models.

REQ-006 §7.2: Consistent response format for all API endpoints.

WHY RESPONSE ENVELOPES:
- Consistent structure across all endpoints
- Easy to distinguish success from error responses
- Pagination metadata in a predictable location
- Type-safe response building in endpoints
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, computed_field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata for collections.

    REQ-006 §7.3: Included in all list responses.

    Attributes:
        total: Total number of items across all pages.
        page: Current page number (1-indexed).
        per_page: Number of items per page.
    """

    total: int
    page: int
    per_page: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages.

        Returns:
            Number of pages needed to display all items.
            Returns 0 if total is 0.
        """
        if self.total == 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page


class DataResponse(BaseModel, Generic[T]):
    """Standard response envelope for single resources.

    REQ-006 §7.2: All success responses use {"data": ...} envelope.

    Usage:
        @router.get("/personas/{id}")
        async def get_persona(id: UUID) -> DataResponse[PersonaSchema]:
            persona = await service.get(id)
            return DataResponse(data=persona)
    """

    data: T


class ListResponse(BaseModel, Generic[T]):
    """Standard response envelope for collections.

    REQ-006 §7.2: Collection responses include pagination meta.

    Usage:
        @router.get("/personas")
        async def list_personas(
            pagination: PaginationParams = Depends(pagination_params)
        ) -> ListResponse[PersonaSchema]:
            personas, total = await service.list(pagination)
            return ListResponse(
                data=personas,
                meta=PaginationMeta(
                    total=total,
                    page=pagination.page,
                    per_page=pagination.per_page,
                ),
            )
    """

    data: list[T]
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    """Error detail for response body.

    REQ-006 §8.2: Consistent error code and message format.

    Attributes:
        code: Machine-readable error code (e.g., "NOT_FOUND").
        message: Human-readable error message.
        details: Optional list of field-level errors (for validation).
    """

    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    REQ-006 §7.2: All errors use {"error": {...}} envelope.

    Usage in exception handlers:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(code=exc.code, message=exc.message)
            ).model_dump(),
        )
    """

    error: ErrorDetail
