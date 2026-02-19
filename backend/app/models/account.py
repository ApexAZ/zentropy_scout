"""Account model - OAuth provider connections.

REQ-013 §6.2 - Stores identity provider connections.
Multiple rows per user (one per provider).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User

_DEFAULT_UUID = text("gen_random_uuid()")


class Account(Base):
    """OAuth/credentials provider connection for a user.

    OAuth tokens (refresh_token, access_token) are encrypted at the
    application layer before storage. See Phase 1 §3 for encryption
    implementation.

    Attributes:
        id: UUID primary key.
        user_id: FK to users table.
        type: Account type ("oauth", "email", "credentials").
        provider: Provider name ("google", "linkedin", "email", "credentials").
        provider_account_id: Provider's unique user ID.
        refresh_token: OAuth refresh token (encrypted at application layer).
        access_token: OAuth access token (encrypted at application layer).
        expires_at: Token expiry (Unix timestamp).
        token_type: Token type (e.g., "bearer").
        scope: OAuth scopes granted.
        id_token: OIDC ID token.
        session_state: Provider session state.
        created_at: Record creation timestamp.
    """

    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_accounts_provider_account"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expires_at: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    token_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scope: Mapped[str | None] = mapped_column(Text(), nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    session_state: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="accounts")
