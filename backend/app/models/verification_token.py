"""Verification token model - magic link tokens.

REQ-013 §6.4 - Stores magic link tokens. Single-use, time-limited.
No id column — looked up by (identifier, token) composite key.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VerificationToken(Base):
    """Magic link verification token.

    Entries are single-use and time-limited. Looked up by composite key
    (identifier, token) and deleted after use.

    Attributes:
        identifier: Email address.
        token: Hashed token value.
        expires: Token expiry timestamp.
        purpose: Token intent — ``"sign_in"`` or ``"password_reset"``.
    """

    __tablename__ = "verification_tokens"
    __table_args__ = (
        UniqueConstraint(
            "identifier", "token", name="uq_verification_tokens_identifier_token"
        ),
    )

    # No UUID id — composite key via unique constraint
    # Use identifier as the "primary key" for SQLAlchemy ORM mapping
    identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
    )
    token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        primary_key=True,
    )
    expires: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="sign_in",
    )
