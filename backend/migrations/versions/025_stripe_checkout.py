"""Stripe checkout schema + signup grant data migration.

REQ-029 §4.6: Add stripe_customer_id to users, stripe_event_id to
credit_transactions, create stripe_purchases table with indexes, update
CHECK constraint for signup_grant transaction type, and backfill signup
grant transactions for existing users.
"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "025_stripe_checkout"
down_revision: str = "024_gemini_embedding_dimensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")
_SIGNUP_GRANT_QUERY = sa.text(
    "SELECT value FROM system_config WHERE key = 'signup_grant_cents'"
)


def _read_grant_cents(conn) -> int:
    """Read signup_grant_cents from system_config, defaulting to 0."""
    row = conn.execute(_SIGNUP_GRANT_QUERY).fetchone()
    if not row:
        return 0
    try:
        return int(row[0])
    except (ValueError, TypeError):
        return 0


def upgrade() -> None:
    # 1. Add stripe_customer_id to users (VARCHAR 255, nullable, unique)
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_users_stripe_customer_id", "users", ["stripe_customer_id"]
    )

    # 2. Add stripe_event_id to credit_transactions (VARCHAR 255, nullable, unique)
    op.add_column(
        "credit_transactions",
        sa.Column("stripe_event_id", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_credit_txn_stripe_event_id",
        "credit_transactions",
        ["stripe_event_id"],
    )

    # 3. Update CHECK constraint to include signup_grant
    op.drop_constraint("ck_credit_txn_type_valid", "credit_transactions", type_="check")
    op.create_check_constraint(
        "ck_credit_txn_type_valid",
        "credit_transactions",
        "transaction_type IN ("
        "'purchase', 'usage_debit', 'admin_grant', 'refund', 'signup_grant')",
    )

    # 4. Create stripe_purchases table
    op.create_table(
        "stripe_purchases",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=_UUID_DEFAULT,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("pack_id", sa.UUID(), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False),
        sa.Column("stripe_payment_intent", sa.String(255), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("grant_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'usd'"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "refund_amount_cents",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pack_id"], ["funding_packs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("stripe_session_id", name="uq_stripe_purchases_session_id"),
        sa.CheckConstraint(
            "amount_cents > 0",
            name="ck_stripe_purchases_amount_positive",
        ),
        sa.CheckConstraint(
            "grant_cents > 0",
            name="ck_stripe_purchases_grant_positive",
        ),
        sa.CheckConstraint(
            "refund_amount_cents >= 0",
            name="ck_stripe_purchases_refund_nonneg",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'refunded', 'partial_refund')",
            name="ck_stripe_purchases_status_valid",
        ),
    )

    # 5. Create indexes
    op.create_index("ix_stripe_purchases_user_id", "stripe_purchases", ["user_id"])
    op.create_index(
        "ix_stripe_purchases_customer_id",
        "stripe_purchases",
        ["stripe_customer_id"],
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_stripe_purchases_status_pending "
            "ON stripe_purchases(status) WHERE status = 'pending'"
        )
    )

    # 6. Data migration: signup grant for existing users
    #    Read signup_grant_cents from system_config; skip if 0 or missing.
    conn = op.get_bind()
    grant_cents = _read_grant_cents(conn)

    if grant_cents > 0:
        grant_usd = Decimal(grant_cents) / Decimal(100)

        # CTE: INSERT signup_grant for eligible users, then credit only
        # the newly-inserted users (prevents double-credit on re-run).
        conn.execute(
            sa.text(
                "WITH inserted AS ("
                "  INSERT INTO credit_transactions "
                "  (id, user_id, amount_usd, transaction_type, description, created_at) "
                "  SELECT gen_random_uuid(), u.id, :grant_usd, 'signup_grant', "
                "  'Welcome bonus — free starter balance', now() "
                "  FROM users u "
                "  WHERE u.id NOT IN ("
                "    SELECT ct.user_id FROM credit_transactions ct "
                "    WHERE ct.transaction_type = 'signup_grant'"
                "  ) "
                "  RETURNING user_id"
                ") "
                "UPDATE users SET balance_usd = balance_usd + :grant_usd "
                "WHERE id IN (SELECT user_id FROM inserted)"
            ),
            {"grant_usd": grant_usd},
        )


def downgrade() -> None:
    conn = op.get_bind()

    # 1. Reverse data migration: debit signup grant and delete transactions
    grant_cents = _read_grant_cents(conn)

    if grant_cents > 0:
        grant_usd = Decimal(grant_cents) / Decimal(100)
        # Debit balance, flooring at zero (users may have spent part)
        conn.execute(
            sa.text(
                "UPDATE users SET balance_usd = GREATEST(balance_usd - :grant_usd, 0) "
                "WHERE id IN ("
                "  SELECT user_id FROM credit_transactions "
                "  WHERE transaction_type = 'signup_grant'"
                ")"
            ),
            {"grant_usd": grant_usd},
        )

    # Delete all signup_grant transactions (regardless of grant_cents value)
    conn.execute(
        sa.text(
            "DELETE FROM credit_transactions WHERE transaction_type = 'signup_grant'"
        )
    )

    # 2. Drop stripe_purchases table and indexes
    op.drop_index("ix_stripe_purchases_status_pending", table_name="stripe_purchases")
    op.drop_index("ix_stripe_purchases_customer_id", table_name="stripe_purchases")
    op.drop_index("ix_stripe_purchases_user_id", table_name="stripe_purchases")
    op.drop_table("stripe_purchases")

    # 3. Restore original CHECK constraint (without signup_grant)
    op.drop_constraint("ck_credit_txn_type_valid", "credit_transactions", type_="check")
    op.create_check_constraint(
        "ck_credit_txn_type_valid",
        "credit_transactions",
        "transaction_type IN ('purchase', 'usage_debit', 'admin_grant', 'refund')",
    )

    # 4. Drop stripe_event_id from credit_transactions
    op.drop_constraint(
        "uq_credit_txn_stripe_event_id",
        "credit_transactions",
        type_="unique",
    )
    op.drop_column("credit_transactions", "stripe_event_id")

    # 5. Drop stripe_customer_id from users
    op.drop_constraint("uq_users_stripe_customer_id", "users", type_="unique")
    op.drop_column("users", "stripe_customer_id")
