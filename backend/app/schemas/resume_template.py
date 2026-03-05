"""Resume template Pydantic schemas.

REQ-025 §4.3, §6.4: Request/response models for resume template API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResumeTemplateResponse(BaseModel):
    """Response model for a resume template.

    Attributes:
        id: Template UUID.
        name: Display name.
        description: Brief description for template picker.
        markdown_content: Template skeleton with placeholder sections.
        is_system: True for built-in templates.
        user_id: Owner UUID (None for system templates).
        display_order: Ordering in template picker.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = Field(default=None)
    markdown_content: str
    is_system: bool
    user_id: uuid.UUID | None = Field(default=None)
    display_order: int
    created_at: datetime
    updated_at: datetime


class CreateResumeTemplateRequest(BaseModel):
    """Request body for creating a user template.

    Attributes:
        name: Template display name (1-100 chars).
        markdown_content: Template markdown content.
        description: Optional description for template picker.
        display_order: Ordering in template picker (default 0).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    markdown_content: str = Field(..., min_length=1, max_length=100000)
    description: str | None = Field(default=None, max_length=500)
    display_order: int = Field(default=0, ge=0, le=10000)


class UpdateResumeTemplateRequest(BaseModel):
    """Request body for partially updating a user template.

    All fields optional — only provided fields are updated.

    Attributes:
        name: New display name.
        markdown_content: New markdown content.
        description: New description.
        display_order: New ordering value.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    markdown_content: str | None = Field(default=None, min_length=1, max_length=100000)
    description: str | None = Field(default=None, max_length=500)
    display_order: int | None = Field(default=None, ge=0, le=10000)


class ResumeTemplateListResponse(BaseModel):
    """Response wrapper for a list of templates.

    Attributes:
        templates: List of template response objects.
    """

    model_config = ConfigDict(extra="forbid")

    templates: list[ResumeTemplateResponse]
