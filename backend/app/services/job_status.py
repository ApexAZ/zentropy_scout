"""Job posting status transitions service.

REQ-003 §6.1: Status Transitions.

Implements a state machine for job posting statuses:
- Discovered → Dismissed, Applied, Expired
- Dismissed → Expired
- Applied → Expired
- Expired → (terminal, no transitions)

One-way transitions only. No reversing.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.core.errors import APIError

# =============================================================================
# Exceptions
# =============================================================================


class InvalidStatusTransitionError(APIError):
    """Raised when attempting an invalid status transition.

    REQ-003 §6.1: Only valid transitions are allowed.
    """

    def __init__(
        self,
        current_status: "JobPostingStatus",
        target_status: "JobPostingStatus",
        valid_transitions: list["JobPostingStatus"],
    ) -> None:
        """Initialize with transition details.

        Args:
            current_status: The current status of the job posting.
            target_status: The attempted target status.
            valid_transitions: List of valid target statuses from current.
        """
        self.current_status = current_status
        self.target_status = target_status
        self.valid_transitions = valid_transitions
        valid_names = [s.value for s in valid_transitions]
        super().__init__(
            code="INVALID_STATUS_TRANSITION",
            message=(
                f"Cannot transition from {current_status.value} to {target_status.value}. "
                f"Valid transitions: {valid_names or 'none (terminal state)'}"
            ),
            status_code=422,
        )


# =============================================================================
# Enums
# =============================================================================


class JobPostingStatus(Enum):
    """Job posting status values.

    REQ-003 §6: Status definitions.

    Values match the database check constraint in job_postings table.
    """

    DISCOVERED = "Discovered"
    DISMISSED = "Dismissed"
    APPLIED = "Applied"
    EXPIRED = "Expired"

    @classmethod
    def from_string(cls, value: str) -> "JobPostingStatus":
        """Convert a database string to enum.

        Args:
            value: Status string from database.

        Returns:
            The corresponding JobPostingStatus enum value.

        Raises:
            ValueError: If the string doesn't match any status.
        """
        for status in cls:
            if status.value == value:
                return status
        valid = [s.value for s in cls]
        raise ValueError(f"Invalid job posting status: '{value}'. Valid: {valid}")


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class StatusTransitionResult:
    """Result of a status transition.

    REQ-003 §6.1: Includes timestamps for tracking when transitions occurred.

    Attributes:
        new_status: The status after transition.
        dismissed_at: Timestamp when dismissed (if transitioning to Dismissed).
        expired_at: Timestamp when expired (if transitioning to Expired).
    """

    new_status: JobPostingStatus
    dismissed_at: datetime | None = None
    expired_at: datetime | None = None


# =============================================================================
# State Machine Definition
# =============================================================================


# WHY dict[JobPostingStatus, list[JobPostingStatus]]: This defines valid transitions
# from each status. Keys are current status, values are list of valid targets.
# Expired has empty list because it's a terminal state.
_VALID_TRANSITIONS: dict[JobPostingStatus, list[JobPostingStatus]] = {
    JobPostingStatus.DISCOVERED: [
        JobPostingStatus.DISMISSED,
        JobPostingStatus.APPLIED,
        JobPostingStatus.EXPIRED,
    ],
    JobPostingStatus.DISMISSED: [
        JobPostingStatus.EXPIRED,
    ],
    JobPostingStatus.APPLIED: [
        JobPostingStatus.EXPIRED,
    ],
    JobPostingStatus.EXPIRED: [],  # Terminal state
}


# =============================================================================
# Public Functions
# =============================================================================


def is_valid_transition(
    current: JobPostingStatus,
    target: JobPostingStatus,
) -> bool:
    """Check if a status transition is valid.

    REQ-003 §6.1: One-way transitions only.

    Args:
        current: The current status of the job posting.
        target: The desired target status.

    Returns:
        True if the transition is allowed, False otherwise.
    """
    valid_targets = _VALID_TRANSITIONS.get(current, [])
    return target in valid_targets


def get_valid_transitions(status: JobPostingStatus) -> list[JobPostingStatus]:
    """Get valid target statuses from current status.

    Args:
        status: The current status.

    Returns:
        List of statuses that can be transitioned to.
    """
    return _VALID_TRANSITIONS.get(status, [])


def transition_status(
    current: JobPostingStatus,
    target: JobPostingStatus,
) -> StatusTransitionResult:
    """Execute a status transition with validation.

    REQ-003 §6.1: Validates transition and sets appropriate timestamps.

    Args:
        current: The current status of the job posting.
        target: The desired target status.

    Returns:
        StatusTransitionResult with new status and timestamps.

    Raises:
        InvalidStatusTransitionError: If the transition is not allowed.
    """
    if not is_valid_transition(current, target):
        raise InvalidStatusTransitionError(
            current_status=current,
            target_status=target,
            valid_transitions=get_valid_transitions(current),
        )

    now = datetime.now(UTC)

    dismissed_at = now if target == JobPostingStatus.DISMISSED else None
    expired_at = now if target == JobPostingStatus.EXPIRED else None

    return StatusTransitionResult(
        new_status=target,
        dismissed_at=dismissed_at,
        expired_at=expired_at,
    )
