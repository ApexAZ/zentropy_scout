"""Tests for credit Pydantic schemas.

REQ-029 §8.1–§8.3, §13.1: Validates request/response schemas for credit
endpoints — checkout request/response, pack listing, and purchase history.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.credits import (
    CheckoutRequest,
    CheckoutResponse,
    PackResponse,
    PurchaseResponse,
    format_usd_display,
)

# =============================================================================
# Constants
# =============================================================================

_CHECKOUT_URL = "https://checkout.stripe.com/pay/cs_test_123"
_SESSION_ID = "cs_test_123"
_TEST_TIMESTAMP = "2026-03-10T12:00:00Z"


# =============================================================================
# Helpers
# =============================================================================


def _make_pack(**overrides: object) -> PackResponse:
    """Build a PackResponse with sensible defaults."""
    defaults: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "name": "Starter",
        "price_cents": 100,
        "price_display": "$1.00",
        "grant_cents": 100,
        "amount_display": "$1.00",
    }
    defaults.update(overrides)
    return PackResponse(**defaults)


def _make_purchase(**overrides: object) -> PurchaseResponse:
    """Build a PurchaseResponse with sensible defaults."""
    defaults: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "amount_usd": "10.000000",
        "amount_display": "$10.00",
        "transaction_type": "purchase",
        "created_at": _TEST_TIMESTAMP,
    }
    defaults.update(overrides)
    return PurchaseResponse(**defaults)


# =============================================================================
# format_usd_display helper
# =============================================================================


class TestFormatUsdDisplay:
    """format_usd_display converts cents to a formatted USD string."""

    def test_formats_whole_dollars(self) -> None:
        assert format_usd_display(500) == "$5.00"

    def test_formats_cents(self) -> None:
        assert format_usd_display(99) == "$0.99"

    def test_formats_large_amount(self) -> None:
        assert format_usd_display(10000) == "$100.00"

    def test_formats_single_cent(self) -> None:
        assert format_usd_display(1) == "$0.01"

    def test_formats_zero(self) -> None:
        assert format_usd_display(0) == "$0.00"

    def test_formats_negative_amount(self) -> None:
        assert format_usd_display(-500) == "-$5.00"

    def test_formats_negative_cents(self) -> None:
        assert format_usd_display(-1) == "-$0.01"


# =============================================================================
# CheckoutRequest
# =============================================================================


class TestCheckoutRequest:
    """CheckoutRequest accepts a valid pack_id UUID."""

    def test_valid_pack_id(self) -> None:
        pack_id = uuid.uuid4()
        schema = CheckoutRequest(pack_id=pack_id)
        assert schema.pack_id == pack_id

    def test_coerces_uuid_string(self) -> None:
        pack_id = str(uuid.uuid4())
        schema = CheckoutRequest(pack_id=pack_id)  # type: ignore[arg-type]
        assert schema.pack_id == uuid.UUID(pack_id)

    def test_rejects_missing_pack_id(self) -> None:
        with pytest.raises(ValidationError, match="pack_id"):
            CheckoutRequest()  # type: ignore[call-arg]

    def test_rejects_invalid_uuid(self) -> None:
        with pytest.raises(ValidationError, match="pack_id"):
            CheckoutRequest(pack_id="not-a-uuid")  # type: ignore[arg-type]

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            CheckoutRequest(
                pack_id=uuid.uuid4(),
                secret="nope",  # type: ignore[call-arg]
            )


# =============================================================================
# CheckoutResponse
# =============================================================================


class TestCheckoutResponse:
    """CheckoutResponse returns checkout_url and session_id."""

    def test_valid_response(self) -> None:
        schema = CheckoutResponse(
            checkout_url=_CHECKOUT_URL,
            session_id=_SESSION_ID,
        )
        assert schema.checkout_url == _CHECKOUT_URL
        assert schema.session_id == _SESSION_ID

    def test_rejects_missing_checkout_url(self) -> None:
        with pytest.raises(ValidationError, match="checkout_url"):
            CheckoutResponse(session_id=_SESSION_ID)  # type: ignore[call-arg]

    def test_rejects_missing_session_id(self) -> None:
        with pytest.raises(ValidationError, match="session_id"):
            CheckoutResponse(checkout_url=_CHECKOUT_URL)  # type: ignore[call-arg]

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            CheckoutResponse(
                checkout_url=_CHECKOUT_URL,
                session_id=_SESSION_ID,
                secret="nope",  # type: ignore[call-arg]
            )


# =============================================================================
# PackResponse
# =============================================================================


class TestPackResponse:
    """PackResponse serializes funding pack data for the API."""

    def test_valid_pack_with_highlight(self) -> None:
        schema = _make_pack(
            name="Standard",
            price_cents=500,
            price_display="$5.00",
            grant_cents=500,
            amount_display="$5.00",
            description="Standard credit pack",
            highlight_label="Most Popular",
        )
        assert schema.name == "Standard"
        assert schema.price_display == "$5.00"
        assert schema.highlight_label == "Most Popular"

    def test_valid_pack_without_highlight(self) -> None:
        schema = _make_pack(description="Starter pack")
        assert schema.highlight_label is None

    def test_description_optional(self) -> None:
        schema = _make_pack()
        assert schema.description is None

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            _make_pack(secret="nope")


# =============================================================================
# PurchaseResponse
# =============================================================================


class TestPurchaseResponse:
    """PurchaseResponse serializes credit transaction data."""

    def test_valid_purchase(self) -> None:
        schema = _make_purchase(description="Standard Credit Pack")
        assert schema.amount_usd == "10.000000"
        assert schema.amount_display == "$10.00"
        assert schema.transaction_type == "purchase"

    def test_refund_negative_amount(self) -> None:
        schema = _make_purchase(
            amount_usd="-5.000000",
            amount_display="-$5.00",
            transaction_type="refund",
            description="Refund — $5.00",
        )
        assert schema.amount_usd == "-5.000000"
        assert schema.transaction_type == "refund"

    def test_description_optional(self) -> None:
        schema = _make_purchase(transaction_type="signup_grant")
        assert schema.description is None

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError, match="amount_usd"):
            PurchaseResponse(
                id=str(uuid.uuid4()),
                amount_display="$10.00",
                transaction_type="purchase",
                created_at=_TEST_TIMESTAMP,
            )  # type: ignore[call-arg]

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            _make_purchase(secret="nope")
