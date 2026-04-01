"""Resume template API endpoints.

REQ-025 §6.4: CRUD endpoints for resume templates.

Coordinates with:
  - api/deps.py (CurrentUserId, DbSession)
  - core/responses.py (DataResponse, ListResponse, PaginationMeta)
  - models/resume_template.py (ResumeTemplate)
  - schemas/resume_template.py (CreateResumeTemplateRequest,
    ResumeTemplateResponse, UpdateResumeTemplateRequest)
  - services/rendering/resume_template_service.py (list_templates,
    get_template, create_template, update_template, delete_template)

Called by: api/v1/router.py.
"""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUserId, DbSession
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models.resume_template import ResumeTemplate
from app.schemas.resume_template import (
    CreateResumeTemplateRequest,
    ResumeTemplateResponse,
    UpdateResumeTemplateRequest,
)
from app.services.rendering import resume_template_service

router = APIRouter()


def _template_to_response(template: ResumeTemplate) -> dict:
    """Convert ORM template to response dict.

    Args:
        template: ResumeTemplate ORM instance.

    Returns:
        JSON-serializable dict matching ResumeTemplateResponse.
    """
    return ResumeTemplateResponse.model_validate(template).model_dump(mode="json")


@router.get("")
async def list_resume_templates(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List available resume templates.

    REQ-025 §6.4: Returns system templates + user's own templates,
    ordered by display_order.
    """
    templates = await resume_template_service.list_templates(db, user_id)
    items = [_template_to_response(t) for t in templates]
    return ListResponse(
        data=items,
        meta=PaginationMeta(total=len(items), page=1, per_page=len(items) or 20),
    )


@router.get("/{template_id}")
async def get_resume_template(
    template_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a resume template by ID.

    REQ-025 §6.4: Access control — system templates or user's own.

    Raises:
        NotFoundError: If template not found or not accessible.
    """
    template = await resume_template_service.get_template(db, template_id, user_id)
    return DataResponse(data=_template_to_response(template))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_resume_template(
    request: CreateResumeTemplateRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a user resume template.

    REQ-025 §6.4, §8: Upload markdown as a custom template.
    Validates that markdown contains at least one heading.

    Raises:
        ValidationError: If markdown is invalid.
    """
    template = await resume_template_service.create_template(
        db,
        user_id,
        name=request.name,
        markdown_content=request.markdown_content,
        description=request.description,
        display_order=request.display_order,
    )
    return DataResponse(data=_template_to_response(template))


@router.patch("/{template_id}")
async def update_resume_template(
    template_id: uuid.UUID,
    request: UpdateResumeTemplateRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a user resume template.

    REQ-025 §6.4: System templates cannot be modified.

    Raises:
        NotFoundError: If template not found or not accessible.
        InvalidStateError: If template is a system template.
        ValidationError: If markdown is invalid.
    """
    update_data = request.model_dump(exclude_unset=True)
    template = await resume_template_service.update_template(
        db, template_id, user_id, **update_data
    )
    return DataResponse(data=_template_to_response(template))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume_template(
    template_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Delete a user resume template.

    REQ-025 §6.4: System templates cannot be deleted.

    Raises:
        NotFoundError: If template not found or not accessible.
        InvalidStateError: If template is a system template.
    """
    await resume_template_service.delete_template(db, template_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
