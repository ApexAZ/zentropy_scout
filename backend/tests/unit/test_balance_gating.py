"""Tests for InsufficientBalanceError and require_sufficient_balance dependency.

REQ-020 §7.1-§7.4: Balance gating for LLM-triggering endpoints.
REQ-030 §6.1: Available balance = balance_usd - held_balance_usd.
Raises 402 Payment Required when user has insufficient balance.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_sufficient_balance
from app.core.errors import InsufficientBalanceError
from app.models import User

TEST_USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_TEST_EMAIL = "test-gating@example.com"
_ZERO_BALANCE = Decimal("0.000000")
_FIVE_DOLLARS = Decimal("5.000000")
_CUSTOM_THRESHOLD = 0.05
_CUSTOM_THRESHOLD_DECIMAL = Decimal("0.050000")
_SETTINGS_PATCH = "app.api.deps.settings"


async def _create_test_user(
    db: AsyncSession,
    balance: Decimal,
    user_id: uuid.UUID = TEST_USER_ID,
    held: Decimal = _ZERO_BALANCE,
) -> User:
    """Insert a user with a specific balance for gating tests.

    Args:
        db: Database session.
        balance: Initial balance_usd value.
        user_id: User UUID (defaults to TEST_USER_ID).
        held: Initial held_balance_usd value (defaults to 0).

    Returns:
        The created User instance.
    """
    user = User(
        id=user_id, email=_TEST_EMAIL, balance_usd=balance, held_balance_usd=held
    )
    db.add(user)
    await db.commit()
    return user


# =============================================================================
# InsufficientBalanceError — error class
# =============================================================================


class TestInsufficientBalanceError:
    """InsufficientBalanceError has correct code, status, message, details."""

    def test_status_code_is_402(self) -> None:
        """HTTP status code is 402 Payment Required."""
        error = InsufficientBalanceError(
            balance=_ZERO_BALANCE,
            minimum_required=_ZERO_BALANCE,
        )
        assert error.status_code == 402

    def test_code_is_insufficient_balance(self) -> None:
        """Error code matches REQ-020 §7.2."""
        error = InsufficientBalanceError(
            balance=_ZERO_BALANCE,
            minimum_required=_ZERO_BALANCE,
        )
        assert error.code == "INSUFFICIENT_BALANCE"

    def test_message_formats_balance_two_decimals(self) -> None:
        """Message includes balance formatted to 2 decimal places."""
        error = InsufficientBalanceError(
            balance=Decimal("1.234567"),
            minimum_required=_ZERO_BALANCE,
        )
        assert "$1.23" in error.message
        assert "add funds" in error.message.lower()

    def test_message_formats_zero_balance(self) -> None:
        """Message shows $0.00 for zero balance."""
        error = InsufficientBalanceError(
            balance=_ZERO_BALANCE,
            minimum_required=_ZERO_BALANCE,
        )
        assert "$0.00" in error.message

    def test_details_include_balance_usd(self) -> None:
        """Details contain balance_usd as 6-decimal-place string."""
        error = InsufficientBalanceError(
            balance=Decimal("0.123456"),
            minimum_required=_ZERO_BALANCE,
        )
        assert error.details is not None
        assert error.details[0]["balance_usd"] == "0.123456"

    def test_details_include_minimum_required(self) -> None:
        """Details contain minimum_required as 6-decimal-place string."""
        error = InsufficientBalanceError(
            balance=_ZERO_BALANCE,
            minimum_required=_CUSTOM_THRESHOLD_DECIMAL,
        )
        assert error.details is not None
        assert error.details[0]["minimum_required"] == "0.050000"

    def test_caught_by_api_error_handler(self) -> None:
        """Can be caught as APIError — required for api_error_handler in main.py."""
        from app.core.errors import APIError

        with pytest.raises(APIError) as exc_info:
            raise InsufficientBalanceError(
                balance=_ZERO_BALANCE,
                minimum_required=_ZERO_BALANCE,
            )
        assert exc_info.value.status_code == 402


# =============================================================================
# require_sufficient_balance — dependency function (DB integration)
# =============================================================================


class TestRequireSufficientBalance:
    """require_sufficient_balance dependency gates LLM access by balance."""

    async def test_allows_when_balance_positive(self, db_session: AsyncSession) -> None:
        """No error raised when user has positive balance."""
        await _create_test_user(db_session, _FIVE_DOLLARS)
        await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_raises_when_balance_zero(self, db_session: AsyncSession) -> None:
        """Raises InsufficientBalanceError when balance is zero."""
        await _create_test_user(db_session, _ZERO_BALANCE)

        with pytest.raises(InsufficientBalanceError) as exc_info:
            await require_sufficient_balance(TEST_USER_ID, db_session)
        assert exc_info.value.status_code == 402

    async def test_raises_when_balance_negative(self, db_session: AsyncSession) -> None:
        """Raises InsufficientBalanceError when balance is negative."""
        await _create_test_user(db_session, Decimal("-1.000000"))

        with pytest.raises(InsufficientBalanceError):
            await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_error_has_correct_response_shape(
        self, db_session: AsyncSession
    ) -> None:
        """Error matches REQ-020 §7.2 response structure."""
        await _create_test_user(db_session, _ZERO_BALANCE)

        with pytest.raises(InsufficientBalanceError) as exc_info:
            await require_sufficient_balance(TEST_USER_ID, db_session)

        error = exc_info.value
        assert error.code == "INSUFFICIENT_BALANCE"
        assert "$0.00" in error.message
        assert error.details is not None
        assert error.details[0]["balance_usd"] == "0.000000"
        assert "minimum_required" in error.details[0]

    async def test_skips_check_when_metering_disabled(
        self, db_session: AsyncSession
    ) -> None:
        """No balance check when metering_enabled=False."""
        await _create_test_user(db_session, _ZERO_BALANCE)

        with patch(_SETTINGS_PATCH) as mock_settings:
            mock_settings.metering_enabled = False
            # Should NOT raise even with zero balance
            await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_custom_threshold_blocks_below(
        self, db_session: AsyncSession
    ) -> None:
        """Balance below custom threshold is blocked."""
        await _create_test_user(db_session, Decimal("0.030000"))

        with patch(_SETTINGS_PATCH) as mock_settings:
            mock_settings.metering_enabled = True
            mock_settings.metering_minimum_balance = _CUSTOM_THRESHOLD

            with pytest.raises(InsufficientBalanceError):
                await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_custom_threshold_allows_above(
        self, db_session: AsyncSession
    ) -> None:
        """Balance above custom threshold is allowed."""
        await _create_test_user(db_session, Decimal("1.000000"))

        with patch(_SETTINGS_PATCH) as mock_settings:
            mock_settings.metering_enabled = True
            mock_settings.metering_minimum_balance = _CUSTOM_THRESHOLD

            await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_custom_threshold_blocks_at_exact(
        self, db_session: AsyncSession
    ) -> None:
        """Balance exactly equal to threshold is blocked (strict >)."""
        await _create_test_user(db_session, _CUSTOM_THRESHOLD_DECIMAL)

        with patch(_SETTINGS_PATCH) as mock_settings:
            mock_settings.metering_enabled = True
            mock_settings.metering_minimum_balance = _CUSTOM_THRESHOLD

            with pytest.raises(InsufficientBalanceError):
                await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_raises_when_user_not_in_db(self, db_session: AsyncSession) -> None:
        """User not in DB is treated as zero balance (fail-safe).

        When get_current_user_id passes a valid JWT for a deleted user,
        require_sufficient_balance defaults to zero balance and blocks
        with 402. This is fail-safe — access is denied.
        """
        missing_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        with pytest.raises(InsufficientBalanceError):
            await require_sufficient_balance(missing_id, db_session)


# =============================================================================
# require_sufficient_balance — held balance (REQ-030 §6.1)
# =============================================================================


class TestRequireSufficientBalanceHeld:
    """REQ-030 §6.1: available = balance_usd - held_balance_usd."""

    async def test_held_balance_reduces_available(
        self, db_session: AsyncSession
    ) -> None:
        """Held balance makes otherwise-sufficient balance insufficient.

        balance=5.00, held=5.00 → available=0.00 → blocks (≤ threshold 0).
        """
        await _create_test_user(db_session, _FIVE_DOLLARS, held=_FIVE_DOLLARS)
        with pytest.raises(InsufficientBalanceError):
            await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_allows_when_available_after_hold(
        self, db_session: AsyncSession
    ) -> None:
        """User passes when balance minus held is still positive.

        balance=10.00, held=3.00 → available=7.00 → passes.
        """
        await _create_test_user(
            db_session, Decimal("10.000000"), held=Decimal("3.000000")
        )
        await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_zero_held_unchanged_from_no_held(
        self, db_session: AsyncSession
    ) -> None:
        """Zero held balance behaves identically to pre-REQ-030 behavior.

        balance=5.00, held=0.00 → available=5.00 → passes.
        """
        await _create_test_user(db_session, _FIVE_DOLLARS, held=_ZERO_BALANCE)
        await require_sufficient_balance(TEST_USER_ID, db_session)

    async def test_error_reports_available_not_total(
        self, db_session: AsyncSession
    ) -> None:
        """InsufficientBalanceError reports available balance, not total.

        REQ-030 §6.1: Users see spendable balance, not gross balance.
        balance=5.00, held=5.00 → available=0.00 → error shows $0.00.
        """
        await _create_test_user(db_session, _FIVE_DOLLARS, held=_FIVE_DOLLARS)
        with pytest.raises(InsufficientBalanceError) as exc_info:
            await require_sufficient_balance(TEST_USER_ID, db_session)
        assert "$0.00" in exc_info.value.message
        assert exc_info.value.details is not None
        assert exc_info.value.details[0]["balance_usd"] == "0.000000"

    async def test_negative_available_clamped_to_zero(
        self, db_session: AsyncSession
    ) -> None:
        """When held exceeds balance, available is clamped to zero.

        balance=1.00, held=3.00 → raw=-2.00 → clamped to 0.00.
        Error shows $0.00, never a negative dollar amount.
        """
        await _create_test_user(
            db_session, Decimal("1.000000"), held=Decimal("3.000000")
        )
        with pytest.raises(InsufficientBalanceError) as exc_info:
            await require_sufficient_balance(TEST_USER_ID, db_session)
        assert "$0.00" in exc_info.value.message
        assert exc_info.value.details is not None
        assert Decimal(exc_info.value.details[0]["balance_usd"]) >= 0

    async def test_held_balance_with_custom_threshold(
        self, db_session: AsyncSession
    ) -> None:
        """Available balance checked against custom threshold.

        balance=1.00, held=0.96 → available=0.04 → below 0.05 threshold.
        """
        await _create_test_user(
            db_session, Decimal("1.000000"), held=Decimal("0.960000")
        )
        with patch(_SETTINGS_PATCH) as mock_settings:
            mock_settings.metering_enabled = True
            mock_settings.metering_minimum_balance = _CUSTOM_THRESHOLD

            with pytest.raises(InsufficientBalanceError):
                await require_sufficient_balance(TEST_USER_ID, db_session)
