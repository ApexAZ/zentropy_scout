"""Billing and metering hardening schema changes.

Revision ID: 028_billing_hardening
Revises: 027_stripe_payment_intent_index
Create Date: 2026-03-28

REQ-030 §4: Adds held_balance_usd to users, creates usage_reservations
table for pre-debit reservation pattern, aligns grant_cents type
(BIGINT->INTEGER) on stripe_purchases and funding_packs, adds 'expired'
to stripe_purchases status constraint.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_billing_hardening"
down_revision: str = "027_stripe_payment_intent_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Constants (matching sibling migration patterns from 020/021/025)
_PG_UUID = sa.dialects.postgresql.UUID(as_uuid=True)
_UUID_DEFAULT = sa.text("gen_random_uuid()")
_NUMERIC_10_6 = sa.Numeric(10, 6)
_STRIPE_PURCHASES = "stripe_purchases"
_FUNDING_PACKS = "funding_packs"
_USAGE_RESERVATIONS = "usage_reservations"
_GRANT_CENTS = "grant_cents"
_CK_STATUS_VALID = "ck_stripe_purchases_status_valid"
_CK_HELD_BALANCE = "ck_users_held_balance_nonneg"
_IX_USER_STATUS = "ix_reservation_user_status"
_IX_STALE_SWEEP = "ix_reservation_stale_sweep"
_INTEGER_MAX = 2_147_483_647


def upgrade() -> None:
    """Add reservation infrastructure and hardening fixes."""
    # 1. Add held_balance_usd to users (REQ-030 §4.1)
    op.add_column(
        "users",
        sa.Column(
            "held_balance_usd",
            _NUMERIC_10_6,
            nullable=False,
            server_default=sa.text("0.000000"),
        ),
    )
    op.create_check_constraint(
        _CK_HELD_BALANCE,
        "users",
        "held_balance_usd >= 0",
    )

    # 2. Create usage_reservations table (REQ-030 §4.2)
    op.create_table(
        _USAGE_RESERVATIONS,
        sa.Column(
            "id",
            _PG_UUID,
            primary_key=True,
            server_default=_UUID_DEFAULT,
        ),
        sa.Column(
            "user_id",
            _PG_UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("estimated_cost_usd", _NUMERIC_10_6, nullable=False),
        sa.Column("actual_cost_usd", _NUMERIC_10_6, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'held'"),
        ),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(20), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("max_tokens", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('held', 'settled', 'released', 'stale')",
            name="ck_reservation_status_valid",
        ),
        sa.CheckConstraint(
            "estimated_cost_usd > 0",
            name="ck_reservation_estimated_positive",
        ),
        sa.CheckConstraint(
            "actual_cost_usd IS NULL OR actual_cost_usd >= 0",
            name="ck_reservation_actual_nonneg",
        ),
    )

    # Indexes on usage_reservations
    op.create_index(
        _IX_USER_STATUS,
        _USAGE_RESERVATIONS,
        ["user_id", "status"],
    )
    op.create_index(
        _IX_STALE_SWEEP,
        _USAGE_RESERVATIONS,
        ["created_at"],
        postgresql_where=sa.text("status = 'held'"),
    )

    # 3. Align grant_cents BIGINT -> INTEGER (REQ-030 §4.3)
    # Safety: verify no existing data exceeds INTEGER range
    conn = op.get_bind()
    for table in (_STRIPE_PURCHASES, _FUNDING_PACKS):
        max_val = conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
            # AF-12: Both _GRANT_CENTS and table are module-level string constants,
            # not user input — f-string is safe here. Parameterized queries cannot
            # be used for table/column identifiers in SQL.
            sa.text(f"SELECT COALESCE(MAX({_GRANT_CENTS}), 0) FROM {table}")
        ).scalar()
        if max_val > _INTEGER_MAX:
            msg = f"{table}.{_GRANT_CENTS} has value {max_val} exceeding INTEGER max"
            raise RuntimeError(msg)

    op.alter_column(
        _STRIPE_PURCHASES,
        _GRANT_CENTS,
        type_=sa.Integer,
        existing_type=sa.BigInteger,
        existing_nullable=False,
    )
    op.alter_column(
        _FUNDING_PACKS,
        _GRANT_CENTS,
        type_=sa.Integer,
        existing_type=sa.BigInteger,
        existing_nullable=False,
    )

    # 4. Add 'expired' to stripe_purchases status constraint (REQ-030 §7.3)
    op.drop_constraint(_CK_STATUS_VALID, _STRIPE_PURCHASES, type_="check")
    op.create_check_constraint(
        _CK_STATUS_VALID,
        _STRIPE_PURCHASES,
        "status IN ('pending', 'completed', 'refunded', 'partial_refund', 'expired')",
    )


def downgrade() -> None:
    """Reverse all billing hardening schema changes."""
    # 4. Migrate 'expired' rows before restoring narrower constraint
    op.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
        # AF-12: _STRIPE_PURCHASES is a module-level constant, not user input.
        sa.text(
            f"UPDATE {_STRIPE_PURCHASES} SET status = 'pending' "
            "WHERE status = 'expired'"
        )
    )
    op.drop_constraint(_CK_STATUS_VALID, _STRIPE_PURCHASES, type_="check")
    op.create_check_constraint(
        _CK_STATUS_VALID,
        _STRIPE_PURCHASES,
        "status IN ('pending', 'completed', 'refunded', 'partial_refund')",
    )

    # 3. Restore grant_cents INTEGER -> BIGINT
    op.alter_column(
        _FUNDING_PACKS,
        _GRANT_CENTS,
        type_=sa.BigInteger,
        existing_type=sa.Integer,
        existing_nullable=False,
    )
    op.alter_column(
        _STRIPE_PURCHASES,
        _GRANT_CENTS,
        type_=sa.BigInteger,
        existing_type=sa.Integer,
        existing_nullable=False,
    )

    # 2. Release held reservations, then drop table
    op.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
        # AF-12: _USAGE_RESERVATIONS is a module-level constant, not user input.
        sa.text(
            f"UPDATE {_USAGE_RESERVATIONS} SET status = 'released', "
            "settled_at = now() WHERE status = 'held'"
        )
    )
    op.execute(sa.text("UPDATE users SET held_balance_usd = 0"))
    op.drop_index(_IX_STALE_SWEEP, table_name=_USAGE_RESERVATIONS)
    op.drop_index(_IX_USER_STATUS, table_name=_USAGE_RESERVATIONS)
    op.drop_table(_USAGE_RESERVATIONS)

    # 1. Remove held_balance_usd from users
    op.drop_constraint(_CK_HELD_BALANCE, "users", type_="check")
    op.drop_column("users", "held_balance_usd")
