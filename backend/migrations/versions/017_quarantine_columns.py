"""Add quarantine columns to job_postings for pool poisoning defense.

Revision ID: 017_quarantine_columns
Revises: 016_source_external_unique_index
Create Date: 2026-02-22

REQ-015 §8.4 mitigation 3: Manual submissions are quarantined until
independently confirmed, admin-approved, or auto-released after 7 days.

Columns added:
- is_quarantined (BOOLEAN NOT NULL DEFAULT false)
- quarantined_at (TIMESTAMPTZ NULL)
- quarantine_expires_at (TIMESTAMPTZ NULL — NULL means permanent quarantine)

Index: partial on is_quarantined=true for efficient surfacing worker queries.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_quarantine_columns"
down_revision: str = "016_source_external_unique_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add quarantine columns and index to job_postings."""
    op.add_column(
        "job_postings",
        sa.Column(
            "is_quarantined",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "quarantined_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "quarantine_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Partial index: only quarantined jobs need to be queried by the worker.
    # Most jobs are NOT quarantined, so a partial index is efficient.
    op.create_index(
        "idx_job_postings_quarantined",
        "job_postings",
        ["is_quarantined"],
        postgresql_where=sa.text("is_quarantined = true"),
    )


def downgrade() -> None:
    """Remove quarantine columns and index from job_postings."""
    op.drop_index("idx_job_postings_quarantined", table_name="job_postings")
    op.drop_column("job_postings", "quarantine_expires_at")
    op.drop_column("job_postings", "quarantined_at")
    op.drop_column("job_postings", "is_quarantined")
