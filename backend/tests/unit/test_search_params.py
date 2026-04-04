"""Tests for the SearchParams dataclass.

REQ-007 §6.3, REQ-034 §5.1: SearchParams backward compatibility,
new optional fields (max_days_old, posted_after, remoteok_tags), and
__post_init__ validation contracts.

Coordinates with:
  - app/adapters/sources/base.py (SearchParams)
"""

from datetime import UTC, datetime

import pytest

from app.adapters.sources.base import SearchParams

_KEYWORDS = ["software", "engineer"]
_POSTED_AFTER = datetime(2026, 3, 1, tzinfo=UTC)


# =============================================================================
# Backward compatibility (REQ-007 §6.3)
# =============================================================================


class TestSearchParamsBackwardCompat:
    """Existing callers still work — no positional argument changes."""

    def test_keywords_only_construction_succeeds(self) -> None:
        """SearchParams accepts keywords alone — all other fields are optional."""
        params = SearchParams(keywords=_KEYWORDS)
        assert params.keywords == _KEYWORDS

    def test_original_optional_fields_accept_values(self) -> None:
        """Original optional fields (location, remote_only, page, results_per_page) still work."""
        params = SearchParams(
            keywords=_KEYWORDS,
            location="Remote",
            remote_only=True,
            page=2,
            results_per_page=50,
        )
        assert params.location == "Remote"
        assert params.remote_only is True
        assert params.page == 2
        assert params.results_per_page == 50


# =============================================================================
# New field defaults (REQ-034 §5.1)
# =============================================================================


class TestSearchParamsNewFieldDefaults:
    """New fields default to None — backward-compatible with existing callers."""

    def test_max_days_old_is_none_when_not_provided(self) -> None:
        """max_days_old is None when not provided."""
        params = SearchParams(keywords=_KEYWORDS)
        assert params.max_days_old is None

    def test_posted_after_is_none_when_not_provided(self) -> None:
        """posted_after is None when not provided."""
        params = SearchParams(keywords=_KEYWORDS)
        assert params.posted_after is None

    def test_remoteok_tags_is_none_when_not_provided(self) -> None:
        """remoteok_tags is None when not provided."""
        params = SearchParams(keywords=_KEYWORDS)
        assert params.remoteok_tags is None

    def test_new_fields_accept_provided_values(self) -> None:
        """All three new fields accept valid values when provided."""
        params = SearchParams(
            keywords=_KEYWORDS,
            max_days_old=7,
            posted_after=_POSTED_AFTER,
            remoteok_tags=["python", "backend"],
        )
        assert params.max_days_old == 7
        assert params.posted_after == _POSTED_AFTER
        assert params.remoteok_tags == ["python", "backend"]


# =============================================================================
# Validation contracts (REQ-034 §5.1)
# =============================================================================


class TestSearchParamsValidation:
    """__post_init__ rejects invalid field values at construction time."""

    def test_raises_when_posted_after_is_timezone_naive(self) -> None:
        """posted_after without tzinfo raises ValueError — prevents silent UTC/local mismatch."""
        with pytest.raises(ValueError, match="timezone-aware"):
            SearchParams(keywords=_KEYWORDS, posted_after=datetime(2026, 3, 1))

    def test_posted_after_accepts_timezone_aware_datetime(self) -> None:
        """posted_after with tzinfo does not raise."""
        params = SearchParams(keywords=_KEYWORDS, posted_after=_POSTED_AFTER)
        assert params.posted_after == _POSTED_AFTER

    def test_raises_when_max_days_old_exceeds_90(self) -> None:
        """max_days_old > 90 raises ValueError — prevents quota exhaustion."""
        with pytest.raises(ValueError, match="max_days_old"):
            SearchParams(keywords=_KEYWORDS, max_days_old=91)

    def test_raises_when_max_days_old_is_zero(self) -> None:
        """max_days_old of 0 raises ValueError — must be at least 1 day."""
        with pytest.raises(ValueError, match="max_days_old"):
            SearchParams(keywords=_KEYWORDS, max_days_old=0)

    def test_max_days_old_accepts_boundary_values(self) -> None:
        """max_days_old accepts 1 and 90 (inclusive boundaries)."""
        params_min = SearchParams(keywords=_KEYWORDS, max_days_old=1)
        params_max = SearchParams(keywords=_KEYWORDS, max_days_old=90)
        assert params_min.max_days_old == 1
        assert params_max.max_days_old == 90

    def test_raises_when_remoteok_tags_list_exceeds_10(self) -> None:
        """remoteok_tags with >10 tags raises ValueError — prevents URL length overflow."""
        with pytest.raises(ValueError, match="remoteok_tags"):
            SearchParams(
                keywords=_KEYWORDS, remoteok_tags=[f"tag{i}" for i in range(11)]
            )

    def test_raises_when_remoteok_tag_contains_invalid_chars(self) -> None:
        """remoteok_tags with a tag containing '&' raises ValueError — prevents query string injection."""
        with pytest.raises(ValueError, match="Invalid remoteok tag"):
            SearchParams(keywords=_KEYWORDS, remoteok_tags=["python&evil=1"])

    def test_remoteok_tags_accepts_valid_tag_formats(self) -> None:
        """remoteok_tags accepts alphanumeric, dots, underscores, hyphens."""
        params = SearchParams(
            keywords=_KEYWORDS,
            remoteok_tags=["python", "node.js", "full_stack", "back-end"],
        )
        assert len(params.remoteok_tags) == 4  # type: ignore[arg-type]
