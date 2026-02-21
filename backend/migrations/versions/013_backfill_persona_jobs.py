"""Backfill persona_jobs from existing job_postings data.

Revision ID: 013_backfill_persona_jobs
Revises: 012_persona_jobs
Create Date: 2026-02-21

REQ-015 §11 steps 4–5: Data-only migration (no DDL changes).

Step 4: Populate persona_jobs from existing job_postings per-user data.
        Maps 'Expired' status to 'Discovered' (expiry now tracked by
        is_active on the shared job_postings table).

Step 5: Set is_active = false for job_postings with status = 'Expired'.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "013_backfill_persona_jobs"
down_revision: str | None = "012_persona_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # Step 4: Backfill persona_jobs from existing job_postings (REQ-015 §11 step 4)
    # =========================================================================

    op.execute(
        text(
            """
            INSERT INTO persona_jobs (
                persona_id, job_posting_id, status, is_favorite,
                fit_score, stretch_score, failed_non_negotiables, score_details,
                dismissed_at, discovery_method, discovered_at, scored_at,
                created_at, updated_at
            )
            SELECT
                jp.persona_id,
                jp.id,
                CASE jp.status
                    WHEN 'Expired' THEN 'Discovered'
                    ELSE jp.status
                END,
                jp.is_favorite,
                jp.fit_score,
                jp.stretch_score,
                jp.failed_non_negotiables,
                jp.score_details,
                jp.dismissed_at,
                'scouter',
                jp.first_seen_date::timestamptz,
                CASE WHEN jp.fit_score IS NOT NULL THEN jp.updated_at END,
                jp.created_at,
                jp.updated_at
            FROM job_postings jp
            """
        )
    )

    # =========================================================================
    # Step 5: Backfill is_active on job_postings (REQ-015 §11 step 5)
    # =========================================================================

    op.execute(
        text(
            """
            UPDATE job_postings
            SET is_active = false
            WHERE status = 'Expired'
            """
        )
    )


def downgrade() -> None:
    # Reset is_active to true only for Expired rows that this migration set to false.
    # Safe: migration 013 is the only writer of is_active=false at this point
    # in the migration chain (is_active was added in 012 with DEFAULT true).
    op.execute(
        text(
            """
            UPDATE job_postings
            SET is_active = true
            WHERE status = 'Expired' AND is_active = false
            """
        )
    )

    # Remove all persona_jobs rows. Safe: no application code writes to this
    # table until a later release — only backfill data exists at this point.
    op.execute(text("DELETE FROM persona_jobs"))
