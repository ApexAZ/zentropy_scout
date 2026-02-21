"""Create persona_jobs table and add is_active to job_postings.

Revision ID: 012_persona_jobs
Revises: 011_rename_indexes
Create Date: 2026-02-21

REQ-015 §4, §11 steps 1–3: Shared job pool schema preparation.

Step 1: Create persona_jobs table — per-user relationship to shared job
        postings. Holds all fields that were previously per-user on
        job_postings (status, is_favorite, scores, discovery metadata).

Step 2: Add is_active BOOLEAN to job_postings — replaces the per-user
        'Expired' status with a shared flag.

Step 3: Add partial UNIQUE on job_postings(source_id, external_id) WHERE
        both are NOT NULL — race condition guard for Scouter dedup.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "012_persona_jobs"
down_revision: str | None = "011_rename_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # Step 1: Create persona_jobs table (REQ-015 §4.2)
    # =========================================================================

    op.create_table(
        "persona_jobs",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("persona_id", sa.UUID(), nullable=False),
        sa.Column("job_posting_id", sa.UUID(), nullable=False),
        # User relationship
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'Discovered'"),
        ),
        sa.Column(
            "is_favorite",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        # Per-user scoring (from Strategist)
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("stretch_score", sa.Integer(), nullable=True),
        sa.Column("failed_non_negotiables", JSONB(), nullable=True),
        sa.Column("score_details", JSONB(), nullable=True),
        # Discovery metadata
        sa.Column(
            "discovery_method",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pool'"),
        ),
        # Timestamps
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
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
        # Foreign keys
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["job_posting_id"], ["job_postings.id"], ondelete="RESTRICT"
        ),
        # Check constraints
        sa.CheckConstraint(
            "status IN ('Discovered', 'Dismissed', 'Applied')",
            name="ck_persona_jobs_status",
        ),
        sa.CheckConstraint(
            "discovery_method IN ('scouter', 'manual', 'pool')",
            name="ck_persona_jobs_discovery_method",
        ),
        sa.CheckConstraint(
            "fit_score >= 0 AND fit_score <= 100 OR fit_score IS NULL",
            name="ck_persona_jobs_fit_score",
        ),
        sa.CheckConstraint(
            "stretch_score >= 0 AND stretch_score <= 100 OR stretch_score IS NULL",
            name="ck_persona_jobs_stretch_score",
        ),
        # One link per persona per job
        sa.UniqueConstraint(
            "persona_id", "job_posting_id", name="uq_persona_jobs_persona_job"
        ),
    )

    # Indexes (REQ-015 §4.2)
    op.create_index("idx_persona_jobs_persona_id", "persona_jobs", ["persona_id"])
    op.create_index(
        "idx_persona_jobs_job_posting_id", "persona_jobs", ["job_posting_id"]
    )
    op.create_index(
        "idx_persona_jobs_persona_id_status",
        "persona_jobs",
        ["persona_id", "status"],
    )
    # Partial index: only Discovered jobs need fast score lookup
    op.execute(
        "CREATE INDEX idx_persona_jobs_persona_id_fit_score "
        "ON persona_jobs (persona_id, fit_score DESC) "
        "WHERE status = 'Discovered'"
    )

    # =========================================================================
    # Step 2: Add is_active to job_postings (REQ-015 §4.1)
    # =========================================================================

    op.add_column(
        "job_postings",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # =========================================================================
    # Step 3: Partial UNIQUE on (source_id, external_id) (REQ-015 §10.3)
    # =========================================================================

    op.execute(
        "CREATE UNIQUE INDEX uq_job_postings_source_id_external_id "
        "ON job_postings (source_id, external_id) "
        "WHERE source_id IS NOT NULL AND external_id IS NOT NULL"
    )


def downgrade() -> None:
    # Step 3: Drop partial UNIQUE index
    op.execute("DROP INDEX IF EXISTS uq_job_postings_source_id_external_id")

    # Step 2: Remove is_active from job_postings
    op.drop_column("job_postings", "is_active")

    # Step 1: Drop persona_jobs indexes and table
    op.execute("DROP INDEX IF EXISTS idx_persona_jobs_persona_id_fit_score")
    op.drop_index("idx_persona_jobs_persona_id_status")
    op.drop_index("idx_persona_jobs_job_posting_id")
    op.drop_index("idx_persona_jobs_persona_id")
    op.drop_table("persona_jobs")
