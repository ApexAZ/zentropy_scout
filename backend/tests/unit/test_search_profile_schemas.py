"""Tests for SearchProfile Pydantic schemas.

REQ-034 §4.2, §4.5: Verifies SearchBucketSchema shape validation, and
SearchProfileRead/Create/Update/ApiUpdate schema construction and field
constraints. Specifically verifies that SearchProfileApiUpdate rejects
internal system fields (is_stale, persona_fingerprint, generated_at).
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.search_profile import (
    SearchBucketSchema,
    SearchProfileApiUpdate,
    SearchProfileCreate,
    SearchProfileRead,
    SearchProfileUpdate,
)

_NOW = datetime.now(UTC)
_PERSONA_ID = uuid.uuid4()
_PROFILE_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bucket(**overrides: object) -> dict:
    """Build a minimal valid SearchBucketSchema dict."""
    data: dict = {
        "label": "Senior Software Engineer",
        "keywords": ["python", "fastapi"],
        "titles": ["Senior Software Engineer", "Staff Engineer"],
        "remoteok_tags": ["python", "senior"],
    }
    data.update(overrides)
    return data


def _make_read_data(**overrides: object) -> dict:
    """Build a minimal valid SearchProfileRead dict."""
    data: dict = {
        "id": _PROFILE_ID,
        "persona_id": _PERSONA_ID,
        "fit_searches": [_make_bucket()],
        "stretch_searches": [],
        "persona_fingerprint": "a" * 64,
        "is_stale": False,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    data.update(overrides)
    return data


# =============================================================================
# SearchBucketSchema
# =============================================================================


class TestSearchBucketSchema:
    """Tests for SearchBucketSchema — JSONB bucket shape validation."""

    def test_valid_bucket_accepted(self) -> None:
        """Valid bucket with all required fields passes validation."""
        bucket = SearchBucketSchema(**_make_bucket())
        assert bucket.label == "Senior Software Engineer"
        assert bucket.keywords == ["python", "fastapi"]
        assert bucket.titles == ["Senior Software Engineer", "Staff Engineer"]
        assert bucket.remoteok_tags == ["python", "senior"]

    def test_location_defaults_to_none(self) -> None:
        """location is optional and defaults to None."""
        bucket = SearchBucketSchema(**_make_bucket())
        assert bucket.location is None

    def test_explicit_location_stored(self) -> None:
        """Explicit location value is preserved."""
        bucket = SearchBucketSchema(**_make_bucket(location="New York, NY"))
        assert bucket.location == "New York, NY"

    def test_null_location_accepted(self) -> None:
        """Explicit None location is accepted (persona home_city fallback)."""
        bucket = SearchBucketSchema(**_make_bucket(location=None))
        assert bucket.location is None

    def test_empty_lists_accepted(self) -> None:
        """keywords, titles, and remoteok_tags can be empty lists."""
        bucket = SearchBucketSchema(
            label="Generic Role",
            keywords=[],
            titles=[],
            remoteok_tags=[],
        )
        assert bucket.keywords == []
        assert bucket.titles == []
        assert bucket.remoteok_tags == []

    def test_extra_field_rejected(self) -> None:
        """Extra fields are forbidden (security: prevents mass assignment)."""
        with pytest.raises(ValidationError) as exc_info:
            SearchBucketSchema(
                **_make_bucket(),
                injected_field="malicious",  # pyright: ignore[reportCallIssue]
            )
        errors = exc_info.value.errors()
        assert any("injected_field" in str(e) for e in errors)

    def test_missing_label_rejected(self) -> None:
        """label is required — ValidationError when absent."""
        data = _make_bucket()
        del data["label"]
        with pytest.raises(ValidationError):
            SearchBucketSchema(**data)

    def test_missing_keywords_rejected(self) -> None:
        """keywords is required — ValidationError when absent."""
        data = _make_bucket()
        del data["keywords"]
        with pytest.raises(ValidationError):
            SearchBucketSchema(**data)

    def test_missing_titles_rejected(self) -> None:
        """titles is required — ValidationError when absent."""
        data = _make_bucket()
        del data["titles"]
        with pytest.raises(ValidationError):
            SearchBucketSchema(**data)

    def test_missing_remoteok_tags_rejected(self) -> None:
        """remoteok_tags is required — ValidationError when absent."""
        data = _make_bucket()
        del data["remoteok_tags"]
        with pytest.raises(ValidationError):
            SearchBucketSchema(**data)


# =============================================================================
# SearchProfileRead
# =============================================================================


class TestSearchProfileRead:
    """Tests for SearchProfileRead — full profile response schema."""

    def test_valid_data_accepted(self) -> None:
        """SearchProfileRead accepts all required fields."""
        profile = SearchProfileRead(**_make_read_data())
        assert profile.persona_id == _PERSONA_ID
        assert profile.is_stale is False
        assert profile.persona_fingerprint == "a" * 64

    def test_optional_timestamps_default_none(self) -> None:
        """generated_at and approved_at default to None when omitted."""
        profile = SearchProfileRead(**_make_read_data())
        assert profile.generated_at is None
        assert profile.approved_at is None

    def test_optional_timestamps_accepted(self) -> None:
        """generated_at and approved_at are accepted when provided."""
        profile = SearchProfileRead(
            **_make_read_data(generated_at=_NOW, approved_at=_NOW)
        )
        assert profile.generated_at == _NOW
        assert profile.approved_at == _NOW

    def test_multiple_fit_and_stretch_buckets(self) -> None:
        """fit_searches and stretch_searches accept multiple buckets."""
        buckets = [_make_bucket(label=f"Role {i}") for i in range(3)]
        profile = SearchProfileRead(
            **_make_read_data(fit_searches=buckets, stretch_searches=buckets)
        )
        assert len(profile.fit_searches) == 3
        assert len(profile.stretch_searches) == 3

    def test_invalid_bucket_in_fit_searches_rejected(self) -> None:
        """fit_searches rejects items that are not valid SearchBucket shapes."""
        with pytest.raises(ValidationError):
            SearchProfileRead(**_make_read_data(fit_searches=[{"not_a_bucket": True}]))

    def test_extra_field_rejected(self) -> None:
        """Extra fields are forbidden on SearchProfileRead."""
        with pytest.raises(ValidationError) as exc_info:
            SearchProfileRead(
                **_make_read_data(),
                extra_field="bad",  # pyright: ignore[reportCallIssue]
            )
        errors = exc_info.value.errors()
        assert any("extra_field" in str(e) for e in errors)

    def test_from_attributes_mode_enabled(self) -> None:
        """from_attributes=True allows construction from ORM-like objects."""

        class FakeProfile:
            id = _PROFILE_ID
            persona_id = _PERSONA_ID
            fit_searches = [
                {"label": "SWE", "keywords": [], "titles": [], "remoteok_tags": []}
            ]
            stretch_searches = []
            persona_fingerprint = "b" * 64
            is_stale = True
            generated_at = None
            approved_at = None
            created_at = _NOW
            updated_at = _NOW

        profile = SearchProfileRead.model_validate(FakeProfile(), from_attributes=True)
        assert profile.persona_id == _PERSONA_ID
        assert profile.is_stale is True


# =============================================================================
# SearchProfileCreate
# =============================================================================


class TestSearchProfileCreate:
    """Tests for SearchProfileCreate — internal creation request schema."""

    def test_minimal_valid_create(self) -> None:
        """Only persona_id is required — all others have defaults."""
        create = SearchProfileCreate(persona_id=_PERSONA_ID)
        assert create.persona_id == _PERSONA_ID
        assert create.fit_searches == []
        assert create.stretch_searches == []
        assert create.persona_fingerprint == ""
        assert create.is_stale is True
        assert create.generated_at is None
        assert create.approved_at is None

    def test_valid_buckets_accepted(self) -> None:
        """fit_searches and stretch_searches accept valid bucket lists."""
        create = SearchProfileCreate(
            persona_id=_PERSONA_ID,
            fit_searches=[SearchBucketSchema(**_make_bucket())],
            stretch_searches=[SearchBucketSchema(**_make_bucket(label="Stretch Role"))],
        )
        assert len(create.fit_searches) == 1
        assert create.fit_searches[0].label == "Senior Software Engineer"
        assert create.stretch_searches[0].label == "Stretch Role"

    def test_invalid_bucket_shape_in_fit_searches_rejected(self) -> None:
        """Invalid bucket shapes in fit_searches raise ValidationError."""
        with pytest.raises(ValidationError):
            SearchProfileCreate(
                persona_id=_PERSONA_ID,
                fit_searches=[{"missing_required_fields": True}],  # pyright: ignore[reportArgumentType]
            )

    def test_extra_field_rejected(self) -> None:
        """Extra fields are forbidden on SearchProfileCreate."""
        with pytest.raises(ValidationError) as exc_info:
            SearchProfileCreate(
                persona_id=_PERSONA_ID,
                injected="bad",  # pyright: ignore[reportCallIssue]
            )
        errors = exc_info.value.errors()
        assert any("injected" in str(e) for e in errors)

    def test_missing_persona_id_rejected(self) -> None:
        """persona_id is required — ValidationError when absent."""
        with pytest.raises(ValidationError):
            SearchProfileCreate()  # pyright: ignore[reportCallIssue]


# =============================================================================
# SearchProfileUpdate
# =============================================================================


class TestSearchProfileUpdate:
    """Tests for SearchProfileUpdate — partial update (PATCH) request schema."""

    def test_empty_update_is_valid(self) -> None:
        """All fields are optional — empty update is valid."""
        update = SearchProfileUpdate()
        assert update.fit_searches is None
        assert update.stretch_searches is None
        assert update.persona_fingerprint is None
        assert update.is_stale is None
        assert update.generated_at is None
        assert update.approved_at is None

    def test_setting_approved_at(self) -> None:
        """approved_at can be set to approve a profile."""
        update = SearchProfileUpdate(approved_at=_NOW)
        assert update.approved_at == _NOW

    def test_setting_is_stale_false(self) -> None:
        """is_stale can be explicitly set to False."""
        update = SearchProfileUpdate(is_stale=False)
        assert update.is_stale is False

    def test_valid_bucket_update(self) -> None:
        """fit_searches can be updated with valid bucket list."""
        buckets = [SearchBucketSchema(**_make_bucket())]
        update = SearchProfileUpdate(fit_searches=buckets)
        assert update.fit_searches is not None
        assert len(update.fit_searches) == 1

    def test_invalid_bucket_in_update_rejected(self) -> None:
        """Invalid bucket shape in fit_searches update raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchProfileUpdate(fit_searches=[{"bad": "shape"}])  # pyright: ignore[reportArgumentType]

    def test_extra_field_rejected(self) -> None:
        """Extra fields are forbidden on SearchProfileUpdate."""
        with pytest.raises(ValidationError) as exc_info:
            SearchProfileUpdate(
                persona_id=_PERSONA_ID,  # pyright: ignore[reportCallIssue]
            )
        errors = exc_info.value.errors()
        assert any("persona_id" in str(e) for e in errors)


# =============================================================================
# Size constraint tests (security: defense-in-depth against oversized payloads)
# =============================================================================


class TestSearchBucketSizeConstraints:
    """Verify SearchBucketSchema enforces length limits on all string fields."""

    def test_empty_label_rejected(self) -> None:
        """label must be non-empty (min_length=1)."""
        with pytest.raises(ValidationError):
            SearchBucketSchema(**_make_bucket(label=""))

    def test_oversized_label_rejected(self) -> None:
        """label exceeding 120 characters raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchBucketSchema(**_make_bucket(label="x" * 121))

    def test_max_label_accepted(self) -> None:
        """label at exactly 120 characters passes validation."""
        bucket = SearchBucketSchema(**_make_bucket(label="x" * 120))
        assert len(bucket.label) == 120

    def test_oversized_keyword_item_rejected(self) -> None:
        """A keyword string exceeding 100 characters raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchBucketSchema(**_make_bucket(keywords=["k" * 101]))

    def test_oversized_keywords_list_rejected(self) -> None:
        """A keywords list exceeding 30 items raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchBucketSchema(**_make_bucket(keywords=["python"] * 31))

    def test_oversized_location_rejected(self) -> None:
        """location exceeding 120 characters raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchBucketSchema(**_make_bucket(location="x" * 121))


class TestSearchProfileCreateSizeConstraints:
    """Verify SearchProfileCreate enforces bucket list and fingerprint limits."""

    def test_oversized_fingerprint_rejected(self) -> None:
        """persona_fingerprint exceeding 64 characters raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchProfileCreate(
                persona_id=_PERSONA_ID,
                persona_fingerprint="a" * 65,
            )

    def test_max_fingerprint_accepted(self) -> None:
        """persona_fingerprint at exactly 64 characters passes validation."""
        create = SearchProfileCreate(
            persona_id=_PERSONA_ID,
            persona_fingerprint="a" * 64,
        )
        assert len(create.persona_fingerprint) == 64

    def test_oversized_fit_searches_list_rejected(self) -> None:
        """fit_searches with more than 15 buckets raises ValidationError."""
        buckets = [
            SearchBucketSchema(**_make_bucket(label=f"Role {i}")) for i in range(16)
        ]
        with pytest.raises(ValidationError):
            SearchProfileCreate(persona_id=_PERSONA_ID, fit_searches=buckets)

    def test_oversized_stretch_searches_list_rejected(self) -> None:
        """stretch_searches with more than 15 buckets raises ValidationError."""
        buckets = [
            SearchBucketSchema(**_make_bucket(label=f"Role {i}")) for i in range(16)
        ]
        with pytest.raises(ValidationError):
            SearchProfileCreate(persona_id=_PERSONA_ID, stretch_searches=buckets)


class TestSearchProfileUpdateSizeConstraints:
    """Verify SearchProfileUpdate enforces the same size limits as Create."""

    def test_oversized_fingerprint_update_rejected(self) -> None:
        """persona_fingerprint update exceeding 64 characters raises ValidationError."""
        with pytest.raises(ValidationError):
            SearchProfileUpdate(persona_fingerprint="a" * 65)

    def test_oversized_fit_searches_update_rejected(self) -> None:
        """fit_searches update with more than 15 buckets raises ValidationError."""
        buckets = [
            SearchBucketSchema(**_make_bucket(label=f"Role {i}")) for i in range(16)
        ]
        with pytest.raises(ValidationError):
            SearchProfileUpdate(fit_searches=buckets)


# =============================================================================
# SearchProfileApiUpdate
# =============================================================================


class TestSearchProfileApiUpdate:
    """SearchProfileApiUpdate — user-facing PATCH schema (3 fields only)."""

    def test_empty_api_update_is_valid(self) -> None:
        """All fields optional — empty update is valid (no-op PATCH)."""
        update = SearchProfileApiUpdate()
        assert update.fit_searches is None
        assert update.stretch_searches is None
        assert update.approved_at is None

    def test_api_update_accepts_user_settable_fields(self) -> None:
        """fit_searches, stretch_searches, and approved_at are accepted."""
        bucket = SearchBucketSchema(**_make_bucket())
        update = SearchProfileApiUpdate(
            fit_searches=[bucket],
            approved_at=_NOW,
        )
        assert len(update.fit_searches) == 1  # type: ignore[arg-type]
        assert update.approved_at == _NOW

    def test_api_update_rejects_is_stale(self) -> None:
        """is_stale is an internal field — rejected by extra='forbid'."""
        with pytest.raises(ValidationError):
            SearchProfileApiUpdate(is_stale=False)  # type: ignore[call-arg]

    def test_api_update_rejects_persona_fingerprint(self) -> None:
        """persona_fingerprint is an internal field — rejected by extra='forbid'."""
        with pytest.raises(ValidationError):
            SearchProfileApiUpdate(persona_fingerprint="a" * 64)  # type: ignore[call-arg]

    def test_api_update_rejects_generated_at(self) -> None:
        """generated_at is an internal field — rejected by extra='forbid'."""
        with pytest.raises(ValidationError):
            SearchProfileApiUpdate(generated_at=_NOW)  # type: ignore[call-arg]
