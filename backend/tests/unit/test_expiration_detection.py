"""Tests for expiration detection service.

REQ-003 §12.2: Expiration Detection.

Tests cover:
- Deadline-based expiration detection
- URL verification (404/gone detection)
- User manual expiration marking
- Verification scheduling (daily for 2 weeks, weekly after)
- Agent communication message generation
"""

from datetime import UTC, datetime, timedelta

from app.services.expiration_detection import (
    ExpirationDetectionResult,
    ExpirationMethod,
    VerificationSchedule,
    check_deadline_expired,
    generate_expiration_message,
    get_verification_schedule,
    needs_verification,
)

# =============================================================================
# Deadline-Based Expiration Tests (REQ-003 §12.2)
# =============================================================================


class TestCheckDeadlineExpired:
    """Tests for check_deadline_expired() function."""

    def test_deadline_passed_returns_expired(self) -> None:
        """Job with past deadline should be detected as expired."""
        # WHY UTC: Implementation uses datetime.now(UTC).date() for consistency.
        today_utc = datetime.now(UTC).date()
        yesterday = today_utc - timedelta(days=1)

        result = check_deadline_expired(application_deadline=yesterday)

        assert result is True

    def test_deadline_today_not_expired(self) -> None:
        """Job with deadline today is NOT expired (still time to apply)."""
        # WHY UTC: Implementation uses datetime.now(UTC).date() for consistency.
        today_utc = datetime.now(UTC).date()

        result = check_deadline_expired(application_deadline=today_utc)

        assert result is False

    def test_deadline_future_not_expired(self) -> None:
        """Job with future deadline is not expired."""
        # WHY UTC: Implementation uses datetime.now(UTC).date() for consistency.
        today_utc = datetime.now(UTC).date()
        tomorrow = today_utc + timedelta(days=1)

        result = check_deadline_expired(application_deadline=tomorrow)

        assert result is False

    def test_no_deadline_not_expired(self) -> None:
        """Job without deadline is not considered expired by this check."""
        result = check_deadline_expired(application_deadline=None)

        assert result is False


# =============================================================================
# Verification Schedule Tests (REQ-003 §12.2)
# =============================================================================


class TestGetVerificationSchedule:
    """Tests for get_verification_schedule() function.

    REQ-003 §12.2: Daily for first 2 weeks, weekly after.
    """

    def test_first_day_is_daily(self) -> None:
        """Day 1 after application should use daily schedule."""
        applied_at = datetime.now(UTC) - timedelta(days=1)

        schedule = get_verification_schedule(applied_at)

        assert schedule == VerificationSchedule.DAILY

    def test_day_13_is_daily(self) -> None:
        """Day 13 (within 2 weeks) should use daily schedule."""
        applied_at = datetime.now(UTC) - timedelta(days=13)

        schedule = get_verification_schedule(applied_at)

        assert schedule == VerificationSchedule.DAILY

    def test_day_14_is_daily(self) -> None:
        """Day 14 (exactly 2 weeks) should still use daily schedule."""
        applied_at = datetime.now(UTC) - timedelta(days=14)

        schedule = get_verification_schedule(applied_at)

        assert schedule == VerificationSchedule.DAILY

    def test_day_15_is_weekly(self) -> None:
        """Day 15 (past 2 weeks) should use weekly schedule."""
        applied_at = datetime.now(UTC) - timedelta(days=15)

        schedule = get_verification_schedule(applied_at)

        assert schedule == VerificationSchedule.WEEKLY

    def test_day_30_is_weekly(self) -> None:
        """Day 30 should use weekly schedule."""
        applied_at = datetime.now(UTC) - timedelta(days=30)

        schedule = get_verification_schedule(applied_at)

        assert schedule == VerificationSchedule.WEEKLY


class TestNeedsVerification:
    """Tests for needs_verification() function.

    Determines if a job needs verification based on schedule and last_verified_at.
    """

    def test_never_verified_needs_verification(self) -> None:
        """Job that was never verified needs verification."""
        applied_at = datetime.now(UTC) - timedelta(days=1)

        result = needs_verification(
            applied_at=applied_at,
            last_verified_at=None,
        )

        assert result is True

    def test_daily_schedule_verified_today_no_need(self) -> None:
        """Daily schedule: verified today does NOT need verification."""
        applied_at = datetime.now(UTC) - timedelta(days=5)
        last_verified = datetime.now(UTC) - timedelta(hours=12)

        result = needs_verification(
            applied_at=applied_at,
            last_verified_at=last_verified,
        )

        assert result is False

    def test_daily_schedule_verified_yesterday_needs_verification(self) -> None:
        """Daily schedule: verified yesterday needs verification."""
        applied_at = datetime.now(UTC) - timedelta(days=5)
        last_verified = datetime.now(UTC) - timedelta(days=1, hours=1)

        result = needs_verification(
            applied_at=applied_at,
            last_verified_at=last_verified,
        )

        assert result is True

    def test_weekly_schedule_verified_3_days_ago_no_need(self) -> None:
        """Weekly schedule: verified 3 days ago does NOT need verification."""
        applied_at = datetime.now(UTC) - timedelta(days=20)
        last_verified = datetime.now(UTC) - timedelta(days=3)

        result = needs_verification(
            applied_at=applied_at,
            last_verified_at=last_verified,
        )

        assert result is False

    def test_weekly_schedule_verified_8_days_ago_needs_verification(self) -> None:
        """Weekly schedule: verified 8 days ago needs verification."""
        applied_at = datetime.now(UTC) - timedelta(days=20)
        last_verified = datetime.now(UTC) - timedelta(days=8)

        result = needs_verification(
            applied_at=applied_at,
            last_verified_at=last_verified,
        )

        assert result is True


# =============================================================================
# Expiration Detection Result Tests
# =============================================================================


class TestExpirationDetectionResult:
    """Tests for ExpirationDetectionResult dataclass."""

    def test_deadline_expired_result(self) -> None:
        """Result for deadline-based expiration."""
        result = ExpirationDetectionResult(
            is_expired=True,
            method=ExpirationMethod.DEADLINE_PASSED,
            job_title="Software Engineer",
            company_name="Acme Corp",
        )

        assert result.is_expired is True
        assert result.method == ExpirationMethod.DEADLINE_PASSED
        assert result.job_title == "Software Engineer"
        assert result.company_name == "Acme Corp"

    def test_url_check_expired_result(self) -> None:
        """Result for URL 404 detection."""
        result = ExpirationDetectionResult(
            is_expired=True,
            method=ExpirationMethod.URL_NOT_FOUND,
            job_title="Data Analyst",
            company_name="TechCo",
        )

        assert result.is_expired is True
        assert result.method == ExpirationMethod.URL_NOT_FOUND

    def test_user_reported_result(self) -> None:
        """Result for user-reported expiration."""
        result = ExpirationDetectionResult(
            is_expired=True,
            method=ExpirationMethod.USER_REPORTED,
            job_title="Product Manager",
            company_name="StartupXYZ",
        )

        assert result.is_expired is True
        assert result.method == ExpirationMethod.USER_REPORTED

    def test_not_expired_result(self) -> None:
        """Result when job is not expired."""
        result = ExpirationDetectionResult(
            is_expired=False,
            method=None,
            job_title="Designer",
            company_name="DesignCo",
        )

        assert result.is_expired is False
        assert result.method is None


# =============================================================================
# Agent Communication Message Tests (REQ-003 §12.2)
# =============================================================================


class TestGenerateExpirationMessage:
    """Tests for generate_expiration_message() function.

    REQ-003 §12.2 example:
    "Heads up — the Scrum Master role at Acme Corp appears to have been taken down.
     I've marked it as expired."
    """

    def test_url_not_found_message(self) -> None:
        """Message for URL 404 detection mentions 'taken down'."""
        result = ExpirationDetectionResult(
            is_expired=True,
            method=ExpirationMethod.URL_NOT_FOUND,
            job_title="Scrum Master",
            company_name="Acme Corp",
        )

        message = generate_expiration_message(result)

        assert "Scrum Master" in message
        assert "Acme Corp" in message
        assert (
            "taken down" in message.lower() or "no longer available" in message.lower()
        )
        assert "expired" in message.lower()

    def test_deadline_passed_message(self) -> None:
        """Message for deadline expiration mentions the deadline."""
        result = ExpirationDetectionResult(
            is_expired=True,
            method=ExpirationMethod.DEADLINE_PASSED,
            job_title="Data Engineer",
            company_name="DataCorp",
        )

        message = generate_expiration_message(result)

        assert "Data Engineer" in message
        assert "DataCorp" in message
        assert "deadline" in message.lower()
        assert "expired" in message.lower()

    def test_user_reported_message(self) -> None:
        """Message for user-reported expiration acknowledges user action."""
        result = ExpirationDetectionResult(
            is_expired=True,
            method=ExpirationMethod.USER_REPORTED,
            job_title="Frontend Developer",
            company_name="WebCo",
        )

        message = generate_expiration_message(result)

        assert "Frontend Developer" in message
        assert "WebCo" in message
        assert "marked" in message.lower() or "reported" in message.lower()

    def test_not_expired_returns_empty(self) -> None:
        """No message generated for non-expired jobs."""
        result = ExpirationDetectionResult(
            is_expired=False,
            method=None,
            job_title="Designer",
            company_name="DesignCo",
        )

        message = generate_expiration_message(result)

        assert message == ""
