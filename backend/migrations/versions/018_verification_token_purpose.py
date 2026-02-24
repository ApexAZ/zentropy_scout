"""Add purpose column to verification_tokens.

Revision ID: 018_verification_token_purpose
Revises: 017_quarantine_columns
Create Date: 2026-02-24

Security fix: Binds the token purpose (sign_in vs password_reset) to the
stored token so that a sign-in magic link cannot be escalated to a
password-reset flow by tampering with the URL query parameter.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_verification_token_purpose"
down_revision: str = "017_quarantine_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add purpose column with server default 'sign_in'."""
    op.add_column(
        "verification_tokens",
        sa.Column(
            "purpose",
            sa.String(20),
            server_default=sa.text("'sign_in'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove purpose column."""
    op.drop_column("verification_tokens", "purpose")
