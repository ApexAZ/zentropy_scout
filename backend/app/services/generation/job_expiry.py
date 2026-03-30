"""Job expiry checks for content generation.

REQ-010 §8.2: Expired Job During Generation.

Two-phase expiry check:
1. Pre-generation: If job status is already "Expired", abort with error + suggestion.
2. Post-generation: If job expired mid-generation, preserve content + add warning.
"""

from dataclasses import dataclass

_EXPIRED_STATUS: str = "Expired"
"""The status value indicating a job posting has expired."""

_VALID_STATUSES: frozenset[str] = frozenset(
    {"Discovered", "Dismissed", "Applied", "Expired"}
)
"""All valid job posting statuses per the DB check constraint."""


@dataclass(frozen=True)
class JobExpiryResult:
    """Result of checking job expiry status for content generation.

    REQ-010 §8.2: Captures the expiry check outcome in a single
    immutable result. Used for both pre- and post-generation checks.

    Attributes:
        can_proceed: False if job is already expired (pre-generation only).
        is_expired: True if the job status is "Expired".
        error: Error message when can_proceed is False.
        suggestion: Actionable suggestion when can_proceed is False.
        warning: Warning message when expired mid-generation (post-generation only).
    """

    can_proceed: bool
    is_expired: bool
    error: str | None
    suggestion: str | None
    warning: str | None


def check_job_expiry_before(*, job_status: str) -> JobExpiryResult:
    """Pre-flight check before starting content generation.

    REQ-010 §8.2: If the job posting is already expired, abort
    generation with an error message and actionable suggestion.

    Unknown statuses are treated as non-expired (fail open). The DB
    check constraint enforces valid statuses upstream.

    Args:
        job_status: Current status of the job posting.

    Returns:
        JobExpiryResult with can_proceed=False if expired.
    """
    is_expired = job_status == _EXPIRED_STATUS
    if is_expired:
        return JobExpiryResult(
            can_proceed=False,
            is_expired=True,
            error="Job posting has expired",
            suggestion="Search for similar active postings?",
            warning=None,
        )
    return JobExpiryResult(
        can_proceed=True,
        is_expired=False,
        error=None,
        suggestion=None,
        warning=None,
    )


def check_job_expiry_after(*, job_status: str) -> JobExpiryResult:
    """Post-generation check after content has been generated.

    REQ-010 §8.2: If the job expired during generation, preserve
    the content and add a warning. The user may have alternative
    application paths (e.g., recruiter contact, saved listing).

    Unknown statuses are treated as non-expired (fail open). The DB
    check constraint enforces valid statuses upstream.

    Args:
        job_status: Refreshed status of the job posting.

    Returns:
        JobExpiryResult with can_proceed=True and warning if expired.
    """
    is_expired = job_status == _EXPIRED_STATUS
    if is_expired:
        return JobExpiryResult(
            can_proceed=True,
            is_expired=True,
            error=None,
            suggestion=None,
            warning=(
                "Note: This job posting may no longer be active. "
                "Materials saved in case you have an alternative "
                "application path."
            ),
        )
    return JobExpiryResult(
        can_proceed=True,
        is_expired=False,
        error=None,
        suggestion=None,
        warning=None,
    )
