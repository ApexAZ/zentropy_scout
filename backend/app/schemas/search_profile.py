"""Pydantic schemas for SearchProfile API endpoints.

REQ-034 §4.2, §4.5: Request/response models for the search_profiles resource.
SearchBucketSchema validates the JSONB bucket shape stored in fit_searches and
stretch_searches. SearchProfileRead covers GET/POST responses; SearchProfileCreate
and SearchProfileUpdate cover internal creation and PATCH requests.

Coordinates with:
  - (no internal app imports — standalone Pydantic schemas)

Called by / Used by:
  - api/v1/search_profiles.py: endpoint response/request models
  - services/discovery/search_profile_service.py: parsing LLM output into SearchBucket objects
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Size limits (defense-in-depth against oversized JSONB payloads and LLM output)
# ---------------------------------------------------------------------------

_MAX_LABEL = 120
_MAX_KEYWORD_LEN = 100
_MAX_TITLE_LEN = 200
_MAX_TAG_LEN = 60
_MAX_LIST_ITEMS = 30
_MAX_LOCATION = 120
_MAX_FINGERPRINT = 64
_MAX_BUCKETS = 15


class SearchBucketSchema(BaseModel):
    """A single search criterion bucket — fit or stretch.

    REQ-034 §4.2: JSONB shape for each item in fit_searches / stretch_searches.
    All four keyword/title fields are required on every bucket; location is
    optional and falls back to persona.home_city when None.

    Attributes:
        label: Human-readable name for this bucket (e.g., "Senior Product Manager").
        keywords: Keyword strings for keyword-based search APIs (Adzuna, The Muse).
        titles: Exact job title strings for title-matching adapters.
        remoteok_tags: Tag slugs for RemoteOK's tag-based search endpoint.
        location: Override location string. None → adapter falls back to persona.home_city.
    """

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=_MAX_LABEL)
    keywords: list[Annotated[str, Field(max_length=_MAX_KEYWORD_LEN)]] = Field(
        max_length=_MAX_LIST_ITEMS
    )
    titles: list[Annotated[str, Field(max_length=_MAX_TITLE_LEN)]] = Field(
        max_length=_MAX_LIST_ITEMS
    )
    remoteok_tags: list[Annotated[str, Field(max_length=_MAX_TAG_LEN)]] = Field(
        max_length=_MAX_LIST_ITEMS
    )
    location: str | None = Field(default=None, max_length=_MAX_LOCATION)


class SearchProfileRead(BaseModel):
    """Full SearchProfile response — all fields.

    REQ-034 §4.5: Returned by GET /search-profiles/{persona_id} and
    POST /search-profiles/{persona_id}/generate.

    Attributes:
        id: UUID primary key.
        persona_id: Owning persona UUID.
        fit_searches: Current-fit role search buckets.
        stretch_searches: Growth-target role search buckets.
        persona_fingerprint: SHA-256 of material persona fields at generation time.
        is_stale: True when persona has changed since last generation.
        generated_at: When AI generated this profile (None until first generation).
        approved_at: When user approved this profile (None until approved).
        created_at: Record creation timestamp.
        updated_at: Record last-modified timestamp.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    persona_id: uuid.UUID
    fit_searches: list[SearchBucketSchema]
    stretch_searches: list[SearchBucketSchema]
    persona_fingerprint: str
    is_stale: bool
    generated_at: datetime | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SearchProfileCreate(BaseModel):
    """Request model for creating a SearchProfile record.

    REQ-034 §4.5: Used internally by SearchProfileService.upsert() and
    SearchProfileRepository.create(). All fields except persona_id have
    sensible defaults — a placeholder row can be inserted with just persona_id.

    Attributes:
        persona_id: UUID of the owning persona.
        fit_searches: Initial fit-role search buckets (default empty).
        stretch_searches: Initial stretch-role search buckets (default empty).
        persona_fingerprint: SHA-256 snapshot at creation time (default empty string).
        is_stale: Whether the profile should start as stale (default True).
        generated_at: When AI generation occurred (None if not yet generated).
        approved_at: When the user approved (None if not yet approved).
    """

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    fit_searches: list[SearchBucketSchema] = Field(
        default_factory=list, max_length=_MAX_BUCKETS
    )
    stretch_searches: list[SearchBucketSchema] = Field(
        default_factory=list, max_length=_MAX_BUCKETS
    )
    persona_fingerprint: str = Field(default="", max_length=_MAX_FINGERPRINT)
    is_stale: bool = True
    generated_at: datetime | None = None
    approved_at: datetime | None = None


class SearchProfileUpdate(BaseModel):
    """Partial update model for PATCH /search-profiles/{persona_id}.

    REQ-034 §4.5: All fields are optional — only provided fields are updated.
    Used for user-driven bucket edits and setting approved_at on approval.

    Attributes:
        fit_searches: Replacement fit-role search buckets (None = no change).
        stretch_searches: Replacement stretch-role search buckets (None = no change).
        persona_fingerprint: Updated SHA-256 fingerprint (None = no change).
        is_stale: Updated staleness flag (None = no change).
        generated_at: Updated generation timestamp (None = no change).
        approved_at: Updated approval timestamp — set to approve the profile (None = no change).
    """

    model_config = ConfigDict(extra="forbid")

    fit_searches: list[SearchBucketSchema] | None = Field(
        default=None, max_length=_MAX_BUCKETS
    )
    stretch_searches: list[SearchBucketSchema] | None = Field(
        default=None, max_length=_MAX_BUCKETS
    )
    persona_fingerprint: str | None = Field(default=None, max_length=_MAX_FINGERPRINT)
    is_stale: bool | None = None
    generated_at: datetime | None = None
    approved_at: datetime | None = None
