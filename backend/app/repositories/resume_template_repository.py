"""Repository for ResumeTemplate CRUD operations.

REQ-025 §4.3, §6.4: Database access for resume templates with
access control scoping (system templates + user's own templates).

Coordinates with:
  - models/resume_template.py (ResumeTemplate ORM model)

Called by: services/rendering/resume_template_service.py.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume_template import ResumeTemplate


class SystemTemplateError(ValueError):
    """Raised when attempting to modify or delete a system template."""


_MAX_LIST_RESULTS = 100
"""Safety bound on list query results (defense-in-depth)."""

# Fields that may be updated via ResumeTemplateRepository.update().
# Security: Never add 'id', 'is_system', 'user_id', 'created_at'.
# - id: primary key, immutable
# - is_system: set at creation, immutable
# - user_id: owner, set at creation, immutable
# - created_at: server-managed timestamp
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "markdown_content",
        "display_order",
    }
)


class ResumeTemplateRepository:
    """Stateless repository for ResumeTemplate table operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.

    Access control boundary: All read operations filter to system
    templates OR the requesting user's own templates:
        WHERE is_system = true OR user_id = :current_user_id
    """

    @staticmethod
    async def list_available(
        db: AsyncSession, user_id: uuid.UUID
    ) -> list[ResumeTemplate]:
        """List templates visible to a user.

        Returns system templates (is_system=True) plus the user's own
        templates (user_id=:user_id), ordered by display_order ascending.

        Args:
            db: Async database session.
            user_id: Current user's UUID for scoping.

        Returns:
            List of ResumeTemplate instances ordered by display_order.
        """
        stmt = (
            select(ResumeTemplate)
            .where(
                or_(
                    ResumeTemplate.is_system.is_(True),
                    ResumeTemplate.user_id == user_id,
                )
            )
            .order_by(ResumeTemplate.display_order, ResumeTemplate.name)
            .limit(_MAX_LIST_RESULTS)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ResumeTemplate | None:
        """Fetch a template by ID with access control.

        Returns the template only if it is a system template or owned
        by the requesting user.

        Args:
            db: Async database session.
            template_id: UUID primary key.
            user_id: Current user's UUID for access check.

        Returns:
            ResumeTemplate if found and accessible, None otherwise.
        """
        stmt = select(ResumeTemplate).where(
            ResumeTemplate.id == template_id,
            or_(
                ResumeTemplate.is_system.is_(True),
                ResumeTemplate.user_id == user_id,
            ),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        name: str,
        markdown_content: str,
        description: str | None = None,
        display_order: int = 0,
    ) -> ResumeTemplate:
        """Create a user-owned template.

        User templates always have is_system=False. System templates
        are seeded via migration, not through this method.

        Args:
            db: Async database session.
            user_id: Owner UUID.
            name: Template display name.
            markdown_content: Template markdown content.
            description: Optional description.
            display_order: Ordering in template picker.

        Returns:
            Created ResumeTemplate with database-generated fields.
        """
        template = ResumeTemplate(
            name=name,
            description=description,
            markdown_content=markdown_content,
            is_system=False,
            user_id=user_id,
            display_order=display_order,
        )
        db.add(template)
        await db.flush()
        await db.refresh(template)
        return template

    @staticmethod
    async def update(
        db: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        **kwargs: str | int | None,
    ) -> ResumeTemplate | None:
        """Update a user-owned template.

        System templates cannot be updated. Only fields in
        _UPDATABLE_FIELDS are accepted.

        Args:
            db: Async database session.
            template_id: UUID of the template to update.
            user_id: Current user's UUID for ownership check.
            **kwargs: Field names and values to update.

        Returns:
            Updated ResumeTemplate if found and owned by user,
            None if not found or not accessible.

        Raises:
            ValueError: If template is a system template or unknown
                field names are passed.
        """
        unknown = set(kwargs) - _UPDATABLE_FIELDS
        if unknown:
            msg = f"Unknown fields: {', '.join(sorted(unknown))}"
            raise ValueError(msg)

        # Fetch without access control first to distinguish
        # "not found" from "system template"
        template = await db.get(ResumeTemplate, template_id)
        if template is None:
            return None

        if template.is_system:
            raise SystemTemplateError("Cannot modify system templates.")

        if template.user_id != user_id:
            return None

        for field, value in kwargs.items():
            setattr(template, field, value)

        template.updated_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(template)
        return template

    @staticmethod
    async def delete(
        db: AsyncSession,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a user-owned template.

        System templates cannot be deleted.

        Args:
            db: Async database session.
            template_id: UUID of the template to delete.
            user_id: Current user's UUID for ownership check.

        Returns:
            True if deleted, False if not found or not accessible.

        Raises:
            ValueError: If template is a system template.
        """
        template = await db.get(ResumeTemplate, template_id)
        if template is None:
            return False

        if template.is_system:
            raise SystemTemplateError("Cannot delete system templates.")

        if template.user_id != user_id:
            return False

        await db.delete(template)
        await db.flush()
        return True
