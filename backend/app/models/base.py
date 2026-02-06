"""SQLAlchemy base classes and common mixins.

REQ-005 §2.1: Defines the declarative base and reusable mixins for
timestamp tracking, soft delete, and embedding storage across all models.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, func
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


class EmbeddingColumnsMixin:
    """Mixin for vector embedding storage columns.

    Shared by PersonaEmbedding and JobEmbedding. Each model adds its own
    foreign key (persona_id / job_posting_id) and CheckConstraint for
    allowed embedding_type values.

    Attributes:
        embedding_type: Category of embedding (e.g., 'hard_skills', 'culture').
        vector: 1536-dimensional vector (OpenAI text-embedding-3-small).
        model_name: Name of the embedding model used.
        model_version: Version of the embedding model.
        source_hash: SHA-256 hash of the source text for change detection.
        created_at: When the embedding was generated.
    """

    embedding_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    # Vector column for 1536-dimensional embeddings (OpenAI text-embedding-3-small)
    vector: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    source_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
