"""Add partial unique index for signup grant idempotency.

Revision ID: 026_signup_grant_unique_index
Revises: 025_stripe_checkout
Create Date: 2026-03-11

Security fix: Prevents TOCTOU race in grant_signup_credits() — two
concurrent registrations (double-click, overlapping OAuth + magic link)
could both pass the application-level SELECT check and insert duplicate
signup_grant transactions. The partial unique index enforces one
signup_grant per user at the database level.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "026_signup_grant_unique_index"
down_revision: str = "025_stripe_checkout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial unique index: one signup_grant per user."""
    op.create_index(
        "uq_credit_txn_signup_grant_per_user",
        "credit_transactions",
        ["user_id"],
        unique=True,
        postgresql_where="transaction_type = 'signup_grant'",
    )


def downgrade() -> None:
    """Remove signup grant unique index."""
    op.drop_index(
        "uq_credit_txn_signup_grant_per_user",
        table_name="credit_transactions",
    )
