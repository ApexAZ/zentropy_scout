"""Resume template model for markdown-based resume generation.

REQ-025 §4.3 - ResumeTemplate (Tier 1 - references User optionally).

Coordinates with:
  - models/base.py — imports Base
  - models/user.py — imports User (TYPE_CHECKING, ORM relationship)

Called by: services/generation/resume_generation_service.py,
services/rendering/resume_template_service.py, api/v1/base_resumes.py,
api/v1/resume_templates.py, repositories/resume_template_repository.py,
models/resume.py (TYPE_CHECKING).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

_DEFAULT_UUID = text("gen_random_uuid()")

if TYPE_CHECKING:
    from app.models.user import User


class ResumeTemplate(Base):
    """Markdown template skeleton for resume generation.

    System templates (is_system=True, user_id=NULL) are seeded via migration
    and cannot be modified by users. User templates (is_system=False,
    user_id=<uuid>) are owned by a specific user and can be CRUD'd.

    Access control boundary: Any query returning templates MUST filter to
    system templates OR the requesting user's own templates:
        WHERE is_system = true OR user_id = :current_user_id
    """

    __tablename__ = "resume_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    markdown_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
