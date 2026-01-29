"""SQLAlchemy base classes and common mixins.

REQ-005 §2.1: Defines the declarative base and reusable mixins for
timestamp tracking and soft delete functionality across all models.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns.

    Attributes:
        created_at: Timestamp when the record was created. Set automatically
            by the database on insert.
        updated_at: Timestamp when the record was last modified. Updated
            automatically by the database on each update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that adds soft delete capability.

    Records are not physically deleted; instead, archived_at is set to the
    current timestamp. Queries should filter out archived records by default.

    Attributes:
        archived_at: Timestamp when the record was archived (soft deleted).
            None if the record is active.
    """

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_archived(self) -> bool:
        """Check if the record has been soft deleted.

        Returns:
            True if archived_at is set, False otherwise.
        """
        return self.archived_at is not None
