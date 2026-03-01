"""Persona settings models - voice, preferences, embeddings.

REQ-005 §4.1 - Tier 2 tables for persona metadata and settings.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, EmbeddingColumnsMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.persona import Persona  # noqa: F401

_DEFAULT_UUID = text("gen_random_uuid()")
_PERSONA_FK = "personas.id"


class VoiceProfile(Base, TimestampMixin):
    """Writing style preferences for content generation.

    One-to-one with Persona. Tier 2 - references Persona.
    Uses TimestampMixin for created_at/updated_at (with onupdate).

    REQ-005 §4.1: Database schema.
    REQ-010 §3.1: Generation impact of each field.

    Generation impact by field:
        tone: Overall emotional register for generated content.
        sentence_style: Structural preferences (length, voice).
        vocabulary_level: Word choice guidance (technical vs plain).
        personality_markers: Distinctive characteristics to reproduce.
        sample_phrases: Preferred constructions used as templates.
        things_to_avoid: Blacklisted words/phrases — absolute exclusion.
        writing_sample_text: Raw text for voice derivation by LLM.
    """

    __tablename__ = "voice_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_PERSONA_FK, ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tone: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    sentence_style: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    vocabulary_level: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    personality_markers: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sample_phrases: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    things_to_avoid: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    writing_sample_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="voice_profile",
    )


class CustomNonNegotiable(Base):
    """User-defined filter rules for job matching.

    Tier 2 - references Persona.
    """

    __tablename__ = "custom_non_negotiables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_PERSONA_FK, ondelete="CASCADE"),
        nullable=False,
    )
    filter_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    filter_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    filter_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    filter_field: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "filter_type IN ('Exclude', 'Require')",
            name="ck_customnonneg_filter_type",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="custom_non_negotiables",
    )


class PersonaEmbedding(Base, EmbeddingColumnsMixin):
    """Vector embeddings for persona matching.

    Stores hard_skills, soft_skills, logistics embeddings.
    Tier 2 - references Persona.
    """

    __tablename__ = "persona_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_PERSONA_FK, ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "embedding_type IN ('hard_skills', 'soft_skills', 'logistics')",
            name="ck_personaembedding_type",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="embeddings",
    )


class PersonaChangeFlag(Base):
    """Tracks persona changes needing HITL review.

    When user adds new job/skill/etc, flag it for base resume review.
    Tier 2 - references Persona.
    """

    __tablename__ = "persona_change_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(_PERSONA_FK, ondelete="CASCADE"),
        nullable=False,
    )
    change_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    item_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'Pending'"),
        nullable=False,
    )
    resolution: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('job_added', 'bullet_added', 'skill_added', 'education_added', 'certification_added')",
            name="ck_personachangeflag_change_type",
        ),
        CheckConstraint(
            "status IN ('Pending', 'Resolved')",
            name="ck_personachangeflag_status",
        ),
        CheckConstraint(
            "resolution IN ('added_to_all', 'added_to_some', 'skipped') OR resolution IS NULL",
            name="ck_personachangeflag_resolution",
        ),
    )

    # Relationships
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="change_flags",
    )
