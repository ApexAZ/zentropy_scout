"""Update cleanup_expired_jobs() for shared job pool schema.

Revision ID: 015_update_cleanup_functions
Revises: 014_drop_per_user_columns
Create Date: 2026-02-21

Migration 014 dropped status, is_favorite from job_postings. The
cleanup_expired_jobs() stored procedure (created in 007) references
those columns and must be updated.

New logic: delete job_postings where is_active=false, old enough
(180 days), and not favorited by any persona via persona_jobs.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "015_update_cleanup_functions"
down_revision: str | None = "014_drop_per_user_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Replace cleanup_expired_jobs() to use new schema
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
        RETURNS BIGINT
        LANGUAGE plpgsql
        AS $$
        DECLARE
            deleted_count BIGINT;
        BEGIN
            -- Shared pool: delete inactive job_postings older than 180 days
            -- that are not favorited by any persona.
            -- Must delete persona_jobs first (FK RESTRICT on job_posting_id).
            CREATE TEMP TABLE _expired_job_ids ON COMMIT DROP AS
            SELECT id FROM job_postings
            WHERE is_active = false
              AND updated_at < now() - interval '180 days'
              AND NOT EXISTS (
                  SELECT 1 FROM persona_jobs
                  WHERE persona_jobs.job_posting_id = job_postings.id
                    AND persona_jobs.is_favorite = true
              )
            FOR UPDATE;

            DELETE FROM persona_jobs
            WHERE job_posting_id IN (SELECT id FROM _expired_job_ids);

            WITH deleted AS (
                DELETE FROM job_postings
                WHERE id IN (SELECT id FROM _expired_job_ids)
                RETURNING id
            )
            SELECT COUNT(*) INTO deleted_count FROM deleted;

            RETURN deleted_count;
        END;
        $$
    """
    )
    op.execute(
        """
        COMMENT ON FUNCTION cleanup_expired_jobs() IS
            'REQ-005 §7: Weekly hard delete of inactive job_postings (180-day retention, favorites protected via persona_jobs)'
    """
    )


def downgrade() -> None:
    # Restore original function referencing job_postings columns
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
        RETURNS BIGINT
        LANGUAGE plpgsql
        AS $$
        DECLARE
            deleted_count BIGINT;
        BEGIN
            WITH deleted AS (
                DELETE FROM job_postings
                WHERE status IN ('Expired', 'Dismissed')
                  AND updated_at < now() - interval '180 days'
                  AND is_favorite = false
                RETURNING id
            )
            SELECT COUNT(*) INTO deleted_count FROM deleted;

            RETURN deleted_count;
        END;
        $$
    """
    )
    op.execute(
        """
        COMMENT ON FUNCTION cleanup_expired_jobs() IS
            'REQ-005 §7: Weekly hard delete of expired/dismissed JobPostings (180-day retention, favorites protected)'
    """
    )
