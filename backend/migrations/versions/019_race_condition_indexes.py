"""Add unique indexes to prevent race condition duplicates.

Revision ID: 019_race_condition_indexes
Revises: 018_verification_token_purpose
Create Date: 2026-02-25

Security fix: Adds database-level constraints to prevent duplicate data
from concurrent requests:

1. UNIQUE index on job_postings.description_hash — prevents duplicate
   job postings in the shared pool from concurrent manual submissions.

2. Partial UNIQUE index on job_variants(base_resume_id, job_posting_id)
   WHERE archived_at IS NULL — prevents duplicate active variants for
   the same base resume + job posting combination.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "019_race_condition_indexes"
down_revision: str = "018_verification_token_purpose"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add unique indexes for race condition prevention."""
    # 1. Unique description_hash prevents duplicate job postings from
    #    concurrent manual submissions (SELECT-then-INSERT race).
    #    Replaces the non-unique idx_job_postings_description_hash
    #    (originally idx_jobposting_hash from 003, renamed in 011).
    op.drop_index("idx_job_postings_description_hash", table_name="job_postings")
    op.create_index(
        "uq_job_postings_description_hash",
        "job_postings",
        ["description_hash"],
        unique=True,
    )

    # 2. Partial unique index: only one active (non-archived) variant per
    #    base_resume + job_posting. Concurrent persist_draft_materials calls
    #    can no longer create duplicates.
    op.create_index(
        "uq_job_variants_active_base_job",
        "job_variants",
        ["base_resume_id", "job_posting_id"],
        unique=True,
        postgresql_where="archived_at IS NULL",
    )


def downgrade() -> None:
    """Remove unique indexes (revert to non-unique)."""
    op.drop_index(
        "uq_job_variants_active_base_job",
        table_name="job_variants",
    )
    op.drop_index(
        "uq_job_postings_description_hash",
        table_name="job_postings",
    )
    # Restore the non-unique index (post-011 naming convention)
    op.create_index(
        "idx_job_postings_description_hash",
        "job_postings",
        ["description_hash"],
    )
