"""Resume generation request/response schemas.

REQ-026 §4.6: Generation API — request and response models for
POST /base-resumes/{id}/generate.

Coordinates with:
  - (no internal app imports — standalone Pydantic schemas)

Called by: api/v1/base_resumes.py.
"""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

GenerationMethod = Literal["ai", "template_fill"]
"""Valid resume generation methods."""

_MAX_SECTIONS_COUNT = 10
"""Defense-in-depth: max number of section identifiers (matches prompt builder)."""

_MAX_SECTION_NAME_LENGTH = 50
"""Defense-in-depth: max length per section name (matches prompt builder)."""


class GenerateResumeRequest(BaseModel):
    """Request body for resume generation.

    REQ-026 §4.6, §3.4: Supports both AI and template_fill methods.

    Attributes:
        method: Generation method — "ai" (LLM) or "template_fill" (deterministic).
        page_limit: Target page count for AI generation (1-3). Defaults to 1.
        emphasis: Emphasis preference for AI generation. Defaults to "balanced".
        include_sections: Section identifiers to include (AI only).
        template_id: Template to use. Falls back to resume's template_id if not set.
    """

    model_config = ConfigDict(extra="forbid")

    method: GenerationMethod
    page_limit: int = Field(default=1, ge=1, le=3)
    emphasis: str = Field(default="balanced", max_length=50)
    include_sections: (
        list[Annotated[str, Field(max_length=_MAX_SECTION_NAME_LENGTH)]] | None
    ) = Field(default=None, max_length=_MAX_SECTIONS_COUNT)
    template_id: uuid.UUID | None = None


class GenerateResumeResponse(BaseModel):
    """Response body for resume generation.

    REQ-026 §4.6: Contains generated markdown and metadata.

    Attributes:
        markdown_content: The generated resume markdown.
        word_count: Word count of the generated content.
        method: Which generation method was used.
        model_used: LLM model name (None for template_fill).
        generation_cost_cents: Cost in cents (0 for template_fill).
    """

    model_config = ConfigDict(extra="forbid")

    markdown_content: str
    word_count: int
    method: GenerationMethod
    model_used: str | None = None
    generation_cost_cents: int = 0
