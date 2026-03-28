"""Add index on stripe_purchases.stripe_payment_intent.

Revision ID: 027_stripe_payment_intent_index
Revises: 026_signup_grant_unique_index
Create Date: 2026-03-27

Performance fix: find_by_payment_intent() queries this column on every
charge.refunded webhook. Without an index, PostgreSQL performs a
sequential scan on stripe_purchases — invisible at low volume but
degrades linearly with table growth.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "027_stripe_payment_intent_index"
down_revision: str = "026_signup_grant_unique_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add non-unique index on stripe_payment_intent for webhook lookups."""
    op.create_index(
        "ix_stripe_purchases_stripe_payment_intent",
        "stripe_purchases",
        ["stripe_payment_intent"],
    )


def downgrade() -> None:
    """Remove stripe_payment_intent index."""
    op.drop_index(
        "ix_stripe_purchases_stripe_payment_intent",
        table_name="stripe_purchases",
    )
