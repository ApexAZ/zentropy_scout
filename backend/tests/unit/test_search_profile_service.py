"""Tests for SearchProfileService — fingerprint, staleness, mark_stale, and generate_profile.

REQ-034 §4.3-§4.4: Verifies compute_fingerprint is deterministic and changes on
material field updates but not on non-material fields. Verifies check_staleness
and mark_stale against a live PostgreSQL session. Verifies generate_profile JSON
parsing, error propagation, and stub-mode (provider=None) behavior.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.providers.errors import ProviderError
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import SearchBucketSchema, SearchProfileCreate
from app.services.discovery.search_profile_service import (
    SearchProfileGenerationError,
    build_search_params,
    check_staleness,
    compute_fingerprint,
    generate_profile,
    mark_stale,
)

_STORED_FINGERPRINT = "a" * 64  # Valid 64-char fingerprint used in DB fixtures
_WRONG_FINGERPRINT = "stale" * 16  # 80-char string that never matches a real SHA-256

# Valid LLM response for generate_profile tests
_VALID_RESPONSE = json.dumps(
    {
        "fit_searches": [
            {
                "label": "Senior Backend Engineer",
                "keywords": ["python", "fastapi"],
                "titles": ["Senior Backend Engineer"],
                "remoteok_tags": ["python"],
                "location": None,
            }
        ],
        "stretch_searches": [
            {
                "label": "Engineering Manager",
                "keywords": ["engineering manager"],
                "titles": ["Engineering Manager"],
                "remoteok_tags": ["manager"],
                "location": None,
            }
        ],
    }
)

# Patch target for SearchProfileRepository.upsert in generate_profile tests
_REPO_UPSERT = (
    "app.services.discovery.search_profile_service.SearchProfileRepository.upsert"
)

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
            "id": uuid.uuid4(),
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
            "current_role": "Senior Backend Engineer",
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


class _FakeProfile:
    """Minimal profile-like object — only persona_fingerprint is needed."""

    def __init__(self, fingerprint: str) -> None:
        self.persona_fingerprint = fingerprint


def _make_skill(name: str) -> Any:
    """Build a fake skill object with the given skill_name."""
    return _FakeSkill(name)


def _make_persona(**overrides: object) -> Any:
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


# =============================================================================
# generate_profile helpers
# =============================================================================


def _make_capture_upsert() -> tuple[dict[str, object], AsyncMock]:
    """Return a (captured, mock) pair for patching SearchProfileRepository.upsert.

    The mock captures the SearchProfileCreate data passed to upsert so tests
    can assert on it without a real database session.
    """
    captured: dict[str, object] = {}

    async def _capture(_db: object, _persona_id: object, data: object) -> MagicMock:
        captured["data"] = data
        return MagicMock()

    return captured, AsyncMock(side_effect=_capture)


def _make_mock_provider(content: str = _VALID_RESPONSE) -> AsyncMock:
    """Return a mock LLMProvider whose complete() returns the given content."""
    mock_provider = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = content
    mock_provider.complete.return_value = mock_response
    return mock_provider


# =============================================================================
# generate_profile (AI generation — provider mocked)
# =============================================================================


class TestGenerateProfile:
    """Tests for generate_profile(db, persona, provider) -> SearchProfile."""

    async def test_provider_none_creates_profile_with_empty_buckets(self) -> None:
        """provider=None (stub mode) creates a profile with empty fit/stretch buckets."""
        persona = _make_persona()
        captured, mock_upsert = _make_capture_upsert()
        with patch(_REPO_UPSERT, mock_upsert):
            result = await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=None,  # type: ignore[arg-type]
            )
        assert result is not None
        data = captured["data"]
        assert data.fit_searches == []  # type: ignore[union-attr]
        assert data.stretch_searches == []  # type: ignore[union-attr]
        assert data.is_stale is False  # type: ignore[union-attr]
        assert data.generated_at is not None  # type: ignore[union-attr]

    async def test_valid_json_populates_fit_searches(self) -> None:
        """Valid LLM JSON populates fit_searches with parsed SearchBucketSchema objects."""
        persona = _make_persona()
        captured, mock_upsert = _make_capture_upsert()
        with patch(_REPO_UPSERT, mock_upsert):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=_make_mock_provider(),  # type: ignore[arg-type]
            )
        data = captured["data"]
        assert len(data.fit_searches) == 1  # type: ignore[union-attr]
        assert data.fit_searches[0].label == "Senior Backend Engineer"  # type: ignore[union-attr]

    async def test_valid_json_populates_stretch_searches(self) -> None:
        """Valid LLM JSON populates stretch_searches with parsed SearchBucketSchema objects."""
        persona = _make_persona()
        captured, mock_upsert = _make_capture_upsert()
        with patch(_REPO_UPSERT, mock_upsert):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=_make_mock_provider(),  # type: ignore[arg-type]
            )
        data = captured["data"]
        assert len(data.stretch_searches) == 1  # type: ignore[union-attr]
        assert data.stretch_searches[0].label == "Engineering Manager"  # type: ignore[union-attr]

    async def test_stores_current_fingerprint(self) -> None:
        """Generated profile stores the current persona fingerprint."""
        persona = _make_persona()
        expected_fp = compute_fingerprint(persona)
        captured, mock_upsert = _make_capture_upsert()
        with patch(_REPO_UPSERT, mock_upsert):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=_make_mock_provider(),  # type: ignore[arg-type]
            )
        assert captured["data"].persona_fingerprint == expected_fp  # type: ignore[union-attr]

    async def test_provider_error_raises_generation_error(self) -> None:
        """ProviderError from the LLM raises SearchProfileGenerationError."""
        persona = _make_persona()
        mock_provider = AsyncMock()
        mock_provider.complete.side_effect = ProviderError("LLM unavailable")
        with (
            patch(_REPO_UPSERT, new_callable=AsyncMock),
            pytest.raises(SearchProfileGenerationError),
        ):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=mock_provider,  # type: ignore[arg-type]
            )

    async def test_empty_content_raises_generation_error(self) -> None:
        """Empty LLM response content raises SearchProfileGenerationError."""
        persona = _make_persona()
        with (
            patch(_REPO_UPSERT, new_callable=AsyncMock),
            pytest.raises(SearchProfileGenerationError),
        ):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=_make_mock_provider(content=None),  # type: ignore[arg-type]
            )

    async def test_invalid_json_raises_generation_error(self) -> None:
        """Non-JSON LLM response raises SearchProfileGenerationError."""
        persona = _make_persona()
        with (
            patch(_REPO_UPSERT, new_callable=AsyncMock),
            pytest.raises(SearchProfileGenerationError),
        ):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=_make_mock_provider(content="not valid json"),  # type: ignore[arg-type]
            )

    async def test_sets_is_stale_false_on_generation(self) -> None:
        """Generated profile has is_stale=False and generated_at set."""
        persona = _make_persona()
        captured, mock_upsert = _make_capture_upsert()
        with patch(_REPO_UPSERT, mock_upsert):
            await generate_profile(
                db=MagicMock(),
                persona=persona,
                provider=_make_mock_provider(),  # type: ignore[arg-type]
            )
        data = captured["data"]
        assert data.is_stale is False  # type: ignore[union-attr]
        assert data.generated_at is not None  # type: ignore[union-attr]


# =============================================================================
# build_search_params — delta calculation and SearchParams construction
# =============================================================================


class TestBuildSearchParams:
    """Tests for build_search_params(bucket, persona, last_poll_at).

    REQ-034 §5.2: SearchParams construction from a SearchBucket.
    """

    def _make_bucket(self, **overrides: object) -> SearchBucketSchema:
        """Build a SearchBucketSchema with sensible defaults."""
        defaults: dict[str, object] = {
            "label": "Senior Backend Engineer",
            "keywords": ["python", "fastapi"],
            "titles": ["Senior Backend Engineer", "Staff Engineer"],
            "remoteok_tags": ["python", "backend"],
            "location": None,
        }
        defaults.update(overrides)
        return SearchBucketSchema(**defaults)  # type: ignore[arg-type]

    # -- delta calculation ---------------------------------------------------

    def test_first_poll_uses_7_day_seed(self) -> None:
        """First poll (last_poll_at=None) seeds max_days_old=7."""
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.max_days_old == 7

    def test_recent_poll_calculates_delta(self) -> None:
        """2.5-day-old last_poll_at → ceil(2.5)+1 = 4.

        Uses 2 days + 12 hours to avoid the epsilon rounding at exact day
        boundaries. ceil(2.5) = 3, +1 = 4.
        """
        two_and_half_days_ago = datetime.now(UTC) - timedelta(days=2, hours=12)
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(
            bucket, persona, last_poll_at=two_and_half_days_ago
        )  # type: ignore[arg-type]

        assert result.max_days_old == 4

    def test_same_day_poll_returns_2(self) -> None:
        """A poll from seconds ago → ceil(~0)+1 = 2 (practical minimum for any past poll).

        The max(1, ...) guard only fires for zero-duration deltas. Any positive
        delta gives ceil(x) >= 1, so ceil(x)+1 >= 2.
        """
        seconds_ago = datetime.now(UTC) - timedelta(seconds=30)
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=seconds_ago)  # type: ignore[arg-type]

        assert result.max_days_old == 2

    def test_delta_capped_at_90_days(self) -> None:
        """Last poll 120 days ago → max_days_old capped at 90."""
        very_old = datetime.now(UTC) - timedelta(days=120)
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=very_old)  # type: ignore[arg-type]

        assert result.max_days_old == 90

    def test_delta_boundary_at_88_days_returns_90(self) -> None:
        """88-day-old poll → ceil(88+ε)+1 = 90, which hits the _MAX_POLL_DAYS cap exactly.

        ceil(88 + epsilon) = 89, then 89+1 = 90 = _MAX_POLL_DAYS. This verifies the cap
        is inclusive and that the +1 buffer causes the boundary to sit at 88 days, not 89.
        """
        eighty_eight_days_ago = datetime.now(UTC) - timedelta(days=88)
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(
            bucket, persona, last_poll_at=eighty_eight_days_ago
        )  # type: ignore[arg-type]

        assert result.max_days_old == 90

    # -- field construction --------------------------------------------------

    def test_keywords_concatenates_bucket_keywords_and_titles(self) -> None:
        """keywords = bucket.keywords + bucket.titles (per REQ-034 §5.2)."""
        bucket = self._make_bucket(
            keywords=["python", "fastapi"],
            titles=["Senior Backend Engineer"],
        )
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.keywords == ["python", "fastapi", "Senior Backend Engineer"]

    def test_location_uses_bucket_location_when_present(self) -> None:
        """bucket.location overrides persona.home_city when set."""
        bucket = self._make_bucket(location="Austin, TX")
        persona = _make_persona(home_city="San Francisco, CA")
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.location == "Austin, TX"

    def test_location_falls_back_to_persona_home_city_when_bucket_none(self) -> None:
        """None bucket.location falls back to persona.home_city."""
        bucket = self._make_bucket(location=None)
        persona = _make_persona(home_city="Chicago, IL")
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.location == "Chicago, IL"

    def test_remote_only_when_preference_is_remote_only(self) -> None:
        """remote_only=True when persona.remote_preference == 'Remote Only'."""
        bucket = self._make_bucket()
        persona = _make_persona(remote_preference="Remote Only")
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.remote_only is True

    def test_remote_only_false_for_other_preferences(self) -> None:
        """remote_only=False when persona.remote_preference is not 'Remote Only'."""
        bucket = self._make_bucket()
        persona = _make_persona(remote_preference="Hybrid OK")
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.remote_only is False

    def test_remoteok_tags_from_bucket(self) -> None:
        """Valid remoteok_tags from the bucket are passed through."""
        bucket = self._make_bucket(remoteok_tags=["python", "backend"])
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.remoteok_tags == ["python", "backend"]

    def test_invalid_remoteok_tags_filtered_out(self) -> None:
        """Tags with spaces or invalid characters are excluded from SearchParams."""
        bucket = self._make_bucket(
            remoteok_tags=["python", "product manager"]  # space is invalid
        )
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.remoteok_tags == ["python"]

    def test_all_invalid_remoteok_tags_returns_none(self) -> None:
        """When all tags fail validation, remoteok_tags is None (no tag filter)."""
        bucket = self._make_bucket(remoteok_tags=["has space", "also!invalid"])
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.remoteok_tags is None

    def test_empty_remoteok_tags_returns_none(self) -> None:
        """Empty remoteok_tags list produces None (no tag filter applied)."""
        bucket = self._make_bucket(remoteok_tags=[])
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.remoteok_tags is None

    def test_posted_after_is_utc(self) -> None:
        """posted_after is always a timezone-aware UTC datetime."""
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.posted_after is not None
        assert result.posted_after.tzinfo == UTC

    def test_default_results_per_page_is_50(self) -> None:
        """results_per_page defaults to 50 per REQ-034 §5.2."""
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(bucket, persona, last_poll_at=None)  # type: ignore[arg-type]

        assert result.results_per_page == 50

    def test_custom_results_per_page_respected(self) -> None:
        """Caller-supplied results_per_page is passed through."""
        bucket = self._make_bucket()
        persona = _make_persona()
        result = build_search_params(  # type: ignore[arg-type]
            bucket, persona, last_poll_at=None, results_per_page=100
        )

        assert result.results_per_page == 100
