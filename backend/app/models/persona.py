"""Persona model - user's professional identity.

REQ-005 §4.1 - Tier 1, references User.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

_CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.cover_letter import CoverLetter
    from app.models.job_posting import JobPosting
    from app.models.job_source import PollingConfiguration, UserSourcePreference
    from app.models.persona_content import (
        AchievementStory,
        Certification,
        Education,
        Skill,
        WorkHistory,
    )
    from app.models.persona_settings import (
        CustomNonNegotiable,
        PersonaChangeFlag,
        PersonaEmbedding,
        VoiceProfile,
    )
    from app.models.resume import BaseResume, ResumeFile
    from app.models.user import User


_DEFAULT_EMPTY_JSONB = text("'[]'::jsonb")


class Persona(Base, TimestampMixin):
    """User's professional identity containing all career data.

    Central entity linking to work history, skills, education, etc.
    Tier 1 - references User.
    """

    __tablename__ = "personas"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # User reference (Tier 1 dependency)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Contact information
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Location
    home_city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    home_state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    home_country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Online presence
    linkedin_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    portfolio_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Professional summary
    professional_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    years_experience: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    current_role: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    current_company: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Career goals (JSONB arrays)
    target_roles: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB,
        nullable=False,
    )
    target_skills: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB,
        nullable=False,
    )

    # Location preferences (JSONB arrays)
    commutable_cities: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB,
        nullable=False,
    )
    relocation_cities: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB,
        nullable=False,
    )
    industry_exclusions: Mapped[list] = mapped_column(
        JSONB,
        server_default=_DEFAULT_EMPTY_JSONB,
        nullable=False,
    )

    # Preferences
    stretch_appetite: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Medium'"),
        nullable=False,
    )
    minimum_base_salary: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    salary_currency: Mapped[str] = mapped_column(
        String(10),
        server_default=text("'USD'"),
        nullable=False,
    )
    max_commute_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    remote_preference: Mapped[str] = mapped_column(
        String(30),
        server_default=text("'No Preference'"),
        nullable=False,
    )
    relocation_open: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    visa_sponsorship_required: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    company_size_preference: Mapped[str] = mapped_column(
        String(30),
        server_default=text("'No Preference'"),
        nullable=False,
    )
    max_travel_percent: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Any'"),
        nullable=False,
    )

    # Matching thresholds
    minimum_fit_threshold: Mapped[int] = mapped_column(
        Integer,
        server_default=text("50"),
        nullable=False,
    )
    auto_draft_threshold: Mapped[int] = mapped_column(
        Integer,
        server_default=text("90"),
        nullable=False,
    )

    # Polling settings
    polling_frequency: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Daily'"),
        nullable=False,
    )

    # Onboarding state
    onboarding_complete: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    onboarding_step: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Original uploaded resume (nullable FK added in Tier 2)
    # use_alter=True handles circular dependency with ResumeFile at migration level
    original_resume_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "resume_files.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_persona_original_resume_file",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "stretch_appetite IN ('Low', 'Medium', 'High')",
            name="ck_persona_stretch_appetite",
        ),
        CheckConstraint(
            "remote_preference IN ('Remote Only', 'Hybrid OK', 'Onsite OK', 'No Preference')",
            name="ck_persona_remote_preference",
        ),
        CheckConstraint(
            "company_size_preference IN ('Startup', 'Mid-size', 'Enterprise', 'No Preference')",
            name="ck_persona_company_size",
        ),
        CheckConstraint(
            "max_travel_percent IN ('None', '<25%', '<50%', 'Any')",
            name="ck_persona_max_travel",
        ),
        CheckConstraint(
            "polling_frequency IN ('Daily', 'Twice Daily', 'Weekly', 'Manual Only')",
            name="ck_persona_polling_frequency",
        ),
        CheckConstraint(
            "minimum_fit_threshold >= 0 AND minimum_fit_threshold <= 100",
            name="ck_persona_fit_threshold",
        ),
        CheckConstraint(
            "auto_draft_threshold >= 0 AND auto_draft_threshold <= 100",
            name="ck_persona_draft_threshold",
        ),
    )

    # Relationships to User (Tier 0)
    user: Mapped["User"] = relationship(
        "User",
        back_populates="personas",
    )

    # Relationships to Tier 2 persona content
    work_histories: Mapped[list["WorkHistory"]] = relationship(
        "WorkHistory",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    skills: Mapped[list["Skill"]] = relationship(
        "Skill",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    educations: Mapped[list["Education"]] = relationship(
        "Education",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    certifications: Mapped[list["Certification"]] = relationship(
        "Certification",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    achievement_stories: Mapped[list["AchievementStory"]] = relationship(
        "AchievementStory",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )

    # Relationships to Tier 2 persona settings
    voice_profile: Mapped["VoiceProfile | None"] = relationship(
        "VoiceProfile",
        back_populates="persona",
        uselist=False,
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    custom_non_negotiables: Mapped[list["CustomNonNegotiable"]] = relationship(
        "CustomNonNegotiable",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    embeddings: Mapped[list["PersonaEmbedding"]] = relationship(
        "PersonaEmbedding",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    change_flags: Mapped[list["PersonaChangeFlag"]] = relationship(
        "PersonaChangeFlag",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )

    # Relationships to resume domain
    resume_files: Mapped[list["ResumeFile"]] = relationship(
        "ResumeFile",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
        foreign_keys="ResumeFile.persona_id",
    )
    original_resume_file: Mapped["ResumeFile | None"] = relationship(
        "ResumeFile",
        foreign_keys=[original_resume_file_id],
        post_update=True,
    )
    base_resumes: Mapped[list["BaseResume"]] = relationship(
        "BaseResume",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )

    # Relationships to job source preferences
    source_preferences: Mapped[list["UserSourcePreference"]] = relationship(
        "UserSourcePreference",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    polling_configuration: Mapped["PollingConfiguration | None"] = relationship(
        "PollingConfiguration",
        back_populates="persona",
        uselist=False,
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )

    # Relationships to job/application domain
    job_postings: Mapped[list["JobPosting"]] = relationship(
        "JobPosting",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(
        "CoverLetter",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application",
        back_populates="persona",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
