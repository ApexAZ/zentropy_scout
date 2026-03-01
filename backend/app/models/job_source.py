"""Job source models - where jobs come from.

REQ-005 §4.4 - JobSource (Tier 0), UserSourcePreference, PollingConfiguration (Tier 2).
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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.job_posting import JobPosting  # noqa: F401
    from app.models.persona import Persona  # noqa: F401

_DEFAULT_UUID = text("gen_random_uuid()")


class JobSource(Base, TimestampMixin):
    """Global registry of job sources (LinkedIn, Indeed, etc.).

    Tier 0 - no FK dependencies.
    """

    __tablename__ = "job_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    source_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    api_endpoint: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('API', 'Extension', 'Manual')",
            name="ck_jobsource_source_type",
        ),
    )

    # Relationships
    user_preferences: Mapped[list["UserSourcePreference"]] = relationship(
        "UserSourcePreference",
        back_populates="job_source",
        cascade="all, delete-orphan",
    )
    job_postings: Mapped[list["JobPosting"]] = relationship(
        "JobPosting",
        back_populates="source",
    )


class UserSourcePreference(Base):
    """User's preference for a job source (enabled/disabled, order).

    Tier 2 - references Persona and JobSource.
    """

    __tablename__ = "user_source_preferences"

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
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("true"),
        nullable=False,
    )
    display_order: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "persona_id", "source_id", name="uq_usersourcepref_persona_source"
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="source_preferences",
    )
    job_source: Mapped["JobSource"] = relationship(
        "JobSource",
        back_populates="user_preferences",
    )


class PollingConfiguration(Base):
    """Per-persona polling schedule for job discovery.

    Tier 2 - references Persona (one-to-one).
    """

    __tablename__ = "polling_configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    last_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="polling_configuration",
    )
