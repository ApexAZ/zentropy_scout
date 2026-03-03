"""Rename credit_packs to funding_packs, update seed data to USD cents.

Revision ID: 022_usd_direct_billing
Revises: 021_admin_pricing
Create Date: 2026-03-02

REQ-023 §4.1: Renames the credit_packs table to funding_packs, renames
credit_amount column to grant_cents, updates constraints/index names,
replaces abstract credit seed data with USD-cent dollar-for-dollar values,
and renames the signup_grant_credits config key to signup_grant_cents.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "022_usd_direct_billing"
down_revision: str = "021_admin_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Rename table
    op.execute("ALTER TABLE credit_packs RENAME TO funding_packs")

    # 2. Rename column
    op.execute("ALTER TABLE funding_packs RENAME COLUMN credit_amount TO grant_cents")

    # 3. Rename check constraints
    op.execute(
        "ALTER TABLE funding_packs "
        "RENAME CONSTRAINT ck_credit_packs_price_positive "
        "TO ck_funding_packs_price_positive"
    )
    op.execute(
        "ALTER TABLE funding_packs "
        "RENAME CONSTRAINT ck_credit_packs_amount_positive "
        "TO ck_funding_packs_amount_positive"
    )

    # 4. Rename index
    op.execute("ALTER INDEX ix_credit_packs_active RENAME TO ix_funding_packs_active")

    # 5. Replace seed data — delete abstract credit packs, insert USD-cent packs
    op.execute("DELETE FROM funding_packs WHERE name IN ('Starter', 'Standard', 'Pro')")
    op.execute(
        "INSERT INTO funding_packs "
        "(name, price_cents, grant_cents, display_order, is_active, "
        "description, highlight_label) VALUES "
        "('Starter',  500,  500,  1, TRUE, "
        "'Analyze ~250 jobs and generate tailored materials', NULL), "
        "('Standard', 1000, 1000, 2, TRUE, "
        "'Analyze ~500 jobs and generate tailored materials', 'Most Popular'), "
        "('Pro',      1500, 1500, 3, TRUE, "
        "'Analyze ~750 jobs and generate tailored materials', 'Best Value')"
    )

    # 6. Rename system config key
    op.execute(
        "UPDATE system_config "
        "SET key = 'signup_grant_cents', "
        "    value = '10', "
        "    description = 'USD cents granted to new users on signup "
        "(0 = disabled)' "
        "WHERE key = 'signup_grant_credits'"
    )


def downgrade() -> None:
    # 1. Restore config key
    op.execute(
        "UPDATE system_config "
        "SET key = 'signup_grant_credits', "
        "    value = '0', "
        "    description = 'Credits granted to new users on signup' "
        "WHERE key = 'signup_grant_cents'"
    )

    # 2. Restore original seed data
    op.execute("DELETE FROM funding_packs WHERE name IN ('Starter', 'Standard', 'Pro')")
    op.execute(
        "INSERT INTO funding_packs "
        "(name, price_cents, grant_cents, display_order, is_active, "
        "description, highlight_label) VALUES "
        "('Starter',  500,  50000,  1, TRUE, "
        "'Get started with Zentropy Scout', NULL), "
        "('Standard', 1500, 175000, 2, TRUE, "
        "'For regular users', 'Most Popular'), "
        "('Pro',      4000, 500000, 3, TRUE, "
        "'For power users', 'Best Value')"
    )

    # 3. Rename index back
    op.execute("ALTER INDEX ix_funding_packs_active RENAME TO ix_credit_packs_active")

    # 4. Rename constraints back
    op.execute(
        "ALTER TABLE funding_packs "
        "RENAME CONSTRAINT ck_funding_packs_amount_positive "
        "TO ck_credit_packs_amount_positive"
    )
    op.execute(
        "ALTER TABLE funding_packs "
        "RENAME CONSTRAINT ck_funding_packs_price_positive "
        "TO ck_credit_packs_price_positive"
    )

    # 5. Rename column back
    op.execute("ALTER TABLE funding_packs RENAME COLUMN grant_cents TO credit_amount")

    # 6. Rename table back
    op.execute("ALTER TABLE funding_packs RENAME TO credit_packs")
