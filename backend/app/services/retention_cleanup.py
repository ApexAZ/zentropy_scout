"""Retention cleanup service.

REQ-002 §5.1, REQ-005 §7: Application-layer invocation of database
cleanup functions for data retention enforcement.

Four cleanup jobs:
- Orphan PDF cleanup (daily): 7-day retention
- PersonaChangeFlag cleanup (daily): 30-day retention after resolution
- Archived records hard delete (weekly): 180-day retention
- Expired/dismissed jobs hard delete (weekly): 180-day, favorites protected

SINGLE-TENANT: All cleanup functions operate globally (no user/persona
scoping). Must add persona_id filtering before multi-tenancy.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrphanPdfCleanupResult:
    """Result of orphan PDF cleanup.

    Attributes:
        deleted_resume_pdfs: Number of orphan resume PDFs deleted.
        deleted_cover_letter_pdfs: Number of orphan cover letter PDFs deleted.
    """

    deleted_resume_pdfs: int
    deleted_cover_letter_pdfs: int


@dataclass(frozen=True)
class ArchivedRecordsCleanupResult:
    """Result of archived records hard delete.

    Attributes:
        deleted_job_variants: Number of archived job variants hard deleted.
        deleted_cover_letters: Number of archived cover letters hard deleted.
    """

    deleted_job_variants: int
    deleted_cover_letters: int


@dataclass(frozen=True)
class AllCleanupResult:
    """Aggregate result of all cleanup jobs.

    Attributes:
        orphan_resume_pdfs: Orphan resume PDFs deleted.
        orphan_cover_letter_pdfs: Orphan cover letter PDFs deleted.
        resolved_change_flags: Resolved PersonaChangeFlags deleted.
        archived_job_variants: Archived job variants hard deleted.
        archived_cover_letters: Archived cover letters hard deleted.
        expired_jobs: Expired/dismissed job postings hard deleted.
    """

    orphan_resume_pdfs: int
    orphan_cover_letter_pdfs: int
    resolved_change_flags: int
    archived_job_variants: int
    archived_cover_letters: int
    expired_jobs: int


class CleanupError(APIError):
    """Raised when a cleanup operation fails at the database level."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="CLEANUP_ERROR",
            message=message,
            status_code=500,
        )


async def cleanup_orphan_pdfs(db: AsyncSession) -> OrphanPdfCleanupResult:
    """Delete orphan PDFs not linked to an application after 7 days.

    REQ-005 §7: SubmittedResumePDF and SubmittedCoverLetterPDF with
    application_id IS NULL and generated_at older than 7 days.

    Args:
        db: Database session.

    Returns:
        OrphanPdfCleanupResult with deletion counts.

    Raises:
        CleanupError: If the database operation fails.
    """
    try:
        result = await db.execute(text("SELECT * FROM cleanup_orphan_pdfs()"))
        row = result.one()
        return OrphanPdfCleanupResult(
            deleted_resume_pdfs=row.deleted_resume_pdfs,
            deleted_cover_letter_pdfs=row.deleted_cover_letter_pdfs,
        )
    except SQLAlchemyError as exc:
        logger.error("Orphan PDF cleanup failed: %s", exc)
        raise CleanupError("Orphan PDF cleanup failed") from exc


async def cleanup_resolved_change_flags(db: AsyncSession) -> int:
    """Delete resolved PersonaChangeFlags older than 30 days.

    REQ-005 §7: PersonaChangeFlags with status='Resolved' and
    resolved_at older than 30 days.

    Args:
        db: Database session.

    Returns:
        Number of resolved flags deleted.

    Raises:
        CleanupError: If the database operation fails.
    """
    try:
        result = await db.execute(
            text("SELECT cleanup_resolved_change_flags() AS count")
        )
        return int(result.scalar_one())
    except SQLAlchemyError as exc:
        logger.error("Resolved change flag cleanup failed: %s", exc)
        raise CleanupError("Resolved change flag cleanup failed") from exc


async def cleanup_archived_records(db: AsyncSession) -> ArchivedRecordsCleanupResult:
    """Hard delete archived JobVariants and CoverLetters older than 180 days.

    REQ-005 §7: Records with archived_at older than 180 days.

    Args:
        db: Database session.

    Returns:
        ArchivedRecordsCleanupResult with deletion counts.

    Raises:
        CleanupError: If the database operation fails.
    """
    try:
        result = await db.execute(text("SELECT * FROM cleanup_archived_records()"))
        row = result.one()
        return ArchivedRecordsCleanupResult(
            deleted_job_variants=row.deleted_job_variants,
            deleted_cover_letters=row.deleted_cover_letters,
        )
    except SQLAlchemyError as exc:
        logger.error("Archived records cleanup failed: %s", exc)
        raise CleanupError("Archived records cleanup failed") from exc


async def cleanup_expired_jobs(db: AsyncSession) -> int:
    """Hard delete expired/dismissed JobPostings older than 180 days.

    REQ-005 §7: JobPostings with status IN ('Expired', 'Dismissed'),
    updated_at older than 180 days, and is_favorite=false.
    Favorited jobs are protected from deletion.

    Args:
        db: Database session.

    Returns:
        Number of expired job postings deleted.

    Raises:
        CleanupError: If the database operation fails.
    """
    try:
        result = await db.execute(text("SELECT cleanup_expired_jobs() AS count"))
        return int(result.scalar_one())
    except SQLAlchemyError as exc:
        logger.error("Expired jobs cleanup failed: %s", exc)
        raise CleanupError("Expired jobs cleanup failed") from exc


async def run_all_cleanups(db: AsyncSession) -> AllCleanupResult:
    """Run all four cleanup jobs and return aggregate results.

    REQ-005 §7: Master function that invokes all cleanup jobs.

    Args:
        db: Database session.

    Returns:
        AllCleanupResult with counts from all cleanup categories.

    Raises:
        CleanupError: If the database operation fails.
    """
    try:
        result = await db.execute(text("SELECT * FROM run_all_cleanups()"))
        row = result.one()
        return AllCleanupResult(
            orphan_resume_pdfs=row.orphan_resume_pdfs,
            orphan_cover_letter_pdfs=row.orphan_cover_letter_pdfs,
            resolved_change_flags=row.resolved_change_flags,
            archived_job_variants=row.archived_job_variants,
            archived_cover_letters=row.archived_cover_letters,
            expired_jobs=row.expired_jobs,
        )
    except SQLAlchemyError as exc:
        logger.error("Run all cleanups failed: %s", exc)
        raise CleanupError("Run all cleanups failed") from exc
