"""Session model - active session tracking.

REQ-013 §6.3 - Tracks active JWT sessions for session management
and "sign out everywhere" functionality.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User

_DEFAULT_UUID = text("gen_random_uuid()")


class Session(Base):
    """Active user session record.

    Each JWT issuance creates a session record. Used for listing active
    sessions and bulk revocation.

    Attributes:
        id: UUID primary key.
        session_token: Unique session identifier.
        user_id: FK to users table.
        expires: Session expiry timestamp.
        created_at: Session creation timestamp.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    session_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
