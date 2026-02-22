"""Application models - job applications and timeline events.

REQ-005 §4.5 - Application (Tier 4), TimelineEvent (Tier 5).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin

_DEFAULT_UUID = text("gen_random_uuid()")
_ON_DELETE_SET_NULL = "SET NULL"

if TYPE_CHECKING:
    from app.models.cover_letter import CoverLetter, SubmittedCoverLetterPDF
    from app.models.job_posting import JobPosting
    from app.models.persona import Persona
    from app.models.persona_job import PersonaJob
    from app.models.resume import JobVariant, SubmittedResumePDF


class Application(Base, TimestampMixin, SoftDeleteMixin):
    """Job application record tracking status and materials.

    Tier 4 - references Persona, JobPosting, JobVariant, CoverLetter, SubmittedPDFs.
    """

    __tablename__ = "applications"

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
    job_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_variants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cover_letter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cover_letters.id", ondelete=_ON_DELETE_SET_NULL),
        nullable=True,
    )

    # PersonaJob link (REQ-015 §11 step 7)
    persona_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persona_jobs.id", ondelete=_ON_DELETE_SET_NULL),
        nullable=True,
    )

    # Submitted PDF links (nullable for bidirectional FK - see REQ-005 §9.2)
    # use_alter=True handles circular dependency at migration level
    submitted_resume_pdf_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "submitted_resume_pdfs.id",
            ondelete=_ON_DELETE_SET_NULL,
            use_alter=True,
            name="fk_application_submitted_resume_pdf",
        ),
        nullable=True,
    )
    submitted_cover_letter_pdf_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "submitted_cover_letter_pdfs.id",
            ondelete=_ON_DELETE_SET_NULL,
            use_alter=True,
            name="fk_application_submitted_cover_letter_pdf",
        ),
        nullable=True,
    )

    # Frozen job snapshot at application time
    job_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Applied'"),
        nullable=False,
    )
    current_interview_stage: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    # Outcome details
    offer_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    rejection_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Pin control (REQ-012 Appendix A.1; archived_at inherited from SoftDeleteMixin)
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )

    # Timestamps
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "persona_id", "job_posting_id", name="uq_application_persona_job"
        ),
        CheckConstraint(
            "status IN ('Applied', 'Interviewing', 'Offer', 'Accepted', 'Rejected', 'Withdrawn')",
            name="ck_application_status",
        ),
        CheckConstraint(
            "current_interview_stage IN ('Phone Screen', 'Onsite', 'Final Round') OR current_interview_stage IS NULL",
            name="ck_application_interview_stage",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="applications",
    )
    job_posting: Mapped["JobPosting"] = relationship(
        "JobPosting",
        back_populates="applications",
    )
    job_variant: Mapped["JobVariant"] = relationship(
        "JobVariant",
        back_populates="applications",
    )
    persona_job: Mapped["PersonaJob | None"] = relationship(
        "PersonaJob",
        back_populates="applications",
    )
    # Note: CoverLetter.application is viewonly due to bidirectional FK pattern
    cover_letter: Mapped["CoverLetter | None"] = relationship(
        "CoverLetter",
        foreign_keys=[cover_letter_id],
    )
    submitted_resume_pdf: Mapped["SubmittedResumePDF | None"] = relationship(
        "SubmittedResumePDF",
        back_populates="application",
        foreign_keys="SubmittedResumePDF.application_id",
    )
    submitted_cover_letter_pdf: Mapped["SubmittedCoverLetterPDF | None"] = relationship(
        "SubmittedCoverLetterPDF",
        back_populates="application",
        foreign_keys="SubmittedCoverLetterPDF.application_id",
    )
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        "TimelineEvent",
        back_populates="application",
        cascade="all, delete-orphan",
    )


class TimelineEvent(Base):
    """Event in an application's history timeline.

    Tier 5 - references Application.
    """

    __tablename__ = "timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    interview_stage: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('applied', 'status_changed', 'note_added', 'interview_scheduled', "
            "'interview_completed', 'offer_received', 'offer_accepted', 'rejected', 'withdrawn', "
            "'follow_up_sent', 'response_received', 'custom')",
            name="ck_timelineevent_event_type",
        ),
        CheckConstraint(
            "interview_stage IN ('Phone Screen', 'Onsite', 'Final Round') OR interview_stage IS NULL",
            name="ck_timelineevent_interview_stage",
        ),
    )

    # Relationships
    application: Mapped["Application"] = relationship(
        "Application",
        back_populates="timeline_events",
    )
