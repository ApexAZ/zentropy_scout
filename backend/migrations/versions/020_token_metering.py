"""Add token metering tables and user balance.

Revision ID: 020_token_metering
Revises: 019_race_condition_indexes
Create Date: 2026-02-27

REQ-020 §4: Creates llm_usage_records and credit_transactions tables
for recording LLM/embedding API usage and maintaining a financial ledger.
Adds balance_usd column to users table for cached USD balance.

Note: Both tables use ON DELETE CASCADE per REQ-020 spec. Financial records
are destroyed when a user is deleted. If audit retention is needed later,
switch to soft-delete/anonymization in the application layer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_token_metering"
down_revision: str = "019_race_condition_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Shared column types
_PG_UUID = sa.dialects.postgresql.UUID(as_uuid=True)
_UUID_DEFAULT = sa.text("gen_random_uuid()")
_NUMERIC_10_6 = sa.Numeric(precision=10, scale=6)


def upgrade() -> None:
    """Create metering tables and add balance_usd to users."""
    # 1. Add balance_usd column to users table
    op.add_column(
        "users",
        sa.Column(
            "balance_usd",
            _NUMERIC_10_6,
            server_default="0.000000",
            nullable=False,
        ),
    )

    # 2. Create llm_usage_records table
    op.create_table(
        "llm_usage_records",
        sa.Column("id", _PG_UUID, server_default=_UUID_DEFAULT, primary_key=True),
        sa.Column(
            "user_id",
            _PG_UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("raw_cost_usd", _NUMERIC_10_6, nullable=False),
        sa.Column("billed_cost_usd", _NUMERIC_10_6, nullable=False),
        sa.Column(
            "margin_multiplier", sa.Numeric(precision=4, scale=2), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # CHECK constraints for financial integrity
        sa.CheckConstraint("input_tokens >= 0", name="ck_usage_input_tokens_nonneg"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_usage_output_tokens_nonneg"),
        sa.CheckConstraint("raw_cost_usd >= 0", name="ck_usage_raw_cost_nonneg"),
        sa.CheckConstraint("billed_cost_usd >= 0", name="ck_usage_billed_cost_nonneg"),
        sa.CheckConstraint("margin_multiplier > 0", name="ck_usage_margin_positive"),
    )

    # 3. Create credit_transactions table
    op.create_table(
        "credit_transactions",
        sa.Column("id", _PG_UUID, server_default=_UUID_DEFAULT, primary_key=True),
        sa.Column(
            "user_id",
            _PG_UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_usd", _NUMERIC_10_6, nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("reference_id", sa.String(255), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # CHECK constraint for valid transaction types
        sa.CheckConstraint(
            "transaction_type IN ('purchase', 'usage_debit', 'admin_grant', 'refund')",
            name="ck_credit_txn_type_valid",
        ),
    )

    # 4. Create indexes per REQ-020 §4.4
    op.create_index(
        "ix_llm_usage_records_user_created",
        "llm_usage_records",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_llm_usage_records_user_task",
        "llm_usage_records",
        ["user_id", "task_type"],
    )
    op.create_index(
        "ix_credit_transactions_user_created",
        "credit_transactions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_credit_transactions_user_type",
        "credit_transactions",
        ["user_id", "transaction_type"],
    )


def downgrade() -> None:
    """Remove metering tables and balance_usd column."""
    # Drop indexes first
    op.drop_index(
        "ix_credit_transactions_user_type",
        table_name="credit_transactions",
    )
    op.drop_index(
        "ix_credit_transactions_user_created",
        table_name="credit_transactions",
    )
    op.drop_index(
        "ix_llm_usage_records_user_task",
        table_name="llm_usage_records",
    )
    op.drop_index(
        "ix_llm_usage_records_user_created",
        table_name="llm_usage_records",
    )

    # Drop tables
    op.drop_table("credit_transactions")
    op.drop_table("llm_usage_records")

    # Remove balance_usd column
    op.drop_column("users", "balance_usd")
