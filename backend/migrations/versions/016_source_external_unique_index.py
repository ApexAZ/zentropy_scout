"""Add dedup indexes for shared job pool.

Revision ID: 016_source_external_unique_index
Revises: 015_update_cleanup_functions
Create Date: 2026-02-22

REQ-015 §10.3: UNIQUE constraint on job_postings(source_id, external_id)
WHERE external_id IS NOT NULL. Prevents duplicate inserts when two Scouters
discover the same job simultaneously. Losing INSERT gets IntegrityError,
recovers by looking up the existing record.

Also adds functional index on lower(company_name) for case-insensitive
similarity lookups (dedup step 3).
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers
revision: str = "016_source_external_unique_index"
down_revision: str = "015_update_cleanup_functions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_job_postings_source_external_unique",
        "job_postings",
        ["source_id", "external_id"],
        unique=True,
        postgresql_where="external_id IS NOT NULL",
    )
    op.execute(
        text(
            "CREATE INDEX idx_job_postings_company_lower "
            "ON job_postings (lower(company_name)) "
            "WHERE is_active = true"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "idx_job_postings_company_lower",
        table_name="job_postings",
    )
    op.drop_index(
        "idx_job_postings_source_external_unique",
        table_name="job_postings",
    )
