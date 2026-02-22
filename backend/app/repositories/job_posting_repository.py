"""Repository for JobPosting shared pool operations.

REQ-015 §6, §9: Global CRUD and dedup lookups for the shared job pool.
Job postings are Tier 0 — no per-user scoping at this level.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting

# Fields that may be updated via JobPostingRepository.update().
# Security: Never allow updating id, source_id, or created_at.
# - id: primary key, immutable
# - source_id: FK to job_sources, set at creation
# - created_at/updated_at: server-managed timestamps
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "external_id",
        "job_title",
        "company_name",
        "company_url",
        "source_url",
        "apply_url",
        "location",
        "work_model",
        "seniority_level",
        "salary_min",
        "salary_max",
        "salary_currency",
        "description",
        "culture_text",
        "requirements",
        "raw_text",
        "years_experience_min",
        "years_experience_max",
        "posted_date",
        "application_deadline",
        "first_seen_date",
        "last_verified_at",
        "expired_at",
        "ghost_signals",
        "ghost_score",
        "description_hash",
        "repost_count",
        "previous_posting_ids",
        "also_found_on",
        "is_active",
    }
)


class JobPostingRepository:
    """Stateless repository for shared pool JobPosting operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.

    WARNING — SYSTEM-ONLY: This repository operates on the shared job
    pool (Tier 0). Write operations (create, update, deactivate) are
    NOT user-scoped and must only be called from trusted internal code
    (surfacing worker, dedup pipeline, admin). Never expose these
    methods directly to user-facing API endpoints without an
    authorization guard.
    """

    @staticmethod
    async def get_by_id(
        db: AsyncSession, job_posting_id: uuid.UUID
    ) -> JobPosting | None:
        """Fetch a job posting by primary key.

        Args:
            db: Async database session.
            job_posting_id: UUID primary key.

        Returns:
            JobPosting if found, None otherwise.
        """
        return await db.get(JobPosting, job_posting_id)

    @staticmethod
    async def get_by_source_and_external_id(
        db: AsyncSession,
        *,
        source_id: uuid.UUID,
        external_id: str,
    ) -> JobPosting | None:
        """Fetch a job posting by source + external ID pair.

        REQ-015 §6 dedup step 1: Exact match on source_id + external_id.

        Args:
            db: Async database session.
            source_id: UUID of the job source.
            external_id: External ID from the source platform.

        Returns:
            JobPosting if found, None otherwise.
        """
        stmt = select(JobPosting).where(
            JobPosting.source_id == source_id,
            JobPosting.external_id == external_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_description_hash(
        db: AsyncSession, description_hash: str
    ) -> JobPosting | None:
        """Fetch a job posting by description hash.

        REQ-015 §6 dedup step 2: Content-based dedup via SHA-256 hash.

        Args:
            db: Async database session.
            description_hash: SHA-256 hash of the job description.

        Returns:
            JobPosting if found, None otherwise.
        """
        stmt = select(JobPosting).where(JobPosting.description_hash == description_hash)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        source_id: uuid.UUID,
        job_title: str,
        company_name: str,
        description: str,
        description_hash: str,
        first_seen_date: date,
        external_id: str | None = None,
        company_url: str | None = None,
        source_url: str | None = None,
        apply_url: str | None = None,
        location: str | None = None,
        work_model: str | None = None,
        seniority_level: str | None = None,
        salary_min: int | None = None,
        salary_max: int | None = None,
        salary_currency: str | None = None,
        culture_text: str | None = None,
        requirements: str | None = None,
        raw_text: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
    ) -> JobPosting:
        """Create a new job posting in the shared pool.

        Args:
            db: Async database session.
            source_id: FK to job_sources.
            job_title: Job title.
            company_name: Company name.
            description: Full job description.
            description_hash: SHA-256 hash for dedup.
            first_seen_date: Date the job was first discovered.
            external_id: External ID from source platform.
            company_url: Company website URL.
            source_url: URL where the job was found.
            apply_url: Direct application URL.
            location: Job location.
            work_model: Remote/Hybrid/Onsite.
            seniority_level: Entry/Mid/Senior/Lead/Executive.
            salary_min: Minimum salary.
            salary_max: Maximum salary.
            salary_currency: Currency code (e.g., USD).
            culture_text: Culture/values text.
            requirements: Requirements text.
            raw_text: Original raw text.
            years_experience_min: Minimum years experience.
            years_experience_max: Maximum years experience.

        Returns:
            Created JobPosting with database-generated fields populated.
        """
        job_posting = JobPosting(
            source_id=source_id,
            external_id=external_id,
            job_title=job_title,
            company_name=company_name,
            description=description,
            description_hash=description_hash,
            first_seen_date=first_seen_date,
            company_url=company_url,
            source_url=source_url,
            apply_url=apply_url,
            location=location,
            work_model=work_model,
            seniority_level=seniority_level,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            culture_text=culture_text,
            requirements=requirements,
            raw_text=raw_text,
            years_experience_min=years_experience_min,
            years_experience_max=years_experience_max,
        )
        db.add(job_posting)
        await db.flush()
        await db.refresh(job_posting)
        return job_posting

    @staticmethod
    async def update(
        db: AsyncSession,
        job_posting_id: uuid.UUID,
        **kwargs: str | int | bool | date | datetime | dict | list | None,
    ) -> JobPosting | None:
        """Update job posting fields.

        Only fields in _UPDATABLE_FIELDS are allowed. Unknown field names
        raise ValueError.

        Args:
            db: Async database session.
            job_posting_id: UUID of the job posting to update.
            **kwargs: Field names and values to update.

        Returns:
            Updated JobPosting if found, None if not found.

        Raises:
            ValueError: If an unknown field name is passed.
        """
        unknown = set(kwargs) - _UPDATABLE_FIELDS
        if unknown:
            msg = f"Unknown fields: {', '.join(sorted(unknown))}"
            raise ValueError(msg)

        job_posting = await db.get(JobPosting, job_posting_id)
        if job_posting is None:
            return None

        for field, value in kwargs.items():
            setattr(job_posting, field, value)

        await db.flush()
        await db.refresh(job_posting)
        return job_posting

    @staticmethod
    async def deactivate(
        db: AsyncSession, job_posting_id: uuid.UUID
    ) -> JobPosting | None:
        """Mark a job posting as inactive.

        Convenience method for setting is_active=False.

        Args:
            db: Async database session.
            job_posting_id: UUID of the job posting to deactivate.

        Returns:
            Updated JobPosting if found, None if not found.
        """
        return await JobPostingRepository.update(db, job_posting_id, is_active=False)
