"""Persona content models - work history, skills, education, etc.

REQ-005 §4.1 - Tier 2 tables that hold persona's professional content.
Bullet is Tier 3 (references WorkHistory).
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkHistory(Base):
    """Employment record - job held by the persona.

    Tier 2 - references Persona.
    """

    __tablename__ = "work_histories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    company_industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    job_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        server_default=sa_text("false"),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    work_model: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=sa_text("0"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "work_model IN ('Remote', 'Hybrid', 'Onsite')",
            name="ck_workhistory_work_model",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="work_histories",
    )
    bullets: Mapped[list["Bullet"]] = relationship(
        "Bullet",
        back_populates="work_history",
        cascade="all, delete-orphan",
    )
    achievement_stories: Mapped[list["AchievementStory"]] = relationship(
        "AchievementStory",
        back_populates="related_job",
    )


class Bullet(Base):
    """Achievement bullet point under a work history entry.

    Tier 3 - references WorkHistory.
    """

    __tablename__ = "bullets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    work_history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_histories.id", ondelete="CASCADE"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    skills_demonstrated: Mapped[list] = mapped_column(
        JSONB,
        server_default=sa_text("'[]'::jsonb"),
        nullable=False,
    )
    metrics: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=sa_text("0"),
        nullable=False,
    )

    # Relationships
    work_history: Mapped["WorkHistory"] = relationship(
        "WorkHistory",
        back_populates="bullets",
    )


class Skill(Base):
    """Professional skill possessed by the persona.

    Tier 2 - references Persona.
    """

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
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
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    proficiency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    years_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    last_used: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=sa_text("0"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("persona_id", "skill_name", name="uq_skill_persona_name"),
        CheckConstraint(
            "skill_type IN ('Hard', 'Soft')",
            name="ck_skill_skill_type",
        ),
        CheckConstraint(
            "proficiency IN ('Learning', 'Familiar', 'Proficient', 'Expert')",
            name="ck_skill_proficiency",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="skills",
    )


class Education(Base):
    """Educational background entry.

    Tier 2 - references Persona.
    """

    __tablename__ = "educations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    institution: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    degree: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    field_of_study: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    graduation_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    gpa: Mapped[float | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    honors: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=sa_text("0"),
        nullable=False,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="educations",
    )


class Certification(Base):
    """Professional certification held by the persona.

    Tier 2 - references Persona.
    """

    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    certification_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    issuing_organization: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    date_obtained: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    expiration_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    credential_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    verification_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=sa_text("0"),
        nullable=False,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="certifications",
    )


class AchievementStory(Base):
    """STAR-format achievement story for cover letters.

    Tier 2 - references Persona, WorkHistory.
    """

    __tablename__ = "achievement_stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa_text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    skills_demonstrated: Mapped[list] = mapped_column(
        JSONB,
        server_default=sa_text("'[]'::jsonb"),
        nullable=False,
    )
    related_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_histories.id", ondelete="SET NULL"),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=sa_text("0"),
        nullable=False,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="achievement_stories",
    )
    related_job: Mapped["WorkHistory | None"] = relationship(
        "WorkHistory",
        back_populates="achievement_stories",
    )


# Avoid circular imports
from app.models.persona import Persona  # noqa: E402, F401
