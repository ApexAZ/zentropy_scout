"""Job Posting Ingest request/response schemas.

REQ-006 §5.6: Chrome extension job posting ingest flow.

This module defines schemas for the two-step ingest workflow:
1. POST /ingest: Submit raw text, get preview with confirmation token
2. POST /ingest/confirm: Confirm preview to create JobPosting
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator

# =============================================================================
# Request Schemas
# =============================================================================


class IngestJobPostingRequest(BaseModel):
    """Request body for POST /job-postings/ingest.

    REQ-006 §5.6: Chrome extension submits raw job text for parsing.

    Attributes:
        raw_text: Full job posting text captured from page.
        source_url: URL where the job was found.
        source_name: Name of the source (e.g., "LinkedIn", "Indeed").
    """

    raw_text: str = Field(
        ...,
        min_length=1,
        description="Full job posting text",
    )
    source_url: HttpUrl = Field(
        ...,
        description="URL where job was found",
    )
    source_name: str = Field(
        ...,
        min_length=1,
        description="Source name (e.g., LinkedIn)",
    )

    @field_validator("raw_text", mode="before")
    @classmethod
    def strip_raw_text(cls, v: str) -> str:
        """Strip whitespace from raw_text."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("raw_text")
    @classmethod
    def raw_text_not_empty(cls, v: str) -> str:
        """Validate raw_text is not empty after stripping."""
        if not v:
            msg = "raw_text cannot be empty"
            raise ValueError(msg)
        return v


class IngestConfirmRequest(BaseModel):
    """Request body for POST /job-postings/ingest/confirm.

    REQ-006 §5.6: Confirm preview to create actual JobPosting.

    Attributes:
        confirmation_token: Token from ingest preview response.
        modifications: Optional field overrides from user review.
    """

    confirmation_token: str = Field(
        ...,
        description="Token from ingest preview",
    )
    modifications: dict[str, Any] | None = Field(
        default=None,
        description="Optional field overrides",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class ExtractedSkillPreview(BaseModel):
    """Preview of an extracted skill.

    Attributes:
        skill_name: Name of the skill.
        importance_level: "Required" or "Preferred".
    """

    skill_name: str
    importance_level: str = "Preferred"


class IngestPreview(BaseModel):
    """Preview of extracted job posting data.

    REQ-006 §5.6: Shows user what was extracted before saving.

    Attributes:
        job_title: Extracted job title.
        company_name: Extracted company name.
        location: Extracted location.
        salary_min: Minimum salary if found.
        salary_max: Maximum salary if found.
        salary_currency: Currency code (e.g., "USD").
        employment_type: Full-time, Part-time, Contract, etc.
        extracted_skills: List of extracted skills.
        culture_text: Extracted culture/soft skill signals.
        description_snippet: First 500 chars of description.
    """

    job_title: str | None = None
    company_name: str | None = None
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    employment_type: str | None = None
    extracted_skills: list[ExtractedSkillPreview] = Field(default_factory=list)
    culture_text: str | None = None
    description_snippet: str | None = None


class IngestJobPostingResponse(BaseModel):
    """Response for POST /job-postings/ingest.

    REQ-006 §5.6: Preview with confirmation token.

    Attributes:
        preview: Extracted job data for user review.
        confirmation_token: Token to confirm and create the job.
        expires_at: When the token expires (ISO format).
    """

    preview: IngestPreview
    confirmation_token: str
    expires_at: datetime
