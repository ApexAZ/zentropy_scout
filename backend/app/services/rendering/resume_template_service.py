"""Resume template service.

REQ-025 §6.2–§6.4, §8: Business logic for resume template CRUD
with markdown validation.

Called by: Unit tests. Intended for resume template API (pending router wiring).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError, ValidationError
from app.models.resume_template import ResumeTemplate
from app.repositories.resume_template_repository import (
    ResumeTemplateRepository,
    SystemTemplateError,
)


def validate_template_markdown(markdown_content: str) -> None:
    """Validate that markdown content is suitable for a resume template.

    REQ-025 §8: Template markdown must parse without errors and
    contain at least one heading.

    Args:
        markdown_content: Markdown string to validate.

    Raises:
        ValidationError: If markdown is invalid or missing headings.
    """
    if not markdown_content or not markdown_content.strip():
        raise ValidationError("Template markdown content cannot be empty.")

    # Check for at least one ATX heading (lines starting with #)
    has_heading = any(
        line.lstrip().startswith("#") for line in markdown_content.splitlines()
    )
    if not has_heading:
        raise ValidationError(
            "Template markdown must contain at least one heading (e.g., '# Section')."
        )


async def list_templates(db: AsyncSession, user_id: uuid.UUID) -> list[ResumeTemplate]:
    """List templates available to a user.

    REQ-025 §6.4: Returns system templates + user's own templates.

    Args:
        db: Async database session.
        user_id: Current user's UUID for scoping.

    Returns:
        List of ResumeTemplate instances ordered by display_order.
    """
    return await ResumeTemplateRepository.list_available(db, user_id)


async def get_template(
    db: AsyncSession, template_id: uuid.UUID, user_id: uuid.UUID
) -> ResumeTemplate:
    """Get a template by ID with access control.

    REQ-025 §6.4: Returns template if accessible by user.

    Args:
        db: Async database session.
        template_id: UUID primary key.
        user_id: Current user's UUID for access check.

    Returns:
        ResumeTemplate if found and accessible.

    Raises:
        NotFoundError: If template not found or not accessible.
    """
    template = await ResumeTemplateRepository.get_by_id(db, template_id, user_id)
    if template is None:
        raise NotFoundError("ResumeTemplate", str(template_id))
    return template


async def create_template(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    name: str,
    markdown_content: str,
    description: str | None = None,
    display_order: int = 0,
) -> ResumeTemplate:
    """Create a user-owned template.

    REQ-025 §6.4, §8: Validates markdown before creating.

    Args:
        db: Async database session.
        user_id: Owner UUID.
        name: Template display name.
        markdown_content: Template markdown content.
        description: Optional description.
        display_order: Ordering in template picker.

    Returns:
        Created ResumeTemplate with database-generated fields.

    Raises:
        ValidationError: If markdown is invalid.
    """
    validate_template_markdown(markdown_content)
    return await ResumeTemplateRepository.create(
        db,
        user_id=user_id,
        name=name,
        markdown_content=markdown_content,
        description=description,
        display_order=display_order,
    )


async def update_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
    **kwargs: str | int | None,
) -> ResumeTemplate:
    """Update a user-owned template.

    REQ-025 §6.4, §8: Validates markdown if provided.

    Args:
        db: Async database session.
        template_id: UUID of the template to update.
        user_id: Current user's UUID for ownership check.
        **kwargs: Field names and values to update.

    Returns:
        Updated ResumeTemplate.

    Raises:
        NotFoundError: If template not found or not accessible.
        ValidationError: If markdown is invalid.
        InvalidStateError: If template is a system template.
    """
    if "markdown_content" in kwargs and kwargs["markdown_content"] is not None:
        validate_template_markdown(str(kwargs["markdown_content"]))

    try:
        template = await ResumeTemplateRepository.update(
            db, template_id, user_id, **kwargs
        )
    except SystemTemplateError as exc:
        raise InvalidStateError(str(exc)) from exc

    if template is None:
        raise NotFoundError("ResumeTemplate", str(template_id))
    return template


async def delete_template(
    db: AsyncSession,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a user-owned template.

    REQ-025 §6.4: System templates cannot be deleted.

    Args:
        db: Async database session.
        template_id: UUID of the template to delete.
        user_id: Current user's UUID for ownership check.

    Raises:
        NotFoundError: If template not found or not accessible.
        InvalidStateError: If template is a system template.
    """
    try:
        deleted = await ResumeTemplateRepository.delete(db, template_id, user_id)
    except SystemTemplateError as exc:
        raise InvalidStateError(str(exc)) from exc

    if not deleted:
        raise NotFoundError("ResumeTemplate", str(template_id))
