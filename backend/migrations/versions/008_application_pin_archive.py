"""Add is_pinned and archived_at columns to applications table.

Revision ID: 008_application_pin_archive
Revises: 007_cleanup_functions
Create Date: 2026-02-08

REQ-012 Appendix A.1: Applications support pinning (excluded from
auto-archive) and soft delete via archived_at timestamp.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_application_pin_archive"
down_revision: str | None = "007_cleanup_functions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "applications",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("applications", "archived_at")
    op.drop_column("applications", "is_pinned")
