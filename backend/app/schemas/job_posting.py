"""Job posting schemas for the shared pool.

REQ-015 §8.3: Response models enforce privacy boundaries.
- JobPostingResponse: factual data only, excludes also_found_on
- PersonaJobResponse: nested shared data + per-user fields
REQ-015 §9: Request models for API endpoint updates.
- UpdatePersonaJobRequest: per-user fields only (shared data immutable)
- CreateJobPostingRequest: manual job creation with dedup
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobPostingResponse(BaseModel):
    """Public job data — shared pool fields only.

    REQ-015 §8.3: Excludes also_found_on (internal dedup tracking)
    and raw_text (internal storage only). Never includes cross-user
    aggregations (user_count, etc.).

    Attributes:
        id: Job posting UUID.
        job_title: Job title.
        company_name: Company name.
        is_active: Whether the job is still active.
        description: Job description text.
        description_hash: SHA-256 hash for dedup.
        first_seen_date: Date the job was first discovered.
        ghost_score: Ghost job likelihood score (0-100).
        repost_count: Number of times this job has been reposted.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID | None = None
    external_id: str | None = None
    job_title: str
    company_name: str
    company_url: str | None = None
    source_url: str | None = None
    apply_url: str | None = None
    location: str | None = None
    work_model: str | None = None
    seniority_level: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str
    culture_text: str | None = None
    requirements: str | None = None
    years_experience_min: int | None = None
    years_experience_max: int | None = None
    posted_date: date | None = None
    application_deadline: date | None = None
    first_seen_date: date
    last_verified_at: datetime | None = None
    expired_at: datetime | None = None
    ghost_signals: dict | None = None
    ghost_score: int
    description_hash: str
    repost_count: int
    previous_posting_ids: list | None = None
    is_active: bool


class PersonaJobResponse(BaseModel):
    """Per-user job relationship with nested shared data.

    REQ-015 §8.3: Always returns the per-user wrapper containing
    the shared job data. API never returns raw JobPostingResponse
    directly to users.

    Attributes:
        id: PersonaJob UUID.
        job: Nested shared job data (reads from ORM ``job_posting`` relationship).
        status: User's relationship status (Discovered/Dismissed/Applied).
        is_favorite: Whether the user favorited this job.
        discovery_method: How the job was discovered (scouter/manual/pool).
        discovered_at: When the user first saw this job.
    """

    model_config = ConfigDict(
        extra="forbid", from_attributes=True, populate_by_name=True
    )

    id: uuid.UUID
    job: JobPostingResponse = Field(validation_alias="job_posting")
    status: str
    is_favorite: bool
    discovery_method: str
    discovered_at: datetime
    fit_score: int | None = None
    stretch_score: int | None = None
    failed_non_negotiables: list | None = None
    score_details: dict | None = None
    scored_at: datetime | None = None
    dismissed_at: datetime | None = None


class UpdatePersonaJobRequest(BaseModel):
    """Request body for PATCH /job-postings/{id}.

    REQ-015 §9.1: Only per-user persona_jobs fields can be updated.
    Shared job posting data is immutable from user API.

    Attributes:
        status: New status (Discovered/Dismissed/Applied).
        is_favorite: Toggle favorite flag.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["Discovered", "Dismissed", "Applied"] | None = None
    is_favorite: bool | None = None


class CreateJobPostingRequest(BaseModel):
    """Request body for POST /job-postings.

    REQ-015 §9.1: Creates in shared pool + creates persona_jobs link.
    Dedup check first — if job with same description_hash exists,
    just creates the persona_jobs link.

    Attributes:
        job_title: Job title (required).
        company_name: Company name (required).
        description: Full job description (required, used for dedup hash).
    """

    model_config = ConfigDict(extra="forbid")

    job_title: str = Field(..., min_length=1, max_length=500)
    company_name: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1, max_length=50000)
    source_url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    work_model: str | None = Field(default=None, max_length=50)
    seniority_level: str | None = Field(default=None, max_length=50)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=10)
    culture_text: str | None = Field(default=None, max_length=50000)
    requirements: str | None = Field(default=None, max_length=50000)
