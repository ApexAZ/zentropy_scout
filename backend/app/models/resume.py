"""Resume models - files, base resumes, variants, submitted PDFs.

REQ-005 §4.2 - ResumeFile, BaseResume (Tier 2), JobVariant (Tier 3), SubmittedResumePDF (Tier 4).
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
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

_DEFAULT_UUID = text("gen_random_uuid()")
_DEFAULT_EMPTY_JSONB_ARRAY = text("'[]'::jsonb")
_DEFAULT_EMPTY_JSONB_OBJECT = text("'{}'::jsonb")

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.job_posting import JobPosting
    from app.models.persona import Persona


class ResumeFile(Base):
    """Uploaded resume file stored as binary.

    BYTEA storage - no filesystem paths. Tier 2 - references Persona.
    """

    __tablename__ = "resume_files"

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
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    file_binary: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "file_type IN ('PDF', 'DOCX')",
            name="ck_resumefile_file_type",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="resume_files",
        foreign_keys=[persona_id],
    )


class BaseResume(Base):
    """Master resume template for a role type.

    Contains selections of jobs, bullets, skills to include.
    Tier 2 - references Persona.
    """

    __tablename__ = "base_resumes"

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
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    role_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Selections (JSONB arrays of UUIDs)
    included_jobs: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_ARRAY,
        nullable=False,
    )
    included_education: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_ARRAY,
        nullable=False,
    )
    included_certifications: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_ARRAY,
        nullable=False,
    )
    skills_emphasis: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_ARRAY,
        nullable=False,
    )

    # Bullet ordering (JSONB maps: job_id -> [bullet_ids])
    job_bullet_selections: Mapped[dict] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_OBJECT,
        nullable=False,
    )
    job_bullet_order: Mapped[dict] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_OBJECT,
        nullable=False,
    )

    # Rendered PDF (BYTEA - anchor document)
    rendered_document: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    rendered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Status
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Active'"),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
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
        UniqueConstraint("persona_id", "name", name="uq_baseresume_persona_name"),
        CheckConstraint(
            "status IN ('Active', 'Archived')",
            name="ck_baseresume_status",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="base_resumes",
    )
    job_variants: Mapped[list["JobVariant"]] = relationship(
        "JobVariant",
        back_populates="base_resume",
    )


class JobVariant(Base):
    """Job-specific tailored version of a base resume.

    Contains modified summary and bullet ordering for specific job.
    Tier 3 - references BaseResume, JobPosting.
    """

    __tablename__ = "job_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    base_resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("base_resumes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    job_bullet_order: Mapped[dict] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB_OBJECT,
        nullable=False,
    )
    modifications_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Draft'"),
        nullable=False,
    )

    # Snapshots (JSONB - populated on approval, frozen copy of base resume selections)
    snapshot_included_jobs: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    snapshot_job_bullet_selections: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    snapshot_included_education: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    snapshot_included_certifications: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    snapshot_skills_emphasis: Mapped[dict | None] = mapped_column(
        JSONB,
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
            name="ck_jobvariant_status",
        ),
    )

    # Relationships
    base_resume: Mapped["BaseResume"] = relationship(
        "BaseResume",
        back_populates="job_variants",
    )
    job_posting: Mapped["JobPosting"] = relationship(
        "JobPosting",
        back_populates="job_variants",
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application",
        back_populates="job_variant",
    )


class SubmittedResumePDF(Base):
    """Immutable PDF submitted with an application.

    BYTEA storage - actual PDF binary. Tier 4 - references Application.
    """

    __tablename__ = "submitted_resume_pdfs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    resume_source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    # App-enforced FK - points to BaseResume or JobVariant
    resume_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
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

    __table_args__ = (
        CheckConstraint(
            "resume_source_type IN ('Base', 'Variant')",
            name="ck_submittedresumepdf_source_type",
        ),
    )

    # Relationships
    application: Mapped["Application | None"] = relationship(
        "Application",
        back_populates="submitted_resume_pdf",
        foreign_keys=[application_id],
    )
