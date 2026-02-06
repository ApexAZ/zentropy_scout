"""Tests for persona change detection during content generation.

REQ-010 §8.3: Persona Changed During Generation.

Detects when the user's persona was updated during the 10-30s generation
window by comparing persona.updated_at timestamps before and after.
Generated content is always preserved; a warning prompts the user to
optionally regenerate.
"""

from datetime import UTC, datetime

import pytest

from app.services.persona_change import (
    _WARNING_MESSAGE,
    check_persona_changed,
)

# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_warning_message_value(self) -> None:
        """Warning message should match the spec-defined text."""
        assert _WARNING_MESSAGE == (
            "Your profile was updated during generation. "
            "Want to regenerate with your latest information?"
        )


# =============================================================================
# PersonaChangeResult Structure
# =============================================================================


class TestPersonaChangeResultStructure:
    """Tests for PersonaChangeResult frozen dataclass."""

    def test_result_is_frozen(self) -> None:
        """PersonaChangeResult should be immutable."""
        ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=ts,
            current_updated_at=ts,
        )
        with pytest.raises(AttributeError):
            result.persona_changed = True  # type: ignore[misc]

    def test_result_has_all_fields(self) -> None:
        """PersonaChangeResult should have persona_changed and warning fields."""
        ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=ts,
            current_updated_at=ts,
        )
        assert hasattr(result, "persona_changed")
        assert hasattr(result, "warning")

    def test_unchanged_result_field_types(self) -> None:
        """Unchanged persona result should have correct field types."""
        ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=ts,
            current_updated_at=ts,
        )
        assert isinstance(result.persona_changed, bool)
        assert result.warning is None


# =============================================================================
# Same Timestamps — No Change Detected
# =============================================================================


class TestSameTimestamps:
    """REQ-010 §8.3: When timestamps match, no persona change occurred."""

    def test_identical_timestamps_not_changed(self) -> None:
        """Identical timestamps should report no persona change."""
        ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=ts,
            current_updated_at=ts,
        )
        assert result.persona_changed is False

    def test_identical_timestamps_no_warning(self) -> None:
        """Identical timestamps should produce no warning."""
        ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=ts,
            current_updated_at=ts,
        )
        assert result.warning is None

    def test_equal_but_different_objects_not_changed(self) -> None:
        """Equal datetime objects (different instances) should detect no change."""
        ts1 = datetime(2026, 6, 1, 12, 30, 45, tzinfo=UTC)
        ts2 = datetime(2026, 6, 1, 12, 30, 45, tzinfo=UTC)
        assert ts1 is not ts2  # Different objects
        result = check_persona_changed(
            original_updated_at=ts1,
            current_updated_at=ts2,
        )
        assert result.persona_changed is False
        assert result.warning is None


# =============================================================================
# Different Timestamps — Persona Changed
# =============================================================================


class TestDifferentTimestamps:
    """REQ-010 §8.3: When timestamps differ, persona was changed mid-generation."""

    def test_newer_timestamp_detected_as_changed(self) -> None:
        """Newer current_updated_at should detect persona change."""
        original = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 15, 10, 0, 30, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.persona_changed is True

    def test_changed_persona_has_warning(self) -> None:
        """Changed persona should include the spec-defined warning message."""
        original = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 15, 10, 0, 30, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.warning == _WARNING_MESSAGE

    def test_warning_text_matches_spec(self) -> None:
        """Warning text should exactly match the REQ-010 §8.3 specification."""
        original = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 15, 10, 5, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.warning == (
            "Your profile was updated during generation. "
            "Want to regenerate with your latest information?"
        )

    def test_older_timestamp_also_detected_as_changed(self) -> None:
        """Even an older current_updated_at should detect change (clock skew)."""
        original = datetime(2026, 1, 15, 10, 0, 30, tzinfo=UTC)
        current = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.persona_changed is True
        assert result.warning is not None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case handling for persona change detection."""

    def test_microsecond_difference_detected(self) -> None:
        """Even a 1-microsecond difference should detect a change."""
        original = datetime(2026, 1, 15, 10, 0, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 15, 10, 0, 0, 1, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.persona_changed is True

    def test_timezone_aware_comparison(self) -> None:
        """Timezone-aware datetimes should compare correctly."""
        original = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.persona_changed is False

    def test_large_time_gap_detected(self) -> None:
        """A gap of hours should still detect change."""
        original = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.persona_changed is True
        assert result.warning == _WARNING_MESSAGE

    def test_different_dates_detected(self) -> None:
        """Timestamps from different days should detect change."""
        original = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        current = datetime(2026, 1, 16, 10, 0, 0, tzinfo=UTC)
        result = check_persona_changed(
            original_updated_at=original,
            current_updated_at=current,
        )
        assert result.persona_changed is True
        assert result.warning == _WARNING_MESSAGE
