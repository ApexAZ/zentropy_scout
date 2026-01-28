"""Bulk operation request/response schemas.

REQ-006 §2.6: Bulk operations for efficiency.

These schemas define the request and response format for bulk operations
that allow partial success (some items succeed, some fail).
"""

from uuid import UUID

from pydantic import BaseModel, Field


class BulkDismissRequest(BaseModel):
    """Request body for POST /job-postings/bulk-dismiss.

    Attributes:
        ids: List of job posting UUIDs to dismiss.
    """

    ids: list[UUID] = Field(..., description="Job posting IDs to dismiss")


class BulkFavoriteRequest(BaseModel):
    """Request body for POST /job-postings/bulk-favorite.

    Attributes:
        ids: List of job posting UUIDs to update.
        is_favorite: True to favorite, False to unfavorite.
    """

    ids: list[UUID] = Field(..., description="Job posting IDs to update")
    is_favorite: bool = Field(..., description="True to favorite, False to unfavorite")


class BulkArchiveRequest(BaseModel):
    """Request body for POST /applications/bulk-archive.

    Attributes:
        ids: List of application UUIDs to archive.
    """

    ids: list[UUID] = Field(..., description="Application IDs to archive")


class BulkFailedItem(BaseModel):
    """Details about a failed item in a bulk operation.

    Attributes:
        id: The UUID of the item that failed.
        error: Error code explaining why the operation failed.
    """

    id: str = Field(..., description="UUID of the failed item")
    error: str = Field(..., description="Error code (e.g., NOT_FOUND, FORBIDDEN)")


class BulkOperationResult(BaseModel):
    """Result of a bulk operation with partial success support.

    REQ-006 §2.6: Response includes both succeeded and failed arrays.

    Attributes:
        succeeded: List of UUIDs that were successfully processed.
        failed: List of items that failed with error details.
    """

    succeeded: list[str] = Field(
        default_factory=list,
        description="UUIDs that were successfully processed",
    )
    failed: list[BulkFailedItem] = Field(
        default_factory=list,
        description="Items that failed with error details",
    )
