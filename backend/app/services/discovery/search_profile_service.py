"""SearchProfileService — persona fingerprint, staleness detection, and mark_stale.

REQ-034 §4.4: Computes a deterministic SHA-256 fingerprint of the six material
Persona fields (skills, target_roles, target_skills, stretch_appetite,
location_preferences, remote_preference). Staleness is determined by comparing
the stored fingerprint on the SearchProfile to the freshly-computed fingerprint
of the current Persona state. mark_stale writes is_stale=True when the caller
detects drift.

Coordinates with:
  - repositories/search_profile_repository.py: get_by_persona_id (mark_stale)
  - models/persona.py: Persona fields used in fingerprint
  - models/search_profile.py: SearchProfile.persona_fingerprint, is_stale

Called by:
  - api/v1/personas.py: PATCH /personas/{id} staleness hook (§2.6)
  - api/v1/search_profiles.py: POST /search-profiles/{id}/generate (§2.7)
"""

import hashlib
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.search_profile import SearchProfile
from app.repositories.search_profile_repository import SearchProfileRepository


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
