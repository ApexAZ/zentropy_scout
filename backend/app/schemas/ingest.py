"""Job Posting Ingest request/response schemas.

REQ-006 §5.6: Chrome extension job posting ingest flow.

This module defines schemas for the two-step ingest workflow:
1. POST /ingest: Submit raw text, get preview with confirmation token
2. POST /ingest/confirm: Confirm preview to create JobPosting
"""

from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field, HttpUrl, field_validator

# =============================================================================
# TypedDicts for Extracted Data
# =============================================================================


class ExtractedSkill(TypedDict):
    """A skill extracted from job posting text."""

    skill_name: str
    importance_level: str  # "Required" or "Preferred"


class ExtractedJobData(TypedDict, total=False):
    """Structured data extracted from raw job posting text.

    All fields are optional (total=False) since extraction may not find them.
    """

    job_title: str | None
    company_name: str | None
    location: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    employment_type: str | None
    extracted_skills: list[ExtractedSkill]
    culture_text: str | None
    description_snippet: str


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
            Expected fields match ExtractedJobData: job_title, company_name,
            location, salary_min, salary_max, salary_currency, employment_type,
            extracted_skills, culture_text, description_snippet.
    """

    confirmation_token: str = Field(
        ...,
        description="Token from ingest preview",
    )
    # Note: TypedDict can't be used directly with Pydantic validation.
    # See ExtractedJobData TypedDict for expected field structure.
    modifications: dict[str, Any] | None = Field(
        default=None,
        description="Optional field overrides matching ExtractedJobData structure",
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
