"""Job posting response schemas for the shared pool.

REQ-015 §8.3: Response models enforce privacy boundaries.
- JobPostingResponse: factual data only, excludes also_found_on
- PersonaJobResponse: nested shared data + per-user fields
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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
        job: Nested shared job data.
        status: User's relationship status (Discovered/Dismissed/Applied).
        is_favorite: Whether the user favorited this job.
        discovery_method: How the job was discovered (scouter/manual/pool).
        discovered_at: When the user first saw this job.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    job: JobPostingResponse
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
