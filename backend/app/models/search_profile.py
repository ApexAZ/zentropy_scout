"""SearchProfile ORM model — AI-generated job search criteria for a persona.

REQ-034 §4.2: One profile per persona, split into fit_searches and
stretch_searches JSONB buckets. Staleness tracked via persona_fingerprint
(SHA-256 of material persona fields).

Coordinates with:
  - models/persona.py: Persona (FK parent, one-to-one; back-populated as persona.search_profile)
  - models/base.py: Base, TimestampMixin

Called by / Used by:
  - repositories/search_profile_repository.py: CRUD operations
  - services/discovery/search_profile_service.py: fingerprint, staleness, AI generation
  - api/v1/search_profiles.py: GET/POST/PATCH endpoints
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.persona import Persona


class SearchProfile(Base, TimestampMixin):
    """AI-generated job search criteria for a persona.

    One profile per persona. fit_searches holds current-fit roles;
    stretch_searches holds growth-target roles. is_stale is set True
    whenever material persona fields change (tracked via persona_fingerprint).

    Attributes:
        id: UUID primary key.
        persona_id: FK to personas.id (UNIQUE — one profile per persona, CASCADE delete).
        fit_searches: List of SearchBucket dicts for current-fit roles.
        stretch_searches: List of SearchBucket dicts for growth-target roles.
        persona_fingerprint: SHA-256 hex digest of material persona fields at generation time.
        is_stale: True when persona has changed since last generation.
        generated_at: Timestamp when AI generated this profile (None until first generation).
        approved_at: Timestamp when user approved the profile (None until approved).
        created_at: Record creation timestamp (from TimestampMixin).
        updated_at: Record last-modified timestamp (from TimestampMixin).
    """

    __tablename__ = "search_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    fit_searches: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    stretch_searches: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    # SHA-256 hex digest (64 chars) of material persona fields at generation time.
    # Empty string is the valid un-generated default — is_stale guards against
    # false-match comparisons between two un-generated profiles.
    persona_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("''"),
    )
    # True until user approves; set True again on material persona change.
    # Defaults to True (safe-fail: treat as stale until proven current).
    is_stale: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    # Nullable: profile row may exist before generation/approval
    generated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationship back to Persona (child side, FK owner)
    persona: Mapped["Persona"] = relationship(
        "Persona",
        back_populates="search_profile",
    )
