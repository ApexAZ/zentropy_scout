"""Expiration detection service for job postings.

REQ-003 §12.2: Expiration Detection.

Implements detection methods:
- Deadline passed: application_deadline < today
- URL not found: HTTP 404/gone response
- User reported: Manual marking by user
- API re-query: Periodic verification of Applied jobs

Verification schedule:
- Daily for first 2 weeks after application
- Weekly after 2 weeks
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum

# =============================================================================
# Constants
# =============================================================================


# WHY 14 days: REQ-003 §12.2 specifies "daily for first 2 weeks"
DAILY_VERIFICATION_DAYS = 14

# WHY 1 day: Daily schedule checks once per day
DAILY_INTERVAL = timedelta(days=1)

# WHY 7 days: Weekly schedule checks once per week
WEEKLY_INTERVAL = timedelta(days=7)


# =============================================================================
# Enums
# =============================================================================


class ExpirationMethod(Enum):
    """How the expiration was detected.

    REQ-003 §12.2: Detection methods and their reliability.
    """

    # High reliability - if deadline was specified
    DEADLINE_PASSED = "deadline_passed"

    # Medium reliability - URLs can change
    URL_NOT_FOUND = "url_not_found"

    # High reliability - manual but reliable
    USER_REPORTED = "user_reported"

    # High reliability - if API supports lookup
    API_REQUERY = "api_requery"


class VerificationSchedule(Enum):
    """Verification frequency schedule.

    REQ-003 §12.2: Daily for first 2 weeks, weekly after.
    """

    DAILY = "daily"
    WEEKLY = "weekly"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ExpirationDetectionResult:
    """Result of an expiration detection check.

    Attributes:
        is_expired: Whether the job is expired.
        method: How expiration was detected (None if not expired).
        job_title: Title of the job posting.
        company_name: Name of the company.
    """

    is_expired: bool
    method: ExpirationMethod | None
    job_title: str
    company_name: str


# =============================================================================
# Deadline-Based Detection (REQ-003 §12.2)
# =============================================================================


def check_deadline_expired(application_deadline: date | None) -> bool:
    """Check if a job's application deadline has passed.

    REQ-003 §12.2: "Deadline passed: application_deadline < today"

    The deadline day itself is NOT considered expired - the user still has
    until end of day to apply.

    Args:
        application_deadline: The job's application deadline, or None if not set.

    Returns:
        True if deadline has passed, False otherwise.
    """
    if application_deadline is None:
        return False

    # WHY datetime.now(UTC).date(): Use UTC consistently across all functions
    # in this module to avoid timezone inconsistencies.
    return application_deadline < datetime.now(UTC).date()


# =============================================================================
# Verification Schedule (REQ-003 §12.2)
# =============================================================================


def get_verification_schedule(applied_at: datetime) -> VerificationSchedule:
    """Determine the verification schedule based on when user applied.

    REQ-003 §12.2: "Daily for first 2 weeks, weekly after"

    Args:
        applied_at: When the user applied to this job.

    Returns:
        DAILY if within first 2 weeks, WEEKLY otherwise.
    """
    days_since_applied = (datetime.now(UTC) - applied_at).days

    if days_since_applied <= DAILY_VERIFICATION_DAYS:
        return VerificationSchedule.DAILY
    else:
        return VerificationSchedule.WEEKLY


def needs_verification(
    applied_at: datetime,
    last_verified_at: datetime | None,
) -> bool:
    """Check if a job needs verification based on schedule.

    REQ-003 §12.2: Agent periodically re-verifies Applied jobs.

    Args:
        applied_at: When the user applied to this job.
        last_verified_at: When the job was last verified, or None if never.

    Returns:
        True if verification is needed, False otherwise.
    """
    # Never verified - always needs verification
    if last_verified_at is None:
        return True

    schedule = get_verification_schedule(applied_at)
    interval = (
        DAILY_INTERVAL if schedule == VerificationSchedule.DAILY else WEEKLY_INTERVAL
    )

    time_since_verified = datetime.now(UTC) - last_verified_at

    return time_since_verified >= interval


# =============================================================================
# Agent Communication (REQ-003 §12.2)
# =============================================================================


def generate_expiration_message(result: ExpirationDetectionResult) -> str:
    """Generate user-facing message for expiration detection.

    REQ-003 §12.2 example:
    "Heads up — the Scrum Master role at Acme Corp appears to have been taken down.
     I've marked it as expired."

    Args:
        result: The expiration detection result.

    Returns:
        User-facing message, or empty string if not expired.
    """
    if not result.is_expired:
        return ""

    job_title = result.job_title
    company_name = result.company_name

    if result.method == ExpirationMethod.URL_NOT_FOUND:
        return (
            f"Heads up — the {job_title} role at {company_name} appears to have "
            f"been taken down. I've marked it as expired."
        )
    elif result.method == ExpirationMethod.DEADLINE_PASSED:
        return (
            f"The application deadline for the {job_title} role at {company_name} "
            f"has passed. I've marked it as expired."
        )
    elif result.method == ExpirationMethod.USER_REPORTED:
        return (
            f"Got it — I've marked the {job_title} role at {company_name} as expired "
            f"as you reported."
        )
    elif result.method == ExpirationMethod.API_REQUERY:
        return (
            f"Heads up — the {job_title} role at {company_name} is no longer available "
            f"on the job board. I've marked it as expired."
        )
    else:
        # Fallback for any future methods
        return f"The {job_title} role at {company_name} has expired."
