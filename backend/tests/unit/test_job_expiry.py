"""Tests for job expiry checks during content generation.

REQ-010 §8.2: Expired Job During Generation.

Two phases:
1. Pre-generation: If job is already expired, abort with error + suggestion.
2. Post-generation: If job expired mid-generation, preserve content + warning.
"""

import pytest

from app.services.job_expiry import (
    _EXPIRED_STATUS,
    _VALID_STATUSES,
    check_job_expiry_after,
    check_job_expiry_before,
)

# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_expired_status_value(self) -> None:
        """The expired status constant should be 'Expired'."""
        assert _EXPIRED_STATUS == "Expired"

    def test_valid_statuses_contains_all_known(self) -> None:
        """Valid statuses should match the DB check constraint."""
        expected = frozenset({"Discovered", "Dismissed", "Applied", "Expired"})
        assert expected == _VALID_STATUSES

    def test_valid_statuses_is_frozenset(self) -> None:
        """Valid statuses should be an immutable frozenset."""
        assert isinstance(_VALID_STATUSES, frozenset)


# =============================================================================
# JobExpiryResult Structure
# =============================================================================


class TestJobExpiryResultStructure:
    """Tests for JobExpiryResult frozen dataclass."""

    def test_result_is_frozen(self) -> None:
        """JobExpiryResult should be immutable."""
        result = check_job_expiry_before(job_status="Discovered")
        with pytest.raises(AttributeError):
            result.can_proceed = False  # type: ignore[misc]

    def test_result_has_all_fields(self) -> None:
        """JobExpiryResult should have all required fields."""
        result = check_job_expiry_before(job_status="Discovered")
        assert hasattr(result, "can_proceed")
        assert hasattr(result, "is_expired")
        assert hasattr(result, "error")
        assert hasattr(result, "suggestion")
        assert hasattr(result, "warning")

    def test_active_result_field_types(self) -> None:
        """Active job result should have correct field types."""
        result = check_job_expiry_before(job_status="Discovered")
        assert isinstance(result.can_proceed, bool)
        assert isinstance(result.is_expired, bool)
        assert result.error is None
        assert result.suggestion is None
        assert result.warning is None

    def test_expired_before_result_field_types(self) -> None:
        """Expired pre-generation result should have string error and suggestion."""
        result = check_job_expiry_before(job_status="Expired")
        assert isinstance(result.can_proceed, bool)
        assert isinstance(result.is_expired, bool)
        assert isinstance(result.error, str)
        assert isinstance(result.suggestion, str)


# =============================================================================
# check_job_expiry_before — Active Statuses
# =============================================================================


class TestCheckJobExpiryBeforeActive:
    """REQ-010 §8.2: Pre-generation check for non-expired statuses."""

    def test_discovered_can_proceed(self) -> None:
        """Discovered status should allow generation."""
        result = check_job_expiry_before(job_status="Discovered")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_dismissed_can_proceed(self) -> None:
        """Dismissed status should allow generation."""
        result = check_job_expiry_before(job_status="Dismissed")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_applied_can_proceed(self) -> None:
        """Applied status should allow generation."""
        result = check_job_expiry_before(job_status="Applied")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_active_has_no_error(self) -> None:
        """Active statuses should produce no error."""
        result = check_job_expiry_before(job_status="Discovered")
        assert result.error is None

    def test_active_has_no_suggestion(self) -> None:
        """Active statuses should produce no suggestion."""
        result = check_job_expiry_before(job_status="Discovered")
        assert result.suggestion is None

    def test_active_has_no_warning(self) -> None:
        """Active statuses should produce no warning."""
        result = check_job_expiry_before(job_status="Applied")
        assert result.warning is None


# =============================================================================
# check_job_expiry_before — Expired Status
# =============================================================================


class TestCheckJobExpiryBeforeExpired:
    """REQ-010 §8.2: Pre-generation check blocks expired jobs."""

    def test_expired_cannot_proceed(self) -> None:
        """Expired status should block generation."""
        result = check_job_expiry_before(job_status="Expired")
        assert result.can_proceed is False

    def test_expired_is_flagged(self) -> None:
        """Expired status should set is_expired=True."""
        result = check_job_expiry_before(job_status="Expired")
        assert result.is_expired is True

    def test_expired_has_error_message(self) -> None:
        """Expired should return the spec-defined error message."""
        result = check_job_expiry_before(job_status="Expired")
        assert result.error == "Job posting has expired"

    def test_expired_has_suggestion(self) -> None:
        """Expired should return the spec-defined suggestion."""
        result = check_job_expiry_before(job_status="Expired")
        assert result.suggestion == "Search for similar active postings?"

    def test_expired_has_no_warning(self) -> None:
        """Pre-generation expired should not have a warning (it's an error)."""
        result = check_job_expiry_before(job_status="Expired")
        assert result.warning is None


# =============================================================================
# check_job_expiry_after — Active Statuses
# =============================================================================


class TestCheckJobExpiryAfterActive:
    """REQ-010 §8.2: Post-generation check for non-expired statuses."""

    def test_discovered_can_proceed(self) -> None:
        """Discovered status after generation should proceed normally."""
        result = check_job_expiry_after(job_status="Discovered")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_dismissed_can_proceed(self) -> None:
        """Dismissed status after generation should proceed normally."""
        result = check_job_expiry_after(job_status="Dismissed")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_applied_can_proceed(self) -> None:
        """Applied status after generation should proceed normally."""
        result = check_job_expiry_after(job_status="Applied")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_active_has_no_warning(self) -> None:
        """Active statuses should produce no warning post-generation."""
        result = check_job_expiry_after(job_status="Discovered")
        assert result.warning is None

    def test_active_has_no_error(self) -> None:
        """Active statuses should produce no error post-generation."""
        result = check_job_expiry_after(job_status="Applied")
        assert result.error is None

    def test_active_has_no_suggestion(self) -> None:
        """Active statuses should produce no suggestion post-generation."""
        result = check_job_expiry_after(job_status="Dismissed")
        assert result.suggestion is None


# =============================================================================
# check_job_expiry_after — Expired Status
# =============================================================================


class TestCheckJobExpiryAfterExpired:
    """REQ-010 §8.2: Post-generation check preserves content + warns."""

    def test_expired_can_still_proceed(self) -> None:
        """Expired mid-generation should still allow proceeding (content preserved)."""
        result = check_job_expiry_after(job_status="Expired")
        assert result.can_proceed is True

    def test_expired_is_flagged(self) -> None:
        """Expired status should set is_expired=True."""
        result = check_job_expiry_after(job_status="Expired")
        assert result.is_expired is True

    def test_expired_has_warning(self) -> None:
        """Expired mid-generation should include the spec-defined warning."""
        result = check_job_expiry_after(job_status="Expired")
        assert result.warning == (
            "Note: This job posting may no longer be active. "
            "Materials saved in case you have an alternative application path."
        )

    def test_expired_has_no_error(self) -> None:
        """Post-generation expired should not be an error (content preserved)."""
        result = check_job_expiry_after(job_status="Expired")
        assert result.error is None

    def test_expired_has_no_suggestion(self) -> None:
        """Post-generation expired should not have a suggestion."""
        result = check_job_expiry_after(job_status="Expired")
        assert result.suggestion is None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case handling for job expiry checks."""

    def test_before_unknown_status_can_proceed(self) -> None:
        """Unknown status should allow generation (fail open for before check)."""
        result = check_job_expiry_before(job_status="Unknown")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_after_unknown_status_can_proceed(self) -> None:
        """Unknown status post-generation should proceed normally."""
        result = check_job_expiry_after(job_status="Unknown")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_before_case_sensitive_expired(self) -> None:
        """Expiry check should be case-sensitive (DB stores exact case)."""
        result = check_job_expiry_before(job_status="expired")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_after_case_sensitive_expired(self) -> None:
        """Post-generation expiry check should be case-sensitive."""
        result = check_job_expiry_after(job_status="EXPIRED")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_before_empty_string_can_proceed(self) -> None:
        """Empty string status should allow generation (fail open)."""
        result = check_job_expiry_before(job_status="")
        assert result.can_proceed is True
        assert result.is_expired is False

    def test_before_blocks_but_after_allows_for_expired(self) -> None:
        """Pre-generation blocks expired, post-generation preserves content."""
        before = check_job_expiry_before(job_status="Expired")
        after = check_job_expiry_after(job_status="Expired")
        assert before.can_proceed is False
        assert after.can_proceed is True
