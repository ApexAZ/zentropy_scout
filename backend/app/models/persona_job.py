"""PersonaJob model - per-user relationship to shared job postings.

REQ-015 §4.2 - Tier 2, references Persona and JobPosting.

This table holds all user-specific fields that will be removed from
job_postings in migration 014 (status, is_favorite, scores, discovery
metadata). Each row represents one persona's relationship with one
shared job posting.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.job_posting import JobPosting
    from app.models.persona import Persona


_DEFAULT_UUID = text("gen_random_uuid()")


class PersonaJob(Base, TimestampMixin):
    """Per-user relationship to a shared job posting.

    Tier 2 - references Persona (CASCADE) and JobPosting (RESTRICT).
    """

    __tablename__ = "persona_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # User relationship
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Discovered'"),
        nullable=False,
    )
    is_favorite: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Per-user scoring (from Strategist)
    fit_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    stretch_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    failed_non_negotiables: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    score_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Discovery metadata
    discovery_method: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'pool'"),
        nullable=False,
    )

    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "persona_id", "job_posting_id", name="uq_persona_jobs_persona_job"
        ),
        CheckConstraint(
            "status IN ('Discovered', 'Dismissed', 'Applied')",
            name="ck_persona_jobs_status",
        ),
        CheckConstraint(
            "discovery_method IN ('scouter', 'manual', 'pool')",
            name="ck_persona_jobs_discovery_method",
        ),
        CheckConstraint(
            "fit_score >= 0 AND fit_score <= 100 OR fit_score IS NULL",
            name="ck_persona_jobs_fit_score",
        ),
        CheckConstraint(
            "stretch_score >= 0 AND stretch_score <= 100 OR stretch_score IS NULL",
            name="ck_persona_jobs_stretch_score",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="persona_jobs",
    )
    job_posting: Mapped["JobPosting"] = relationship(
        "JobPosting",
        back_populates="persona_jobs",
    )
