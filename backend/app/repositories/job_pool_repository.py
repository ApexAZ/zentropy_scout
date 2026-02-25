"""Repository for shared job pool operations.

REQ-016 §6.4: Pool check, save, link, and source resolution.
Standalone repository for shared pool operations.
"""

import hashlib
import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_source import JobSource
from app.repositories.job_posting_repository import JobPostingRepository
from app.services.global_dedup_service import deduplicate_and_save

logger = logging.getLogger(__name__)

# Only auto-create JobSource rows for known adapters — prevents
# untrusted source names from polluting the job_sources table.
_KNOWN_SOURCE_NAMES = frozenset({"Adzuna", "RemoteOK", "TheMuse", "USAJobs"})


def _compute_description_hash(text: str) -> str:
    """Compute SHA-256 hash of description text for dedup lookup.

    Args:
        text: Job description text.

    Returns:
        64-character hex digest string.
    """
    return hashlib.sha256(text.encode()).hexdigest()


def _build_dedup_job_data(
    job: dict[str, Any],
    source_id: uuid.UUID,
) -> dict[str, Any]:
    """Transform a raw job dict into global dedup service input format.

    Args:
        job: Raw job dict from source adapters or the fetch pipeline.
        source_id: Resolved UUID of the job source.

    Returns:
        Dict compatible with deduplicate_and_save() job_data parameter.
    """
    description = job.get("description", "")
    return {
        "source_id": source_id,
        "job_title": job.get("title", ""),
        "company_name": job.get("company", ""),
        "description": description,
        "description_hash": _compute_description_hash(description),
        "first_seen_date": date.today(),
        "external_id": job.get("external_id"),
        "source_url": job.get("source_url"),
        "location": job.get("location"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "posted_date": job.get("posted_date"),
        "culture_text": job.get("culture_text"),
        "ghost_score": job.get("ghost_score"),
        "ghost_signals": job.get("ghost_signals"),
        "raw_text": job.get("description"),
    }


class JobPoolRepository:
    """Repository for shared job pool check, save, and link operations.

    Orchestrates pool lookups via JobPostingRepository and saves via
    the global dedup service. All methods are static — no instance state.
    Pass an AsyncSession for every call so the caller controls
    transaction boundaries.
    """

    @staticmethod
    async def check_job_in_pool(
        db: AsyncSession,
        job: dict[str, Any],
        source_id: uuid.UUID,
    ) -> tuple[bool, dict[str, Any]]:
        """Check if a single job exists in the shared pool.

        Two-tier lookup: source_id + external_id first, then description_hash.

        Args:
            db: Async database session.
            job: Job dict with external_id and description.
            source_id: Resolved source UUID.

        Returns:
            (is_existing, enriched_job) where enriched_job has source_id
            and optionally pool_job_posting_id if found in pool.
        """
        external_id = job.get("external_id", "")

        # Tier 1: source_id + external_id
        existing = None
        if external_id:
            existing = await JobPostingRepository.get_by_source_and_external_id(
                db, source_id=source_id, external_id=external_id
            )

        # Tier 2: description_hash
        if existing is None:
            description = job.get("description", "")
            if description:
                desc_hash = _compute_description_hash(description)
                existing = await JobPostingRepository.get_by_description_hash(
                    db, desc_hash
                )

        if existing is not None:
            logger.debug(
                "Job %s already in pool (id=%s)",
                external_id or "(no ext_id)",
                existing.id,
            )
            return True, {
                **job,
                "pool_job_posting_id": str(existing.id),
                "source_id": str(source_id),
            }

        return False, {**job, "source_id": str(source_id)}

    @staticmethod
    async def resolve_source_id(
        db: AsyncSession,
        source_name: str,
    ) -> uuid.UUID | None:
        """Look up or create a JobSource by name.

        Only auto-creates sources for names in _KNOWN_SOURCE_NAMES to
        prevent untrusted input from creating arbitrary source rows.

        Args:
            db: Async database session.
            source_name: Source name (e.g., "Adzuna").

        Returns:
            UUID of the source, or None if unknown and not in allowlist.
        """
        result = await db.execute(
            select(JobSource).where(JobSource.source_name == source_name)
        )
        source = result.scalar_one_or_none()
        if source is not None:
            return source.id

        # Only auto-create for known adapter sources
        if source_name not in _KNOWN_SOURCE_NAMES:
            logger.warning("Unknown source name, cannot auto-create: %s", source_name)
            return None

        source = JobSource(
            source_name=source_name,
            source_type="API",
            description=f"Jobs from {source_name}",
        )
        db.add(source)
        await db.flush()
        await db.refresh(source)
        return source.id

    @staticmethod
    async def save_job_to_pool(
        db: AsyncSession,
        job: dict[str, Any],
        persona_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """Save a single new job to the shared pool via dedup pipeline.

        Args:
            db: Async database session.
            job: Job dict with source_id and dedup-ready fields.
            persona_id: Persona UUID for the persona_jobs link.
            user_id: User UUID for ownership.

        Returns:
            Job posting ID string, or None on failure.
        """
        try:
            source_id = uuid.UUID(job["source_id"])
            job_data = _build_dedup_job_data(job, source_id)
            outcome = await deduplicate_and_save(
                db,
                job_data=job_data,
                persona_id=persona_id,
                user_id=user_id,
                discovery_method="scouter",
            )
            logger.debug(
                "Saved job %s: action=%s, id=%s",
                job.get("external_id"),
                outcome.action,
                outcome.job_posting.id,
            )
            return str(outcome.job_posting.id)
        except (ValueError, KeyError) as e:
            logger.warning("Invalid job data for %s: %s", job.get("external_id"), e)
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to save job %s: %s", job.get("external_id"), e)
            return None

    @staticmethod
    async def link_existing_job(
        db: AsyncSession,
        job: dict[str, Any],
        persona_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """Create persona_jobs link for an existing pool job.

        Args:
            db: Async database session.
            job: Job dict with pool_job_posting_id and source_id.
            persona_id: Persona UUID for the persona_jobs link.
            user_id: User UUID for ownership.

        Returns:
            Pool job posting ID string, or None on failure.
        """
        try:
            source_id = uuid.UUID(job["source_id"])
            job_data = _build_dedup_job_data(job, source_id)
            await deduplicate_and_save(
                db,
                job_data=job_data,
                persona_id=persona_id,
                user_id=user_id,
                discovery_method="scouter",
            )
            return job.get("pool_job_posting_id")
        except (ValueError, KeyError) as e:
            logger.warning(
                "Invalid data for pool job %s: %s",
                job.get("pool_job_posting_id"),
                e,
            )
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Failed to link pool job %s: %s",
                job.get("pool_job_posting_id"),
                e,
            )
            return None
