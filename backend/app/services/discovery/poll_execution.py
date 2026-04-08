"""Per-persona poll execution for the scheduler.

REQ-034 §7.2: Executes a single persona's poll cycle — resolves enabled
sources, builds SearchParams from the persona's SearchProfile, runs the
fetch pipeline, and updates PollingConfiguration timestamps.

Each call opens its own DB session for fault isolation: one persona's
failure does not affect other polls running concurrently.

Coordinates with:
  - discovery/job_fetch_service.py — imports JobFetchService, PollResult
  - discovery/search_profile_service.py — imports build_search_params
  - repositories/search_profile_repository.py — imports SearchProfileRepository
  - models/persona.py — Persona (remote_preference, home_city for SearchParams)
  - models/job_source.py — PollingConfiguration, UserSourcePreference, JobSource

Called by: discovery/poll_scheduler_worker.py (PollSchedulerWorker._poll_persona).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.adapters.sources.base import SearchParams
from app.models.job_source import JobSource, PollingConfiguration, UserSourcePreference
from app.models.persona import Persona
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import SearchBucketSchema
from app.services.discovery.job_fetch_service import JobFetchService, PollResult
from app.services.discovery.search_profile_service import build_search_params

if TYPE_CHECKING:
    from app.services.discovery.poll_scheduler_worker import _DueItem

logger = logging.getLogger(__name__)


async def execute_persona_poll(
    session_factory: async_sessionmaker[AsyncSession],
    item: _DueItem,
) -> PollResult:
    """Execute a single persona's poll cycle.

    Opens its own session for fault isolation — one persona's failure
    does not affect others.

    Args:
        session_factory: Async session factory for DB access.
        item: Due persona metadata from the scheduler query.

    Returns:
        PollResult from JobFetchService.run_poll().
    """
    async with session_factory() as db:
        enabled_sources = await _resolve_enabled_sources(db, item.persona_id)

        if not enabled_sources:
            logger.warning(
                "Persona %s has no enabled sources; skipping poll",
                item.persona_id,
            )
            now = datetime.now(UTC)
            return PollResult(
                processed_jobs=[],
                new_job_count=0,
                existing_job_count=0,
                last_polled_at=now,
                next_poll_at=now,
            )

        search_params_list = await _build_persona_search_params(db, item)

        service = JobFetchService(db, item.user_id, item.persona_id)
        result = await service.run_poll(
            enabled_sources=enabled_sources,
            polling_frequency=item.polling_frequency,
            search_params_list=search_params_list,
        )

        # Update PollingConfiguration with new timestamps
        config_stmt = select(PollingConfiguration).where(
            PollingConfiguration.persona_id == item.persona_id
        )
        config_result = await db.execute(config_stmt)
        config = config_result.scalar_one_or_none()
        if config:
            config.last_poll_at = result.last_polled_at
            config.next_poll_at = result.next_poll_at

        await db.commit()
        return result


async def _resolve_enabled_sources(db: AsyncSession, persona_id: UUID) -> list[str]:
    """Query enabled source names for a persona.

    Args:
        db: Async database session.
        persona_id: UUID of the persona.

    Returns:
        List of source name strings (e.g., ["Adzuna", "RemoteOK"]).
    """
    stmt = (
        select(JobSource.source_name)
        .join(
            UserSourcePreference,
            UserSourcePreference.source_id == JobSource.id,
        )
        .where(
            UserSourcePreference.persona_id == persona_id,
            UserSourcePreference.is_enabled == true(),
        )
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def _build_persona_search_params(
    db: AsyncSession,
    item: _DueItem,
) -> list[SearchParams] | None:
    """Build SearchParams list from the persona's SearchProfile buckets.

    Returns None when no approved/current profile exists — run_poll()
    falls back to a single fetch with empty keywords.

    Args:
        db: Async database session.
        item: Due persona metadata.

    Returns:
        List of SearchParams or None if no usable profile.
    """
    profile = await SearchProfileRepository.get_by_persona_id(db, item.persona_id)
    if profile is None or profile.is_stale:
        return None

    buckets: list[SearchBucketSchema] = []
    for bucket_dict in profile.fit_searches + profile.stretch_searches:
        try:
            buckets.append(SearchBucketSchema.model_validate(bucket_dict))
        except ValueError:
            logger.warning(
                "Invalid bucket in SearchProfile for persona %s; skipping",
                item.persona_id,
            )

    if not buckets:
        return None

    # Load Persona for build_search_params (needs remote_preference, home_city)
    persona = await db.get(
        Persona,
        item.persona_id,
        options=[selectinload(Persona.skills)],
    )
    if persona is None:
        return None

    return [
        build_search_params(bucket, persona, item.last_poll_at) for bucket in buckets
    ]
