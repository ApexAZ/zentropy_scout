"""Create cleanup functions for data retention.

Revision ID: 007_cleanup_functions
Revises: 006_tier5_timeline_event
Create Date: 2026-01-26

REQ-005 §7: Cleanup Jobs
- Orphan PDF cleanup (daily): 7 days
- PersonaChangeFlag cleanup (daily): 30 days after resolution
- Hard delete archived (weekly): 180 days
- Hard delete expired jobs (weekly): 180 days, unless favorited
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_cleanup_functions"
down_revision: str | None = "006_tier5_timeline_event"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # CLEANUP FUNCTION 1: Orphan PDFs (Daily)
    # SubmittedResumePDF and SubmittedCoverLetterPDF with no application link
    # Retention: 7 days
    # =========================================================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_orphan_pdfs()
        RETURNS TABLE(deleted_resume_pdfs BIGINT, deleted_cover_letter_pdfs BIGINT)
        LANGUAGE plpgsql
        AS $$
        DECLARE
            resume_count BIGINT;
            cover_letter_count BIGINT;
        BEGIN
            -- Delete orphan resume PDFs older than 7 days
            WITH deleted AS (
                DELETE FROM submitted_resume_pdfs
                WHERE application_id IS NULL
                  AND generated_at < now() - interval '7 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO resume_count FROM deleted;

            -- Delete orphan cover letter PDFs older than 7 days
            WITH deleted AS (
                DELETE FROM submitted_cover_letter_pdfs
                WHERE application_id IS NULL
                  AND generated_at < now() - interval '7 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO cover_letter_count FROM deleted;

            deleted_resume_pdfs := resume_count;
            deleted_cover_letter_pdfs := cover_letter_count;
            RETURN NEXT;
        END;
        $$;

        COMMENT ON FUNCTION cleanup_orphan_pdfs() IS
            'REQ-005 §7: Daily cleanup of orphan PDFs not linked to applications (7-day retention)';
    """
    )

    # =========================================================================
    # CLEANUP FUNCTION 2: Resolved PersonaChangeFlags (Daily)
    # Retention: 30 days after resolution
    # =========================================================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_resolved_change_flags()
        RETURNS BIGINT
        LANGUAGE plpgsql
        AS $$
        DECLARE
            deleted_count BIGINT;
        BEGIN
            WITH deleted AS (
                DELETE FROM persona_change_flags
                WHERE status = 'Resolved'
                  AND resolved_at < now() - interval '30 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO deleted_count FROM deleted;

            RETURN deleted_count;
        END;
        $$;

        COMMENT ON FUNCTION cleanup_resolved_change_flags() IS
            'REQ-005 §7: Daily cleanup of resolved PersonaChangeFlags (30-day retention after resolution)';
    """
    )

    # =========================================================================
    # CLEANUP FUNCTION 3: Hard Delete Archived Records (Weekly)
    # JobVariant and CoverLetter archived for 180+ days
    # =========================================================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_archived_records()
        RETURNS TABLE(deleted_job_variants BIGINT, deleted_cover_letters BIGINT)
        LANGUAGE plpgsql
        AS $$
        DECLARE
            variant_count BIGINT;
            letter_count BIGINT;
        BEGIN
            -- Delete archived job variants older than 180 days
            WITH deleted AS (
                DELETE FROM job_variants
                WHERE archived_at IS NOT NULL
                  AND archived_at < now() - interval '180 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO variant_count FROM deleted;

            -- Delete archived cover letters older than 180 days
            WITH deleted AS (
                DELETE FROM cover_letters
                WHERE archived_at IS NOT NULL
                  AND archived_at < now() - interval '180 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO letter_count FROM deleted;

            deleted_job_variants := variant_count;
            deleted_cover_letters := letter_count;
            RETURN NEXT;
        END;
        $$;

        COMMENT ON FUNCTION cleanup_archived_records() IS
            'REQ-005 §7: Weekly hard delete of archived JobVariants and CoverLetters (180-day retention)';
    """
    )

    # =========================================================================
    # CLEANUP FUNCTION 4: Hard Delete Expired/Dismissed Jobs (Weekly)
    # JobPosting with status Expired or Dismissed, not favorited
    # Retention: 180 days
    # =========================================================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
        RETURNS BIGINT
        LANGUAGE plpgsql
        AS $$
        DECLARE
            deleted_count BIGINT;
        BEGIN
            -- Note: Favorited jobs are protected from deletion
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
        $$;

        COMMENT ON FUNCTION cleanup_expired_jobs() IS
            'REQ-005 §7: Weekly hard delete of expired/dismissed JobPostings (180-day retention, favorites protected)';
    """
    )

    # =========================================================================
    # MASTER CLEANUP FUNCTION: Run all cleanups
    # Convenience function to run all cleanup jobs at once
    # =========================================================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION run_all_cleanups()
        RETURNS TABLE(
            orphan_resume_pdfs BIGINT,
            orphan_cover_letter_pdfs BIGINT,
            resolved_change_flags BIGINT,
            archived_job_variants BIGINT,
            archived_cover_letters BIGINT,
            expired_jobs BIGINT
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            pdf_result RECORD;
            flags_count BIGINT;
            archived_result RECORD;
            jobs_count BIGINT;
        BEGIN
            -- Run orphan PDF cleanup
            SELECT * INTO pdf_result FROM cleanup_orphan_pdfs();

            -- Run change flags cleanup
            SELECT cleanup_resolved_change_flags() INTO flags_count;

            -- Run archived records cleanup
            SELECT * INTO archived_result FROM cleanup_archived_records();

            -- Run expired jobs cleanup
            SELECT cleanup_expired_jobs() INTO jobs_count;

            -- Return all results
            orphan_resume_pdfs := pdf_result.deleted_resume_pdfs;
            orphan_cover_letter_pdfs := pdf_result.deleted_cover_letter_pdfs;
            resolved_change_flags := flags_count;
            archived_job_variants := archived_result.deleted_job_variants;
            archived_cover_letters := archived_result.deleted_cover_letters;
            expired_jobs := jobs_count;
            RETURN NEXT;
        END;
        $$;

        COMMENT ON FUNCTION run_all_cleanups() IS
            'REQ-005 §7: Master function to run all cleanup jobs and return deletion counts';
    """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS run_all_cleanups()")
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_jobs()")
    op.execute("DROP FUNCTION IF EXISTS cleanup_archived_records()")
    op.execute("DROP FUNCTION IF EXISTS cleanup_resolved_change_flags()")
    op.execute("DROP FUNCTION IF EXISTS cleanup_orphan_pdfs()")
