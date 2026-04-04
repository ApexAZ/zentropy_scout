"""Tests for SearchProfileService — fingerprint, staleness, and mark_stale.

REQ-034 §4.4: Verifies compute_fingerprint is deterministic and changes on
material field updates but not on non-material fields. Verifies check_staleness
and mark_stale against a live PostgreSQL session.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import SearchProfileCreate
from app.services.discovery.search_profile_service import (
    check_staleness,
    compute_fingerprint,
    mark_stale,
)

_STORED_FINGERPRINT = "a" * 64  # Valid 64-char fingerprint used in DB fixtures
_WRONG_FINGERPRINT = "stale" * 16  # 80-char string that never matches a real SHA-256

# ---------------------------------------------------------------------------
# Fake helpers — plain Python objects to avoid SQLAlchemy instrumentation
# ---------------------------------------------------------------------------


class _FakeSkill:
    """Minimal skill-like object — only skill_name is needed for fingerprint."""

    def __init__(self, name: str) -> None:
        self.skill_name = name


class _FakePersona:
    """Minimal persona-like object with all six fingerprint fields."""

    def __init__(self, **kwargs: object) -> None:
        defaults: dict[str, object] = {
            "skills": [_FakeSkill("Python"), _FakeSkill("FastAPI")],
            "target_roles": ["Backend Engineer", "Staff Engineer"],
            "target_skills": ["System Design", "Distributed Systems"],
            "stretch_appetite": "Medium",
            "home_city": "San Francisco, CA",
            "commutable_cities": ["Oakland, CA", "San Jose, CA"],
            "relocation_cities": ["Seattle, WA"],
            "remote_preference": "Remote Only",
            # Non-material fields
            "bio": "Experienced engineer.",
            "summary": "Summary text.",
            "display_name": "Test User",
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class _FakeProfile:
    """Minimal profile-like object — only persona_fingerprint is needed."""

    def __init__(self, fingerprint: str) -> None:
        self.persona_fingerprint = fingerprint


def _make_skill(name: str) -> _FakeSkill:
    """Build a fake skill object with the given skill_name."""
    return _FakeSkill(name)


def _make_persona(**overrides: object) -> _FakePersona:
    """Build a fake Persona-like object with fingerprint fields set."""
    return _FakePersona(**overrides)


def _make_profile(fingerprint: str) -> _FakeProfile:
    """Build a fake SearchProfile-like object with the given fingerprint."""
    return _FakeProfile(fingerprint)


# =============================================================================
# compute_fingerprint — determinism and material-field sensitivity
# =============================================================================


class TestComputeFingerprint:
    """Tests for compute_fingerprint(persona) -> str."""

    def test_returns_64_char_hex_string(self) -> None:
        """Fingerprint is a 64-character hex SHA-256 digest."""
        persona = _make_persona()
        fp = compute_fingerprint(persona)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_same_input_same_fingerprint(self) -> None:
        """Fingerprint is deterministic — same persona produces same digest."""
        persona_a = _make_persona()
        persona_b = _make_persona()
        assert compute_fingerprint(persona_a) == compute_fingerprint(persona_b)

    def test_skill_change_changes_fingerprint(self) -> None:
        """Adding a skill changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(
            skills=[_make_skill("Python"), _make_skill("FastAPI"), _make_skill("Go")]
        )
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_target_roles_change_changes_fingerprint(self) -> None:
        """Changing target_roles changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(target_roles=["Principal Engineer"])
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_target_skills_change_changes_fingerprint(self) -> None:
        """Changing target_skills changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(target_skills=["Machine Learning"])
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_stretch_appetite_change_changes_fingerprint(self) -> None:
        """Changing stretch_appetite changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(stretch_appetite="High")
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_home_city_change_changes_fingerprint(self) -> None:
        """Changing home_city changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(home_city="Austin, TX")
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_commutable_cities_change_changes_fingerprint(self) -> None:
        """Changing commutable_cities changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(commutable_cities=["Berkeley, CA"])
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_relocation_cities_change_changes_fingerprint(self) -> None:
        """Changing relocation_cities changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(relocation_cities=["Austin, TX"])
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_remote_preference_change_changes_fingerprint(self) -> None:
        """Changing remote_preference changes the fingerprint."""
        base = _make_persona()
        changed = _make_persona(remote_preference="Hybrid OK")
        assert compute_fingerprint(base) != compute_fingerprint(changed)

    def test_bio_change_does_not_change_fingerprint(self) -> None:
        """Non-material field bio does NOT affect the fingerprint."""
        base = _make_persona()
        changed = _make_persona(bio="Completely different bio text.")
        assert compute_fingerprint(base) == compute_fingerprint(changed)

    def test_summary_change_does_not_change_fingerprint(self) -> None:
        """Non-material field summary does NOT affect the fingerprint."""
        base = _make_persona()
        changed = _make_persona(summary="New summary.")
        assert compute_fingerprint(base) == compute_fingerprint(changed)

    def test_display_name_change_does_not_change_fingerprint(self) -> None:
        """Non-material field display_name does NOT affect the fingerprint."""
        base = _make_persona()
        changed = _make_persona(display_name="Different Name")
        assert compute_fingerprint(base) == compute_fingerprint(changed)

    def test_skill_order_does_not_affect_fingerprint(self) -> None:
        """Skill list order is normalized — reordering skills doesn't change fingerprint."""
        ordered = _make_persona(skills=[_make_skill("Python"), _make_skill("FastAPI")])
        reversed_order = _make_persona(
            skills=[_make_skill("FastAPI"), _make_skill("Python")]
        )
        assert compute_fingerprint(ordered) == compute_fingerprint(reversed_order)

    def test_empty_skills_accepted(self) -> None:
        """Persona with no skills produces a valid fingerprint."""
        persona = _make_persona(skills=[])
        fp = compute_fingerprint(persona)
        assert len(fp) == 64

    def test_empty_lists_fingerprint_differs_from_populated(self) -> None:
        """Empty target_roles fingerprint differs from populated one."""
        empty = _make_persona(target_roles=[])
        populated = _make_persona(target_roles=["Backend Engineer"])
        assert compute_fingerprint(empty) != compute_fingerprint(populated)


# =============================================================================
# check_staleness
# =============================================================================


class TestCheckStaleness:
    """Tests for check_staleness(persona, profile) -> bool."""

    def test_returns_false_when_fingerprints_match(self) -> None:
        """Profile is fresh when stored fingerprint matches current persona."""
        persona = _make_persona()
        fp = compute_fingerprint(persona)
        profile = _make_profile(fp)
        assert check_staleness(persona, profile) is False  # type: ignore[arg-type]

    def test_returns_true_when_fingerprints_differ(self) -> None:
        """Profile is stale when stored fingerprint differs from current persona."""
        persona = _make_persona()
        profile = _make_profile(_WRONG_FINGERPRINT)
        assert check_staleness(persona, profile) is True  # type: ignore[arg-type]

    def test_returns_true_when_profile_fingerprint_empty(self) -> None:
        """Profile with empty fingerprint is always stale."""
        persona = _make_persona()
        profile = _make_profile("")
        assert check_staleness(persona, profile) is True  # type: ignore[arg-type]

    def test_material_change_causes_staleness(self) -> None:
        """After a material field change, the profile fingerprint becomes stale."""
        original = _make_persona()
        stored_fp = compute_fingerprint(original)

        updated = _make_persona(stretch_appetite="High")
        profile = _make_profile(stored_fp)

        assert check_staleness(updated, profile) is True  # type: ignore[arg-type]

    def test_non_material_change_does_not_cause_staleness(self) -> None:
        """Non-material field changes leave the profile fresh."""
        original = _make_persona()
        stored_fp = compute_fingerprint(original)

        updated = _make_persona(bio="Different bio text.")
        profile = _make_profile(stored_fp)

        assert check_staleness(updated, profile) is False  # type: ignore[arg-type]


# =============================================================================
# mark_stale (integration — requires DB session)
# =============================================================================


class TestMarkStale:
    """Tests for mark_stale(db, persona_id) -> None."""

    async def test_sets_is_stale_true_on_existing_profile(
        self, db_session: AsyncSession, test_persona: Persona
    ) -> None:
        """mark_stale writes is_stale=True on the persona's profile."""
        await SearchProfileRepository.create(
            db_session,
            SearchProfileCreate(
                persona_id=test_persona.id,
                persona_fingerprint=_STORED_FINGERPRINT,
                is_stale=False,
            ),
        )
        await mark_stale(db_session, test_persona.id)

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, test_persona.id
        )
        assert profile is not None
        assert profile.is_stale is True

    async def test_no_error_when_profile_does_not_exist(
        self, db_session: AsyncSession
    ) -> None:
        """mark_stale silently no-ops when persona has no profile."""
        missing_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        await mark_stale(db_session, missing_id)  # Must not raise

    async def test_idempotent_when_already_stale(
        self, db_session: AsyncSession, test_persona: Persona
    ) -> None:
        """mark_stale is idempotent — calling twice on a stale profile is safe."""
        await SearchProfileRepository.create(
            db_session,
            SearchProfileCreate(
                persona_id=test_persona.id,
                persona_fingerprint=_STORED_FINGERPRINT,
                is_stale=True,
            ),
        )
        await mark_stale(db_session, test_persona.id)

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, test_persona.id
        )
        assert profile is not None
        assert profile.is_stale is True
