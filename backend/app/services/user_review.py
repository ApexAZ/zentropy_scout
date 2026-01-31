"""User review service for job postings.

REQ-003 §13.2: User Review Flow.

Implements user actions on Discovered jobs:
- Dismiss: status = "Dismissed", dismissed_at = now()
- Favorite: is_favorite = true (independent of status)
- Apply: status = "Applied", applied_at = now()
- Ignore: No change (implicit, stays Discovered)

WHY sync functions: These are pure domain logic functions that validate and
prepare state changes. They don't make DB or LLM calls. The caller (repository
or API layer) handles async DB operations after receiving the result.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.services.job_status import (
    InvalidStatusTransitionError,
    JobPostingStatus,
    transition_status,
)

# =============================================================================
# Enums
# =============================================================================


class ReviewAction(Enum):
    """User actions on job postings.

    REQ-003 §13.2: User review actions.

    Note: IGNORE is not included because it's an implicit action (do nothing).
    """

    DISMISS = "dismiss"
    FAVORITE = "favorite"
    APPLY = "apply"


# =============================================================================
# Result Dataclasses
# =============================================================================


@dataclass
class DismissResult:
    """Result of dismissing a job posting.

    Attributes:
        success: Whether the dismiss action succeeded.
        new_status: New status after dismissal (DISMISSED if successful).
        dismissed_at: Timestamp when job was dismissed.
        error: Error message if dismiss failed.
    """

    success: bool
    new_status: JobPostingStatus | None
    dismissed_at: datetime | None
    error: str | None


@dataclass
class FavoriteResult:
    """Result of favoriting/unfavoriting a job posting.

    Attributes:
        success: Whether the favorite action succeeded.
        is_favorite: Current favorite state after action.
        error: Error message if action failed.
    """

    success: bool
    is_favorite: bool
    error: str | None


@dataclass
class ApplyResult:
    """Result of applying to a job posting.

    Attributes:
        success: Whether the apply action succeeded.
        new_status: New status after application (APPLIED if successful).
        applied_at: Timestamp when user applied.
        error: Error message if apply failed.
    """

    success: bool
    new_status: JobPostingStatus | None
    applied_at: datetime | None
    error: str | None


# =============================================================================
# Action Parsing
# =============================================================================


def get_review_action_from_string(action: str) -> ReviewAction | None:
    """Parse a string to a ReviewAction enum.

    Args:
        action: String representation of the action (case-insensitive).

    Returns:
        ReviewAction enum value, or None if invalid.
    """
    action_lower = action.lower()

    for review_action in ReviewAction:
        if review_action.value == action_lower:
            return review_action

    return None


# =============================================================================
# Dismiss Action (REQ-003 §13.2)
# =============================================================================


def dismiss_job(current_status: JobPostingStatus) -> DismissResult:
    """Dismiss a job posting.

    REQ-003 §13.2: Dismiss sets status to "Dismissed" and records dismissed_at.

    Valid transition: Discovered → Dismissed

    Args:
        current_status: Current status of the job posting.

    Returns:
        DismissResult with new status and timestamp, or error if invalid.
    """
    try:
        result = transition_status(
            current=current_status,
            target=JobPostingStatus.DISMISSED,
        )

        return DismissResult(
            success=True,
            new_status=result.new_status,
            dismissed_at=result.dismissed_at,
            error=None,
        )

    except InvalidStatusTransitionError:
        # WHY: Provide user-friendly error message without leaking internal details
        if current_status == JobPostingStatus.DISMISSED:
            error_msg = "Job is already dismissed"
        elif current_status == JobPostingStatus.EXPIRED:
            error_msg = "Cannot dismiss an expired job"
        elif current_status == JobPostingStatus.APPLIED:
            error_msg = "Cannot dismiss a job you've already applied to"
        else:
            error_msg = "Cannot perform this action on the job posting"

        return DismissResult(
            success=False,
            new_status=None,
            dismissed_at=None,
            error=error_msg,
        )


# =============================================================================
# Favorite Action (REQ-003 §13.2)
# =============================================================================


def toggle_favorite(  # noqa: ARG001
    current_status: JobPostingStatus,
    current_is_favorite: bool,
    set_favorite: bool,
) -> FavoriteResult:
    """Toggle favorite status on a job posting.

    REQ-003 §13.2: Favorite is independent of status (can apply to any status).
    REQ-003 §12.1: Favorited jobs are excluded from auto-archive.

    Args:
        current_status: Current status (unused - favorite is status-independent).
        current_is_favorite: Current favorite state (unused - we always set to target).
        set_favorite: Target favorite state.

    Returns:
        FavoriteResult with new favorite state.

    WHY unused params: These parameters exist for API consistency with dismiss_job
    and apply_to_job. Future validation could use them (e.g., warn when favoriting
    expired jobs).
    """
    # WHY: Favorite is independent of status per REQ-003 §13.2
    # Any status can be favorited/unfavorited, so we don't validate status
    del current_status, current_is_favorite  # Explicit unused marker

    return FavoriteResult(
        success=True,
        is_favorite=set_favorite,
        error=None,
    )


# =============================================================================
# Apply Action (REQ-003 §13.2)
# =============================================================================


def apply_to_job(current_status: JobPostingStatus) -> ApplyResult:
    """Apply to a job posting.

    REQ-003 §13.2: Apply sets status to "Applied".
    Note: This also triggers Application record creation (handled by caller).

    Valid transition: Discovered → Applied

    Args:
        current_status: Current status of the job posting.

    Returns:
        ApplyResult with new status and timestamp, or error if invalid.
    """
    try:
        result = transition_status(
            current=current_status,
            target=JobPostingStatus.APPLIED,
        )

        # WHY applied_at here: StatusTransitionResult tracks dismissed_at and expired_at
        # but not applied_at since that's application-domain (REQ-004), not job-status.
        # Setting it here ensures consistent UTC timing with the transition.
        applied_at = datetime.now(UTC)

        return ApplyResult(
            success=True,
            new_status=result.new_status,
            applied_at=applied_at,
            error=None,
        )

    except InvalidStatusTransitionError:
        # WHY: Provide user-friendly error message without leaking internal details
        if current_status == JobPostingStatus.APPLIED:
            error_msg = "Already applied to this job"
        elif current_status == JobPostingStatus.DISMISSED:
            error_msg = "Cannot apply to a dismissed job"
        elif current_status == JobPostingStatus.EXPIRED:
            error_msg = "Cannot apply to an expired job"
        else:
            error_msg = "Cannot perform this action on the job posting"

        return ApplyResult(
            success=False,
            new_status=None,
            applied_at=None,
            error=error_msg,
        )
