"""Tests for job posting status transitions.

REQ-003 §6.1: Status Transitions.

Tests verify:
1. Status enum values match database check constraint
2. Valid transitions are allowed
3. Invalid transitions are rejected
4. Transition timestamps are set
"""

from datetime import datetime

import pytest

from app.services.job_status import (
    InvalidStatusTransitionError,
    JobPostingStatus,
    get_valid_transitions,
    is_valid_transition,
    transition_status,
)

# =============================================================================
# Status Enum Tests
# =============================================================================


class TestJobPostingStatus:
    """Tests for JobPostingStatus enum values.

    REQ-003 §6: Status definitions.
    """

    def test_has_discovered_status_when_enum_defined(self) -> None:
        """Discovered status exists for initial job discovery."""
        assert JobPostingStatus.DISCOVERED.value == "Discovered"

    def test_has_dismissed_status_when_enum_defined(self) -> None:
        """Dismissed status exists for user not interested."""
        assert JobPostingStatus.DISMISSED.value == "Dismissed"

    def test_has_applied_status_when_enum_defined(self) -> None:
        """Applied status exists when application created."""
        assert JobPostingStatus.APPLIED.value == "Applied"

    def test_has_expired_status_when_enum_defined(self) -> None:
        """Expired status exists when job no longer available."""
        assert JobPostingStatus.EXPIRED.value == "Expired"


# =============================================================================
# Valid Transition Tests
# =============================================================================


class TestValidTransitions:
    """Tests for allowed status transitions.

    REQ-003 §6.1: State machine rules.
    """

    def test_allows_discovered_to_dismissed_when_user_dismisses(self) -> None:
        """User can dismiss a discovered job."""
        assert is_valid_transition(
            JobPostingStatus.DISCOVERED, JobPostingStatus.DISMISSED
        )

    def test_allows_discovered_to_applied_when_application_created(self) -> None:
        """User can apply to a discovered job."""
        assert is_valid_transition(
            JobPostingStatus.DISCOVERED, JobPostingStatus.APPLIED
        )

    def test_allows_discovered_to_expired_when_job_taken_down(self) -> None:
        """Discovered job can expire when taken down."""
        assert is_valid_transition(
            JobPostingStatus.DISCOVERED, JobPostingStatus.EXPIRED
        )

    def test_allows_dismissed_to_expired_when_job_taken_down(self) -> None:
        """Dismissed job can still expire when taken down."""
        assert is_valid_transition(JobPostingStatus.DISMISSED, JobPostingStatus.EXPIRED)

    def test_allows_applied_to_expired_when_job_taken_down(self) -> None:
        """Applied job can expire (application continues independently)."""
        assert is_valid_transition(JobPostingStatus.APPLIED, JobPostingStatus.EXPIRED)


# =============================================================================
# Invalid Transition Tests
# =============================================================================


class TestInvalidTransitions:
    """Tests for disallowed status transitions.

    REQ-003 §6.1: One-way transitions only.
    """

    def test_rejects_dismissed_to_discovered_when_reversing(self) -> None:
        """Cannot undo dismissal."""
        assert not is_valid_transition(
            JobPostingStatus.DISMISSED, JobPostingStatus.DISCOVERED
        )

    def test_rejects_dismissed_to_applied_when_already_dismissed(self) -> None:
        """Cannot apply after dismissing."""
        assert not is_valid_transition(
            JobPostingStatus.DISMISSED, JobPostingStatus.APPLIED
        )

    def test_rejects_applied_to_discovered_when_reversing(self) -> None:
        """Cannot un-apply."""
        assert not is_valid_transition(
            JobPostingStatus.APPLIED, JobPostingStatus.DISCOVERED
        )

    def test_rejects_applied_to_dismissed_when_already_applied(self) -> None:
        """Cannot dismiss after applying."""
        assert not is_valid_transition(
            JobPostingStatus.APPLIED, JobPostingStatus.DISMISSED
        )

    def test_rejects_expired_to_any_status_when_terminal(self) -> None:
        """Expired is a terminal state - no transitions out."""
        assert not is_valid_transition(
            JobPostingStatus.EXPIRED, JobPostingStatus.DISCOVERED
        )
        assert not is_valid_transition(
            JobPostingStatus.EXPIRED, JobPostingStatus.DISMISSED
        )
        assert not is_valid_transition(
            JobPostingStatus.EXPIRED, JobPostingStatus.APPLIED
        )

    def test_rejects_same_status_transition_when_no_change(self) -> None:
        """Cannot transition to the same status."""
        assert not is_valid_transition(
            JobPostingStatus.DISCOVERED, JobPostingStatus.DISCOVERED
        )
        assert not is_valid_transition(
            JobPostingStatus.DISMISSED, JobPostingStatus.DISMISSED
        )
        assert not is_valid_transition(
            JobPostingStatus.APPLIED, JobPostingStatus.APPLIED
        )
        assert not is_valid_transition(
            JobPostingStatus.EXPIRED, JobPostingStatus.EXPIRED
        )


# =============================================================================
# Get Valid Transitions Tests
# =============================================================================


class TestGetValidTransitions:
    """Tests for getting valid transitions from a status."""

    def test_returns_three_targets_when_discovered(self) -> None:
        """Discovered can go to Dismissed, Applied, or Expired."""
        valid = get_valid_transitions(JobPostingStatus.DISCOVERED)
        assert len(valid) == 3
        assert JobPostingStatus.DISMISSED in valid
        assert JobPostingStatus.APPLIED in valid
        assert JobPostingStatus.EXPIRED in valid

    def test_returns_one_target_when_dismissed(self) -> None:
        """Dismissed can only go to Expired."""
        valid = get_valid_transitions(JobPostingStatus.DISMISSED)
        assert valid == [JobPostingStatus.EXPIRED]

    def test_returns_one_target_when_applied(self) -> None:
        """Applied can only go to Expired."""
        valid = get_valid_transitions(JobPostingStatus.APPLIED)
        assert valid == [JobPostingStatus.EXPIRED]

    def test_returns_empty_when_expired(self) -> None:
        """Expired is terminal - no valid transitions."""
        valid = get_valid_transitions(JobPostingStatus.EXPIRED)
        assert valid == []


# =============================================================================
# Transition Status Function Tests
# =============================================================================


class TestTransitionStatus:
    """Tests for the transition_status function.

    REQ-003 §6.1: Execute transition with validation.
    """

    def test_returns_new_status_when_valid_transition(self) -> None:
        """Returns target status for valid transition."""
        result = transition_status(
            current=JobPostingStatus.DISCOVERED,
            target=JobPostingStatus.DISMISSED,
        )
        assert result.new_status == JobPostingStatus.DISMISSED

    def test_includes_timestamp_when_transitioning_to_dismissed(self) -> None:
        """Sets dismissed_at timestamp when dismissing."""
        result = transition_status(
            current=JobPostingStatus.DISCOVERED,
            target=JobPostingStatus.DISMISSED,
        )
        assert result.dismissed_at is not None
        assert isinstance(result.dismissed_at, datetime)
        assert result.dismissed_at.tzinfo is not None  # timezone-aware

    def test_includes_timestamp_when_transitioning_to_expired(self) -> None:
        """Sets expired_at timestamp when expiring."""
        result = transition_status(
            current=JobPostingStatus.DISCOVERED,
            target=JobPostingStatus.EXPIRED,
        )
        assert result.expired_at is not None
        assert isinstance(result.expired_at, datetime)
        assert result.expired_at.tzinfo is not None  # timezone-aware

    def test_no_dismissed_timestamp_when_transitioning_to_applied(self) -> None:
        """Applied transition doesn't set dismissed_at."""
        result = transition_status(
            current=JobPostingStatus.DISCOVERED,
            target=JobPostingStatus.APPLIED,
        )
        assert result.dismissed_at is None
        assert result.expired_at is None

    def test_raises_error_when_invalid_transition(self) -> None:
        """Raises InvalidStatusTransitionError for invalid transitions."""
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            transition_status(
                current=JobPostingStatus.DISMISSED,
                target=JobPostingStatus.DISCOVERED,
            )
        assert "Dismissed" in str(exc_info.value)
        assert "Discovered" in str(exc_info.value)

    def test_error_includes_current_and_target_when_invalid(self) -> None:
        """Error message includes both statuses for debugging."""
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            transition_status(
                current=JobPostingStatus.EXPIRED,
                target=JobPostingStatus.APPLIED,
            )
        error = exc_info.value
        assert error.current_status == JobPostingStatus.EXPIRED
        assert error.target_status == JobPostingStatus.APPLIED

    def test_error_includes_valid_transitions_when_invalid(self) -> None:
        """Error message includes what transitions are valid."""
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            transition_status(
                current=JobPostingStatus.DISMISSED,
                target=JobPostingStatus.APPLIED,
            )
        error = exc_info.value
        assert error.valid_transitions == [JobPostingStatus.EXPIRED]


# =============================================================================
# String Conversion Tests
# =============================================================================


class TestStatusStringConversion:
    """Tests for converting between string and enum."""

    def test_parses_string_when_from_string_called(self) -> None:
        """Can convert database string to enum."""
        assert JobPostingStatus.from_string("Discovered") == JobPostingStatus.DISCOVERED
        assert JobPostingStatus.from_string("Dismissed") == JobPostingStatus.DISMISSED
        assert JobPostingStatus.from_string("Applied") == JobPostingStatus.APPLIED
        assert JobPostingStatus.from_string("Expired") == JobPostingStatus.EXPIRED

    def test_raises_error_when_invalid_string(self) -> None:
        """Raises ValueError for unknown status string."""
        with pytest.raises(ValueError, match="Invalid job posting status"):
            JobPostingStatus.from_string("Unknown")

    def test_case_sensitive_when_parsing_string(self) -> None:
        """Status parsing is case-sensitive (matches DB constraint)."""
        with pytest.raises(ValueError, match="Invalid job posting status"):
            JobPostingStatus.from_string("discovered")  # lowercase
