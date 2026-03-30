"""Add response metadata columns for settlement retry.

Revision ID: 029_settlement_retry
Revises: 028_billing_hardening
Create Date: 2026-03-29

REQ-030 §5.8: Adds 4 nullable columns to usage_reservations for the
outbox pattern — persists LLM response metadata on the reservation row
so the background sweep can retry settlement on failed-but-completed calls.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "029_settlement_retry"
down_revision: str = "028_billing_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USAGE_RESERVATIONS = "usage_reservations"
_CK_RESP_INPUT = "ck_reservation_resp_input_tokens_nonneg"
_CK_RESP_OUTPUT = "ck_reservation_resp_output_tokens_nonneg"
_CK_RESP_COMPLETE = "ck_reservation_response_metadata_complete"


def upgrade() -> None:
    """Add response metadata columns to usage_reservations."""
    op.add_column(
        _USAGE_RESERVATIONS,
        sa.Column("response_model", sa.String(100), nullable=True),
    )
    op.add_column(
        _USAGE_RESERVATIONS,
        sa.Column("response_input_tokens", sa.Integer, nullable=True),
    )
    op.add_column(
        _USAGE_RESERVATIONS,
        sa.Column("response_output_tokens", sa.Integer, nullable=True),
    )
    op.add_column(
        _USAGE_RESERVATIONS,
        sa.Column("call_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Non-negative token counts (parity with llm_usage_records constraints)
    op.create_check_constraint(
        _CK_RESP_INPUT,
        _USAGE_RESERVATIONS,
        "response_input_tokens IS NULL OR response_input_tokens >= 0",
    )
    op.create_check_constraint(
        _CK_RESP_OUTPUT,
        _USAGE_RESERVATIONS,
        "response_output_tokens IS NULL OR response_output_tokens >= 0",
    )

    # All-or-nothing: outbox columns must be fully NULL or fully populated
    op.create_check_constraint(
        _CK_RESP_COMPLETE,
        _USAGE_RESERVATIONS,
        "(call_completed_at IS NULL AND response_model IS NULL "
        "AND response_input_tokens IS NULL AND response_output_tokens IS NULL) "
        "OR (call_completed_at IS NOT NULL AND response_model IS NOT NULL "
        "AND response_input_tokens IS NOT NULL AND response_output_tokens IS NOT NULL)",
    )


def downgrade() -> None:
    """Remove response metadata columns and constraints from usage_reservations."""
    op.drop_constraint(_CK_RESP_COMPLETE, _USAGE_RESERVATIONS, type_="check")
    op.drop_constraint(_CK_RESP_OUTPUT, _USAGE_RESERVATIONS, type_="check")
    op.drop_constraint(_CK_RESP_INPUT, _USAGE_RESERVATIONS, type_="check")
    op.drop_column(_USAGE_RESERVATIONS, "call_completed_at")
    op.drop_column(_USAGE_RESERVATIONS, "response_output_tokens")
    op.drop_column(_USAGE_RESERVATIONS, "response_input_tokens")
    op.drop_column(_USAGE_RESERVATIONS, "response_model")
