"""Pydantic request/response schemas for API endpoints."""

from app.schemas.bulk import (
    BulkArchiveRequest,
    BulkDismissRequest,
    BulkFailedItem,
    BulkFavoriteRequest,
    BulkOperationResult,
)

__all__ = [
    "BulkArchiveRequest",
    "BulkDismissRequest",
    "BulkFailedItem",
    "BulkFavoriteRequest",
    "BulkOperationResult",
]
