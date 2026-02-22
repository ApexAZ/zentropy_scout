"""Drop per-user columns from job_postings, add persona_job_id to applications.

Revision ID: 014_drop_per_user_columns
Revises: 013_backfill_persona_jobs
Create Date: 2026-02-21

REQ-015 §11 steps 7–10:

Step 7: Add persona_job_id FK to applications (backfill from persona_jobs).
Step 8: Drop per-user columns from job_postings (status, is_favorite,
        fit_score, stretch_score, score_details, failed_non_negotiables,
        dismissed_at).
Step 9: Drop persona_id FK from job_postings.
Step 10: Update indexes (drop persona-scoped, add global).

WARNING: Steps 8-9 are destructive and not trivially reversible. The dedup
script (backend/scripts/dedup_cross_persona.py) MUST have been run before
this migration. The application should be stopped during this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "014_drop_per_user_columns"
down_revision: str | None = "013_backfill_persona_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ===================================================================
    # Step 7: Add persona_job_id FK to applications
    # ===================================================================
    op.add_column(
        "applications",
        sa.Column("persona_job_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_applications_persona_job_id",
        "applications",
        "persona_jobs",
        ["persona_job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill: match applications to persona_jobs via persona_id + job_posting_id
    op.execute(
        sa.text(
            "UPDATE applications a "
            "SET persona_job_id = pj.id "
            "FROM persona_jobs pj "
            "WHERE pj.persona_id = a.persona_id "
            "AND pj.job_posting_id = a.job_posting_id"
        )
    )

    # ===================================================================
    # Step 10: Drop persona-scoped indexes (before dropping columns)
    # ===================================================================
    op.drop_index("idx_job_postings_persona_id", table_name="job_postings")
    op.drop_index("idx_job_postings_persona_id_status", table_name="job_postings")
    op.drop_index("idx_job_postings_persona_id_fit_score", table_name="job_postings")

    # ===================================================================
    # Steps 8–9: Drop per-user columns and constraints from job_postings
    # ===================================================================

    # Drop CHECK constraints that reference columns being removed
    op.drop_constraint("ck_jobposting_status", "job_postings", type_="check")
    op.drop_constraint("ck_jobposting_fit_score", "job_postings", type_="check")
    op.drop_constraint("ck_jobposting_stretch_score", "job_postings", type_="check")

    # Drop persona_id FK constraint
    op.drop_constraint(
        "job_postings_persona_id_fkey", "job_postings", type_="foreignkey"
    )

    # Drop per-user columns
    for col in (
        "persona_id",
        "status",
        "is_favorite",
        "fit_score",
        "stretch_score",
        "failed_non_negotiables",
        "dismissed_at",
        "score_details",
    ):
        op.drop_column("job_postings", col)

    # ===================================================================
    # Step 10: Add global indexes
    # ===================================================================
    op.create_index(
        "idx_job_postings_is_active",
        "job_postings",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_job_postings_company_name_job_title",
        "job_postings",
        ["company_name", "job_title"],
    )
    op.create_index(
        "idx_job_postings_first_seen_date",
        "job_postings",
        [sa.text("first_seen_date DESC")],
    )


def downgrade() -> None:
    # ===================================================================
    # Remove new global indexes
    # ===================================================================
    op.drop_index("idx_job_postings_first_seen_date", table_name="job_postings")
    op.drop_index("idx_job_postings_company_name_job_title", table_name="job_postings")
    op.drop_index("idx_job_postings_is_active", table_name="job_postings")

    # ===================================================================
    # Re-add per-user columns (nullable first for backfill)
    # ===================================================================
    op.add_column(
        "job_postings",
        sa.Column("persona_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'Discovered'"),
            nullable=False,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "is_favorite",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column("fit_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column("stretch_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "failed_non_negotiables",
            JSONB(),
            nullable=True,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column(
            "score_details",
            JSONB(),
            nullable=True,
        ),
    )

    # ===================================================================
    # Backfill from persona_jobs (pick oldest link per job_posting).
    # WARNING: Multi-persona postings will lose all but the oldest link.
    # This is expected — downgrade is lossy by design (see docstring).
    # ===================================================================
    op.execute(
        sa.text(
            "UPDATE job_postings jp "
            "SET persona_id = sub.persona_id, "
            "    status = CASE "
            "        WHEN jp.is_active = false THEN 'Expired' "
            "        ELSE sub.status "
            "    END, "
            "    is_favorite = sub.is_favorite, "
            "    fit_score = sub.fit_score, "
            "    stretch_score = sub.stretch_score, "
            "    failed_non_negotiables = sub.failed_non_negotiables, "
            "    dismissed_at = sub.dismissed_at, "
            "    score_details = sub.score_details "
            "FROM ("
            "    SELECT DISTINCT ON (job_posting_id) "
            "        job_posting_id, persona_id, status, is_favorite, "
            "        fit_score, stretch_score, failed_non_negotiables, "
            "        dismissed_at, score_details "
            "    FROM persona_jobs "
            "    ORDER BY job_posting_id, created_at ASC"
            ") sub "
            "WHERE jp.id = sub.job_posting_id"
        )
    )

    # Delete job_postings with no persona_jobs link (shared pool only —
    # cannot exist in the pre-shared-pool schema).
    # Guard: abort if any orphaned postings have dependent children
    # (job_variants, applications, cover_letters use ON DELETE RESTRICT).
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF EXISTS ("
            "    SELECT 1 FROM job_postings jp "
            "    WHERE NOT EXISTS ("
            "        SELECT 1 FROM persona_jobs pj "
            "        WHERE pj.job_posting_id = jp.id"
            "    ) "
            "    AND ("
            "        EXISTS (SELECT 1 FROM job_variants jv "
            "                WHERE jv.job_posting_id = jp.id) "
            "        OR EXISTS (SELECT 1 FROM applications a "
            "                   WHERE a.job_posting_id = jp.id) "
            "        OR EXISTS (SELECT 1 FROM cover_letters cl "
            "                   WHERE cl.job_posting_id = jp.id)"
            "    )"
            ") THEN "
            "    RAISE EXCEPTION "
            "        'Orphaned job_postings with dependent children found "
            "        — manual resolution required before downgrade'; "
            "END IF; END $$"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM job_postings "
            "WHERE persona_id IS NULL "
            "AND NOT EXISTS ("
            "    SELECT 1 FROM persona_jobs pj "
            "    WHERE pj.job_posting_id = job_postings.id"
            ")"
        )
    )

    # Make persona_id NOT NULL now that backfill is complete
    op.alter_column("job_postings", "persona_id", nullable=False)

    # ===================================================================
    # Re-add FK and CHECK constraints
    # ===================================================================
    op.create_foreign_key(
        "job_postings_persona_id_fkey",
        "job_postings",
        "personas",
        ["persona_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_jobposting_status",
        "job_postings",
        "status IN ('Discovered', 'Dismissed', 'Applied', 'Expired')",
    )
    op.create_check_constraint(
        "ck_jobposting_fit_score",
        "job_postings",
        "fit_score >= 0 AND fit_score <= 100 OR fit_score IS NULL",
    )
    op.create_check_constraint(
        "ck_jobposting_stretch_score",
        "job_postings",
        "stretch_score >= 0 AND stretch_score <= 100 OR stretch_score IS NULL",
    )

    # ===================================================================
    # Restore persona-scoped indexes
    # ===================================================================
    op.create_index(
        "idx_job_postings_persona_id",
        "job_postings",
        ["persona_id"],
    )
    op.create_index(
        "idx_job_postings_persona_id_status",
        "job_postings",
        ["persona_id", "status"],
    )
    op.create_index(
        "idx_job_postings_persona_id_fit_score",
        "job_postings",
        ["persona_id"],
        postgresql_where=sa.text("fit_score IS NOT NULL"),
    )

    # ===================================================================
    # Remove persona_job_id from applications
    # ===================================================================
    op.drop_constraint(
        "fk_applications_persona_job_id", "applications", type_="foreignkey"
    )
    op.drop_column("applications", "persona_job_id")
