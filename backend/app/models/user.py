"""User model - authentication foundation.

REQ-005 §4.0 - Tier 0, no FK dependencies.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    """User account for authentication.

    Minimal for MVP - just email. Future: password hash, OAuth, etc.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    personas: Mapped[list["Persona"]] = relationship(
        "Persona",
        back_populates="user",
        cascade="all, delete-orphan",
    )


# Avoid circular import - Persona imported at runtime
from app.models.persona import Persona  # noqa: E402, F401
