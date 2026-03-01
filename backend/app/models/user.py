"""User model - authentication foundation.

REQ-005 §4.0 - Tier 0, no FK dependencies.
REQ-013 §6.1 - Expanded with auth columns.
REQ-020 §4.1 - balance_usd for token metering.
REQ-022 §4.1 - is_admin for admin access control.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.persona import Persona
    from app.models.session import Session

_DEFAULT_UUID = text("gen_random_uuid()")
_CASCADE_ALL_DELETE_ORPHAN = "all, delete-orphan"


class User(Base, TimestampMixin):
    """User account for authentication.

    Attributes:
        id: UUID primary key.
        email: Unique email address.
        name: Display name (populated from OAuth or registration).
        email_verified: Timestamp when email was verified. NULL = unverified.
        image: Profile picture URL from OAuth provider.
        created_at: Account creation timestamp (from TimestampMixin).
        updated_at: Last modification timestamp (from TimestampMixin).
        password_hash: bcrypt hash. NULL for OAuth-only users.
        token_invalidated_before: JWTs issued before this are rejected.
        balance_usd: Cached balance in USD (Numeric 10,6). Defaults to 0.
        is_admin: Whether the user has admin privileges. Defaults to False.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    email_verified: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    image: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    token_invalidated_before: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
        server_default=text("0.000000"),
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )

    # Relationships
    personas: Mapped[list["Persona"]] = relationship(
        "Persona",
        back_populates="user",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    accounts: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="user",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade=_CASCADE_ALL_DELETE_ORPHAN,
    )
