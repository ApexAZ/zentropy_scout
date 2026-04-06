"""SearchProfileService — persona fingerprint, staleness detection, and mark_stale.

REQ-034 §4.3, §4.4: Computes a deterministic SHA-256 fingerprint of the six material
Persona fields (skills, target_roles, target_skills, stretch_appetite,
location_preferences, remote_preference). Staleness is determined by comparing
the stored fingerprint on the SearchProfile to the freshly-computed fingerprint
of the current Persona state. mark_stale writes is_stale=True when the caller
detects drift. generate_profile calls the LLM once to derive fit/stretch search
criteria from the persona and upserts the result.

Coordinates with:
  - adapters/sources/base.py: SearchParams (build_search_params return type)
  - repositories/search_profile_repository.py: get_by_persona_id, upsert
  - models/persona.py: Persona fields used in fingerprint and prompt
  - models/search_profile.py: SearchProfile.persona_fingerprint, is_stale
  - schemas/search_profile.py: SearchBucketSchema, SearchProfileCreate
  - providers/llm/base.py: LLMMessage, LLMProvider, TaskType
  - core/llm_sanitization.py: sanitize_llm_input

Called by:
  - api/v1/personas.py: PATCH /personas/{id} staleness hook (§2.6)
  - api/v1/search_profiles.py: POST /search-profiles/{id}/generate (§2.7)
  - services/discovery/job_fetch_service.py: build_search_params for bucket-based SearchParams
"""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sources.base import _MAX_REMOTEOK_TAGS, _TAG_RE, SearchParams
from app.core.errors import APIError
from app.core.llm_sanitization import sanitize_llm_input
from app.models.persona import Persona
from app.models.search_profile import SearchProfile
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import SearchBucketSchema, SearchProfileCreate

logger = logging.getLogger(__name__)


# =============================================================================
# Errors
# =============================================================================


class SearchProfileGenerationError(APIError):
    """Raised when LLM search profile generation fails (502).

    REQ-034 §4.3: Propagated to the caller when the LLM call errors,
    returns empty content, or returns unparseable JSON.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            code="SEARCH_PROFILE_GENERATION_ERROR",
            message=message,
            status_code=502,
        )


# =============================================================================
# Prompt helpers (private)
# =============================================================================

_NOT_SPECIFIED = "Not specified"
"""Fallback text for optional persona string fields when absent."""

_MAX_LLM_RESPONSE_BYTES = 50_000
"""Size ceiling for raw LLM JSON response (50 KB). Guards json.loads against unexpectedly large payloads."""

_MAX_SKILL_NAME_LEN = 100
"""Per-element cap for skill names before sanitization (matches _MAX_KEYWORD_LEN in SearchBucketSchema)."""

_MAX_ROLE_LEN = 200
"""Per-element cap for target_roles and target_skills items before sanitization.

Mirrors SearchBucketSchema._MAX_TITLE_LEN (200). Prevents oversized list items
from inflating the LLM prompt beyond token limits or enabling prompt stuffing.
"""

_SYSTEM_PROMPT = """\
You are a job search strategist. Given a professional's persona, generate structured \
job search criteria split into fit roles (roles the user can perform now, based on \
their current experience and skills) and stretch roles (growth-target roles derived \
from their target_roles and target_skills, scaled by stretch_appetite).

Return only a JSON object with this exact structure — no markdown fences, no commentary:
{
  "fit_searches": [
    {
      "label": "Human-readable bucket name",
      "keywords": ["keyword1", "keyword2"],
      "titles": ["Exact Job Title 1"],
      "remoteok_tags": ["tag1"],
      "location": null
    }
  ],
  "stretch_searches": [...]
}

Rules:
- Generate 2-4 fit buckets and 1-3 stretch buckets.
- remoteok_tags must be valid RemoteOK tags (e.g. python, javascript, react, devops, \
backend, frontend, fullstack, golang, senior, manager, product, saas). Leave the list \
empty when no good tag mapping exists.
- Set location to null unless a specific override makes sense.
- stretch_appetite guidance: Low → 1 level above current; Medium → 1-2 levels; \
High → 2+ levels or adjacent role families.\
"""


def _build_generate_prompt(persona: Persona) -> str:
    """Build the user prompt for search profile generation from persona fields.

    Sanitizes all user-supplied string values before inclusion.

    Args:
        persona: Persona ORM instance with skills relationship loaded.

    Returns:
        User prompt string for the LLM.
    """
    # Sanitize per-element before joining — defends against injection via individual list items.
    skill_names = sorted(s.skill_name for s in persona.skills)
    skills_str = (
        ", ".join(sanitize_llm_input(n[:_MAX_SKILL_NAME_LEN]) for n in skill_names)
        or "None listed"
    )
    target_roles_str = (
        ", ".join(sanitize_llm_input(r[:_MAX_ROLE_LEN]) for r in persona.target_roles)
        or _NOT_SPECIFIED
    )
    target_skills_str = (
        ", ".join(sanitize_llm_input(s[:_MAX_ROLE_LEN]) for s in persona.target_skills)
        or _NOT_SPECIFIED
    )
    current_role_str = sanitize_llm_input(persona.current_role or _NOT_SPECIFIED)
    home_city_str = sanitize_llm_input(persona.home_city or _NOT_SPECIFIED)
    stretch_appetite_str = sanitize_llm_input(
        persona.stretch_appetite or _NOT_SPECIFIED
    )
    remote_preference_str = sanitize_llm_input(
        persona.remote_preference or _NOT_SPECIFIED
    )

    return (
        f"Generate job search criteria for this professional:\n\n"
        f"Current Role: {current_role_str}\n"
        f"Skills: {skills_str}\n"
        f"Target Roles: {target_roles_str}\n"
        f"Target Skills: {target_skills_str}\n"
        f"Stretch Appetite: {stretch_appetite_str}\n"
        f"Location: {home_city_str}\n"
        f"Remote Preference: {remote_preference_str}\n\n"
        f"Return JSON only."
    )


def compute_fingerprint(persona: Persona) -> str:
    """Compute a deterministic SHA-256 fingerprint for the six material Persona fields.

    REQ-034 §4.4: The fingerprint captures the fields that, when changed, signal the
    persona's job-search intent has shifted enough to require AI re-generation of the
    SearchProfile. Non-material fields (bio, summary, display_name, etc.) are excluded.

    Callers must ensure that `persona.skills` is loaded (not deferred/expired) before
    calling this function, since it accesses the relationship in-process.

    Args:
        persona: Persona ORM instance with `skills` relationship loaded.

    Returns:
        64-character lowercase hex SHA-256 digest string.
    """
    snapshot = {
        "skills": sorted(s.skill_name for s in persona.skills),
        "target_roles": sorted(persona.target_roles),
        "target_skills": sorted(persona.target_skills),
        "stretch_appetite": persona.stretch_appetite,
        "location_preferences": {
            "home_city": persona.home_city,
            "commutable_cities": sorted(persona.commutable_cities),
            "relocation_cities": sorted(persona.relocation_cities),
        },
        "remote_preference": persona.remote_preference,
    }
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=True)
    # SHA-256 as a deterministic change-detection fingerprint — not a security primitive
    return hashlib.sha256(canonical.encode()).hexdigest()


def check_staleness(persona: Persona, profile: SearchProfile) -> bool:
    """Return True if the persona's current fingerprint differs from the stored one.

    REQ-034 §4.4: A True result means the persona's material fields have changed
    since the SearchProfile was generated and the profile should be regenerated.

    Args:
        persona: Current Persona ORM instance with `skills` relationship loaded.
        profile: Existing SearchProfile to compare against.

    Returns:
        True if stale (fingerprints differ), False if fresh (fingerprints match).
    """
    return compute_fingerprint(persona) != profile.persona_fingerprint


async def mark_stale(db: AsyncSession, persona_id: uuid.UUID) -> None:
    """Set is_stale=True on the SearchProfile for the given persona.

    REQ-034 §4.4: Called when PATCH /personas/{id} detects a fingerprint change.
    No-ops silently if the persona has no SearchProfile yet (profile will be
    generated with is_stale=False once the AI produces it).

    Args:
        db: Async database session.
        persona_id: UUID of the persona whose profile should be marked stale.
    """
    profile = await SearchProfileRepository.get_by_persona_id(db, persona_id)
    if profile is None:
        return
    profile.is_stale = True
    await db.flush()


async def generate_profile(
    db: AsyncSession,
    persona: Persona,
    provider: LLMProvider | None,
) -> SearchProfile:
    """Generate fit/stretch search buckets via LLM and upsert as SearchProfile.

    REQ-034 §4.3: Calls the LLM once to derive structured job search criteria
    from the persona. The result is stored and reused by the polling loop
    without further LLM involvement. When provider is None (test/stub mode),
    upserts an empty profile without calling the LLM.

    Callers must ensure that `persona.skills` is loaded before calling this
    function, since it accesses the relationship in-process.

    Args:
        db: Async database session.
        persona: Persona ORM instance with `skills` relationship loaded.
        provider: LLM provider to call. Pass None to create an empty stub profile.

    Returns:
        Created or updated SearchProfile with fit/stretch buckets populated.

    Raises:
        SearchProfileGenerationError: If the LLM call fails, returns empty
            content, or returns unparseable JSON.
    """
    fingerprint = compute_fingerprint(persona)

    if provider is None:
        # Stub mode: persist an empty profile without calling the LLM.
        return await SearchProfileRepository.upsert(
            db,
            persona.id,
            SearchProfileCreate(
                persona_id=persona.id,
                fit_searches=[],
                stretch_searches=[],
                persona_fingerprint=fingerprint,
                is_stale=False,
                generated_at=datetime.now(UTC),
            ),
        )

    messages = [
        LLMMessage(role="system", content=_SYSTEM_PROMPT),
        LLMMessage(  # nosemgrep: zentropy.llm-unsanitized-input  # sanitized inside _build_generate_prompt()
            role="user", content=_build_generate_prompt(persona)
        ),
    ]

    try:
        response = await provider.complete(
            messages=messages,
            task=TaskType.SEARCH_PROFILE_GENERATION,
            json_mode=True,
        )
    except ProviderError as exc:
        logger.error(
            "Search profile generation failed for persona %s: %s", persona.id, exc
        )
        raise SearchProfileGenerationError("Failed to generate search profile") from exc

    if not response.content:
        raise SearchProfileGenerationError(
            "LLM returned empty response for search profile generation"
        )

    if len(response.content) > _MAX_LLM_RESPONSE_BYTES:
        raise SearchProfileGenerationError(
            "LLM returned oversized response for search profile generation"
        )

    try:
        data = json.loads(response.content)
        fit_searches = [
            SearchBucketSchema.model_validate(b) for b in data.get("fit_searches", [])
        ]
        stretch_searches = [
            SearchBucketSchema.model_validate(b)
            for b in data.get("stretch_searches", [])
        ]
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error(
            "Unparseable LLM JSON for search profile generation (persona %s): %s",
            persona.id,
            exc,
            exc_info=True,
        )
        raise SearchProfileGenerationError(
            "LLM returned unparseable JSON for search profile generation"
        ) from exc

    return await SearchProfileRepository.upsert(
        db,
        persona.id,
        SearchProfileCreate(
            persona_id=persona.id,
            fit_searches=fit_searches,
            stretch_searches=stretch_searches,
            persona_fingerprint=fingerprint,
            is_stale=False,
            generated_at=datetime.now(UTC),
        ),
    )


# =============================================================================
# SearchParams construction
# =============================================================================

_FIRST_POLL_DAYS: int = 7
"""Seed window (days) for a persona's first poll (no prior last_poll_at)."""

_MAX_POLL_DAYS: int = 90
"""Hard ceiling on max_days_old — matches SearchParams validation constraint."""


def build_search_params(
    bucket: SearchBucketSchema,
    persona: Persona,
    last_poll_at: datetime | None,
    *,
    results_per_page: int = 50,
) -> SearchParams:
    """Build SearchParams from a SearchBucket, Persona, and prior poll timestamp.

    REQ-034 §5.2: Constructs the SearchParams that drive a single adapter poll
    for one search bucket.

    Delta calculation (REQ-034 §5.2):
        days = max(1, ceil((now - last_poll_at).total_seconds() / 86400) + 1)
        The +1 adds a one-day buffer to avoid missing jobs at the boundary.
        Capped at 90 days to satisfy SearchParams.max_days_old validation.
        First poll (last_poll_at is None) → max_days_old = 7 (seed window).

    Args:
        bucket: SearchBucket with keywords, titles, remoteok_tags, and optional
            location override.
        persona: Persona ORM instance — provides remote_preference and home_city
            fallback for location.
        last_poll_at: UTC timestamp of the last successful poll; None on first poll.
        results_per_page: Number of results to request per source page (default 50).

    Returns:
        SearchParams ready for dispatch to source adapters.
    """
    now = datetime.now(UTC)

    # Delta calculation per REQ-034 §5.2
    if last_poll_at is None:
        max_days_old = _FIRST_POLL_DAYS
    else:
        days = max(1, ceil((now - last_poll_at).total_seconds() / 86400) + 1)
        max_days_old = min(days, _MAX_POLL_DAYS)

    posted_after = now - timedelta(days=max_days_old)

    # keywords = bucket.keywords + bucket.titles (per REQ-034 §5.2)
    keywords = list(bucket.keywords) + list(bucket.titles)

    # location: bucket override (validated by schema), fallback to persona.home_city.
    # Clamp persona.home_city to 120 chars to mirror SearchBucketSchema._MAX_LOCATION
    # and prevent unbounded strings from reaching adapter query builders.
    raw_location = bucket.location if bucket.location is not None else persona.home_city
    location = raw_location[:120] if raw_location else None

    # remote_only: True only for "Remote Only" persona preference
    remote_only = persona.remote_preference == "Remote Only"

    # Filter bucket tags to those matching SearchParams validation pattern (_TAG_RE),
    # then cap at the SearchParams maximum (_MAX_REMOTEOK_TAGS).
    # WHY import: using the same constants as SearchParams avoids silent divergence
    # if the pattern or cap ever changes in adapters/sources/base.py.
    valid_tags = [t for t in bucket.remoteok_tags if _TAG_RE.match(t)]
    remoteok_tags = valid_tags[:_MAX_REMOTEOK_TAGS] if valid_tags else None

    return SearchParams(
        keywords=keywords,
        location=location,
        remote_only=remote_only,
        results_per_page=results_per_page,
        max_days_old=max_days_old,
        posted_after=posted_after,
        remoteok_tags=remoteok_tags,
    )
