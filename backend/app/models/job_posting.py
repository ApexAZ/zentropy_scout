"""Job posting models - discovered jobs and extracted skills.

REQ-005 §4.4 - JobPosting (Tier 2), ExtractedSkill (Tier 3).
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, EmbeddingColumnsMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.cover_letter import CoverLetter
    from app.models.job_source import JobSource
    from app.models.persona import Persona
    from app.models.resume import JobVariant


_DEFAULT_UUID = text("gen_random_uuid()")


class JobPosting(Base, TimestampMixin):
    """Job posting discovered from various sources.

    Tier 2 - references Persona, JobSource.
    """

    __tablename__ = "job_postings"

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
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Deduplication tracking
    also_found_on: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{\"sources\": []}'::jsonb"),
        nullable=False,
    )

    # Basic info
    job_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    company_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    apply_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Location and work model
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    work_model: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Level and compensation
    seniority_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    salary_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    salary_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    salary_currency: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # Content
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    culture_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    requirements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    raw_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Experience requirements
    years_experience_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    years_experience_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Dates
    posted_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    application_deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    first_seen_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # Status and tracking
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

    # Scoring
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

    # Ghost detection
    ghost_signals: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ghost_score: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )

    # Repost detection
    description_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    repost_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    previous_posting_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Timestamps
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "work_model IN ('Remote', 'Hybrid', 'Onsite') OR work_model IS NULL",
            name="ck_jobposting_work_model",
        ),
        CheckConstraint(
            "seniority_level IN ('Entry', 'Mid', 'Senior', 'Lead', 'Executive') OR seniority_level IS NULL",
            name="ck_jobposting_seniority",
        ),
        CheckConstraint(
            "status IN ('Discovered', 'Dismissed', 'Applied', 'Expired')",
            name="ck_jobposting_status",
        ),
        CheckConstraint(
            "fit_score >= 0 AND fit_score <= 100 OR fit_score IS NULL",
            name="ck_jobposting_fit_score",
        ),
        CheckConstraint(
            "stretch_score >= 0 AND stretch_score <= 100 OR stretch_score IS NULL",
            name="ck_jobposting_stretch_score",
        ),
        CheckConstraint(
            "ghost_score >= 0 AND ghost_score <= 100",
            name="ck_jobposting_ghost_score",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="job_postings",
    )
    source: Mapped["JobSource"] = relationship(
        "JobSource",
        back_populates="job_postings",
    )
    extracted_skills: Mapped[list["ExtractedSkill"]] = relationship(
        "ExtractedSkill",
        back_populates="job_posting",
        cascade="all, delete-orphan",
    )
    job_variants: Mapped[list["JobVariant"]] = relationship(
        "JobVariant",
        back_populates="job_posting",
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(
        "CoverLetter",
        back_populates="job_posting",
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application",
        back_populates="job_posting",
    )
    embeddings: Mapped[list["JobEmbedding"]] = relationship(
        "JobEmbedding",
        back_populates="job_posting",
        cascade="all, delete-orphan",
    )


class ExtractedSkill(Base):
    """Skill extracted from job posting by LLM.

    Tier 3 - references JobPosting.
    """

    __tablename__ = "extracted_skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    skill_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    years_requested: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "skill_type IN ('Hard', 'Soft')",
            name="ck_extractedskill_skill_type",
        ),
    )

    # Relationships
    job_posting: Mapped["JobPosting"] = relationship(
        "JobPosting",
        back_populates="extracted_skills",
    )


class JobEmbedding(Base, EmbeddingColumnsMixin):
    """Vector embeddings for job matching.

    Stores requirements and culture embeddings.
    Tier 3 - references JobPosting.
    """

    __tablename__ = "job_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "embedding_type IN ('requirements', 'culture')",
            name="ck_jobembedding_type",
        ),
    )

    # Relationships
    job_posting: Mapped["JobPosting"] = relationship(
        "JobPosting",
        back_populates="embeddings",
    )
