"""Cover letter models - generated letters and submitted PDFs.

REQ-005 §4.3 - CoverLetter (Tier 3), SubmittedCoverLetterPDF (Tier 4).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job_posting import JobPosting
    from app.models.persona import Persona


class CoverLetter(Base):
    """AI-generated cover letter for a job application.

    Tier 3 - references Persona, JobPosting, Application (nullable).
    """

    __tablename__ = "cover_letters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable until application created - see REQ-005 §9.2
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # FK added separately after Application exists
        nullable=True,
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Achievement stories used (JSONB array of UUIDs)
    achievement_stories_used: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )

    # Content
    draft_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    final_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Draft'"),
        nullable=False,
    )

    # Agent explanation
    agent_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('Draft', 'Approved', 'Archived')",
            name="ck_coverletter_status",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="cover_letters",
    )
    job_posting: Mapped["JobPosting"] = relationship(
        "JobPosting",
        back_populates="cover_letters",
    )
    application: Mapped["Application | None"] = relationship(
        "Application",
        back_populates="cover_letter",
        foreign_keys=[application_id],
    )
    submitted_pdfs: Mapped[list["SubmittedCoverLetterPDF"]] = relationship(
        "SubmittedCoverLetterPDF",
        back_populates="cover_letter",
    )


class SubmittedCoverLetterPDF(Base):
    """Immutable PDF of cover letter submitted with application.

    BYTEA storage - actual PDF binary. Tier 4 - references CoverLetter, Application.
    """

    __tablename__ = "submitted_cover_letter_pdfs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    cover_letter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cover_letters.id", ondelete="RESTRICT"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_binary: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    cover_letter: Mapped["CoverLetter"] = relationship(
        "CoverLetter",
        back_populates="submitted_pdfs",
    )
    application: Mapped["Application | None"] = relationship(
        "Application",
        back_populates="submitted_cover_letter_pdf",
        foreign_keys=[application_id],
    )
