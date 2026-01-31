"""Tests for user review service.

REQ-003 §13.2: User Review Flow.

User actions on Discovered jobs:
- Dismiss: status = "Dismissed", dismissed_at = now()
- Favorite: is_favorite = true (independent flag)
- Apply: status = "Applied", Application record created
- Ignore: No change (stays Discovered)
"""

from datetime import UTC, datetime

from app.services.job_status import JobPostingStatus
from app.services.user_review import (
    ApplyResult,
    DismissResult,
    FavoriteResult,
    ReviewAction,
    apply_to_job,
    dismiss_job,
    get_review_action_from_string,
    toggle_favorite,
)

# =============================================================================
# Review Action Enum Tests
# =============================================================================


class TestReviewAction:
    """Tests for ReviewAction enum."""

    def test_all_actions_defined(self) -> None:
        """All user review actions from REQ-003 §13.2 are defined."""
        assert ReviewAction.DISMISS is not None
        assert ReviewAction.FAVORITE is not None
        assert ReviewAction.APPLY is not None

    def test_action_values(self) -> None:
        """Action values match expected strings."""
        assert ReviewAction.DISMISS.value == "dismiss"
        assert ReviewAction.FAVORITE.value == "favorite"
        assert ReviewAction.APPLY.value == "apply"


class TestGetReviewActionFromString:
    """Tests for get_review_action_from_string function."""

    def test_parse_dismiss(self) -> None:
        """Parses 'dismiss' string to DISMISS action."""
        action = get_review_action_from_string("dismiss")
        assert action == ReviewAction.DISMISS

    def test_parse_favorite(self) -> None:
        """Parses 'favorite' string to FAVORITE action."""
        action = get_review_action_from_string("favorite")
        assert action == ReviewAction.FAVORITE

    def test_parse_apply(self) -> None:
        """Parses 'apply' string to APPLY action."""
        action = get_review_action_from_string("apply")
        assert action == ReviewAction.APPLY

    def test_parse_case_insensitive(self) -> None:
        """Parsing is case-insensitive."""
        assert get_review_action_from_string("DISMISS") == ReviewAction.DISMISS
        assert get_review_action_from_string("Favorite") == ReviewAction.FAVORITE
        assert get_review_action_from_string("APPLY") == ReviewAction.APPLY

    def test_invalid_action_returns_none(self) -> None:
        """Returns None for invalid action strings."""
        assert get_review_action_from_string("invalid") is None
        assert get_review_action_from_string("ignore") is None  # Ignore is implicit
        assert get_review_action_from_string("") is None


# =============================================================================
# Dismiss Action Tests (REQ-003 §13.2)
# =============================================================================


class TestDismissResult:
    """Tests for DismissResult dataclass."""

    def test_successful_dismiss_result(self) -> None:
        """DismissResult captures successful dismissal."""
        now = datetime.now(UTC)
        result = DismissResult(
            success=True,
            new_status=JobPostingStatus.DISMISSED,
            dismissed_at=now,
            error=None,
        )

        assert result.success is True
        assert result.new_status == JobPostingStatus.DISMISSED
        assert result.dismissed_at == now
        assert result.error is None

    def test_failed_dismiss_result(self) -> None:
        """DismissResult captures failed dismissal."""
        result = DismissResult(
            success=False,
            new_status=None,
            dismissed_at=None,
            error="Job already dismissed",
        )

        assert result.success is False
        assert result.new_status is None
        assert result.error == "Job already dismissed"


class TestDismissJob:
    """Tests for dismiss_job function."""

    def test_dismiss_discovered_job(self) -> None:
        """Dismissing a Discovered job succeeds."""
        result = dismiss_job(current_status=JobPostingStatus.DISCOVERED)

        assert result.success is True
        assert result.new_status == JobPostingStatus.DISMISSED
        assert result.dismissed_at is not None
        assert result.error is None

    def test_dismiss_sets_timestamp(self) -> None:
        """Dismissing sets dismissed_at to current UTC time."""
        before = datetime.now(UTC)
        result = dismiss_job(current_status=JobPostingStatus.DISCOVERED)
        after = datetime.now(UTC)

        assert result.dismissed_at is not None
        assert before <= result.dismissed_at <= after

    def test_cannot_dismiss_already_dismissed(self) -> None:
        """Cannot dismiss a job that's already Dismissed."""
        result = dismiss_job(current_status=JobPostingStatus.DISMISSED)

        assert result.success is False
        assert result.new_status is None
        assert result.error is not None
        assert "already" in result.error.lower() or "invalid" in result.error.lower()

    def test_cannot_dismiss_applied_job(self) -> None:
        """Cannot dismiss a job that's Applied."""
        result = dismiss_job(current_status=JobPostingStatus.APPLIED)

        assert result.success is False
        assert result.error is not None

    def test_cannot_dismiss_expired_job(self) -> None:
        """Cannot dismiss a job that's Expired."""
        result = dismiss_job(current_status=JobPostingStatus.EXPIRED)

        assert result.success is False
        assert result.error is not None


# =============================================================================
# Favorite Action Tests (REQ-003 §13.2)
# =============================================================================


class TestFavoriteResult:
    """Tests for FavoriteResult dataclass."""

    def test_successful_favorite_result(self) -> None:
        """FavoriteResult captures successful favoriting."""
        result = FavoriteResult(
            success=True,
            is_favorite=True,
            error=None,
        )

        assert result.success is True
        assert result.is_favorite is True
        assert result.error is None

    def test_unfavorite_result(self) -> None:
        """FavoriteResult captures unfavoriting."""
        result = FavoriteResult(
            success=True,
            is_favorite=False,
            error=None,
        )

        assert result.success is True
        assert result.is_favorite is False


class TestToggleFavorite:
    """Tests for toggle_favorite function.

    REQ-003 §13.2: Favorite is independent of status.
    REQ-003 §12.1: Favorited jobs are excluded from auto-archive.
    """

    def test_favorite_discovered_job(self) -> None:
        """Can favorite a Discovered job."""
        result = toggle_favorite(
            current_status=JobPostingStatus.DISCOVERED,
            current_is_favorite=False,
            set_favorite=True,
        )

        assert result.success is True
        assert result.is_favorite is True

    def test_unfavorite_discovered_job(self) -> None:
        """Can unfavorite a Discovered job."""
        result = toggle_favorite(
            current_status=JobPostingStatus.DISCOVERED,
            current_is_favorite=True,
            set_favorite=False,
        )

        assert result.success is True
        assert result.is_favorite is False

    def test_favorite_dismissed_job(self) -> None:
        """Can favorite a Dismissed job (independent of status)."""
        result = toggle_favorite(
            current_status=JobPostingStatus.DISMISSED,
            current_is_favorite=False,
            set_favorite=True,
        )

        assert result.success is True
        assert result.is_favorite is True

    def test_favorite_applied_job(self) -> None:
        """Can favorite an Applied job (independent of status)."""
        result = toggle_favorite(
            current_status=JobPostingStatus.APPLIED,
            current_is_favorite=False,
            set_favorite=True,
        )

        assert result.success is True
        assert result.is_favorite is True

    def test_favorite_expired_job(self) -> None:
        """Can favorite an Expired job (independent of status)."""
        result = toggle_favorite(
            current_status=JobPostingStatus.EXPIRED,
            current_is_favorite=False,
            set_favorite=True,
        )

        assert result.success is True
        assert result.is_favorite is True

    def test_favorite_already_favorited_is_idempotent(self) -> None:
        """Favoriting an already favorited job succeeds (idempotent)."""
        result = toggle_favorite(
            current_status=JobPostingStatus.DISCOVERED,
            current_is_favorite=True,
            set_favorite=True,
        )

        assert result.success is True
        assert result.is_favorite is True


# =============================================================================
# Apply Action Tests (REQ-003 §13.2)
# =============================================================================


class TestApplyResult:
    """Tests for ApplyResult dataclass."""

    def test_successful_apply_result(self) -> None:
        """ApplyResult captures successful application."""
        now = datetime.now(UTC)
        result = ApplyResult(
            success=True,
            new_status=JobPostingStatus.APPLIED,
            applied_at=now,
            error=None,
        )

        assert result.success is True
        assert result.new_status == JobPostingStatus.APPLIED
        assert result.applied_at == now
        assert result.error is None

    def test_failed_apply_result(self) -> None:
        """ApplyResult captures failed application."""
        result = ApplyResult(
            success=False,
            new_status=None,
            applied_at=None,
            error="Already applied",
        )

        assert result.success is False
        assert result.error == "Already applied"


class TestApplyToJob:
    """Tests for apply_to_job function."""

    def test_apply_to_discovered_job(self) -> None:
        """Applying to a Discovered job succeeds."""
        result = apply_to_job(current_status=JobPostingStatus.DISCOVERED)

        assert result.success is True
        assert result.new_status == JobPostingStatus.APPLIED
        assert result.applied_at is not None
        assert result.error is None

    def test_apply_sets_timestamp(self) -> None:
        """Applying sets applied_at to current UTC time."""
        before = datetime.now(UTC)
        result = apply_to_job(current_status=JobPostingStatus.DISCOVERED)
        after = datetime.now(UTC)

        assert result.applied_at is not None
        assert before <= result.applied_at <= after

    def test_cannot_apply_to_dismissed_job(self) -> None:
        """Cannot apply to a Dismissed job."""
        result = apply_to_job(current_status=JobPostingStatus.DISMISSED)

        assert result.success is False
        assert result.error is not None

    def test_cannot_apply_to_already_applied(self) -> None:
        """Cannot apply to a job that's already Applied."""
        result = apply_to_job(current_status=JobPostingStatus.APPLIED)

        assert result.success is False
        assert result.error is not None
        assert "already" in result.error.lower()

    def test_cannot_apply_to_expired_job(self) -> None:
        """Cannot apply to an Expired job."""
        result = apply_to_job(current_status=JobPostingStatus.EXPIRED)

        assert result.success is False
        assert result.error is not None
