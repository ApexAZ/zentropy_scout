"""Tests for JobPoolRepository save and link operations.

REQ-016 §6.4: Save-to-pool and link-existing-job via dedup pipeline.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.job_pool_repository import JobPoolRepository

_DEDUP_MOCK_TARGET = "app.repositories.job_pool_repository.deduplicate_and_save"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_job() -> dict[str, Any]:
    """Raw job dict as produced by source adapters."""
    return {
        "external_id": "ext-001",
        "title": "Software Engineer",
        "company": "Acme Corp",
        "description": "Build great software",
        "source_url": "https://example.com/job/1",
        "location": "Remote",
        "salary_min": 100000,
        "salary_max": 150000,
        "source_name": "Adzuna",
    }


# ---------------------------------------------------------------------------
# save_job_to_pool
# ---------------------------------------------------------------------------


class TestSaveJobToPool:
    """Tests for saving new jobs via dedup pipeline."""

    async def test_returns_job_posting_id_on_success(
        self, db_session: AsyncSession, sample_job: dict[str, Any]
    ):
        """Successful save returns the job posting ID string."""
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = uuid.uuid4()
        mock_outcome.action = "created"

        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ):
            sample_job["source_id"] = str(uuid.uuid4())
            result = await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, uuid.uuid4(), uuid.uuid4()
            )

        assert result == str(mock_outcome.job_posting.id)

    async def test_calls_dedup_with_scouter_discovery_method(
        self, db_session: AsyncSession, sample_job: dict[str, Any]
    ):
        """Dedup service is called with discovery_method='scouter'."""
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = uuid.uuid4()

        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ) as mock_dedup:
            sample_job["source_id"] = str(uuid.uuid4())
            persona_id = uuid.uuid4()
            user_id = uuid.uuid4()

            await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, persona_id, user_id
            )

            mock_dedup.assert_called_once()
            call_kwargs = mock_dedup.call_args.kwargs
            assert call_kwargs["discovery_method"] == "scouter"
            assert call_kwargs["persona_id"] == persona_id
            assert call_kwargs["user_id"] == user_id

    async def test_returns_none_on_value_error(
        self, db_session: AsyncSession, sample_job: dict[str, Any]
    ):
        """ValueError during save returns None."""
        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            side_effect=ValueError("bad data"),
        ):
            sample_job["source_id"] = str(uuid.uuid4())
            result = await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, uuid.uuid4(), uuid.uuid4()
            )

        assert result is None

    async def test_returns_none_on_unexpected_error(
        self, db_session: AsyncSession, sample_job: dict[str, Any]
    ):
        """Unexpected exception during save returns None."""
        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ):
            sample_job["source_id"] = str(uuid.uuid4())
            result = await JobPoolRepository.save_job_to_pool(
                db_session, sample_job, uuid.uuid4(), uuid.uuid4()
            )

        assert result is None


# ---------------------------------------------------------------------------
# link_existing_job
# ---------------------------------------------------------------------------


class TestLinkExistingJob:
    """Tests for linking existing pool jobs to a persona."""

    async def test_returns_pool_id_on_success(self, db_session: AsyncSession):
        """Successful link returns the pool_job_posting_id."""
        mock_outcome = MagicMock()

        pool_id = str(uuid.uuid4())
        job: dict[str, Any] = {
            "pool_job_posting_id": pool_id,
            "source_id": str(uuid.uuid4()),
            "description": "Existing job",
            "title": "Engineer",
            "company": "PoolCo",
        }

        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ):
            result = await JobPoolRepository.link_existing_job(
                db_session, job, uuid.uuid4(), uuid.uuid4()
            )

        assert result == pool_id

    async def test_returns_none_on_error(self, db_session: AsyncSession):
        """Error during linking returns None."""
        job: dict[str, Any] = {
            "pool_job_posting_id": str(uuid.uuid4()),
            "source_id": str(uuid.uuid4()),
            "description": "Existing job",
            "title": "Engineer",
            "company": "PoolCo",
        }

        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            side_effect=ValueError("bad link"),
        ):
            result = await JobPoolRepository.link_existing_job(
                db_session, job, uuid.uuid4(), uuid.uuid4()
            )

        assert result is None

    async def test_calls_dedup_with_scouter_method(self, db_session: AsyncSession):
        """Link uses scouter discovery method."""
        mock_outcome = MagicMock()
        job: dict[str, Any] = {
            "pool_job_posting_id": str(uuid.uuid4()),
            "source_id": str(uuid.uuid4()),
            "description": "Link test",
            "title": "Dev",
            "company": "LinkCo",
        }

        with patch(
            _DEDUP_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_outcome,
        ) as mock_dedup:
            await JobPoolRepository.link_existing_job(
                db_session, job, uuid.uuid4(), uuid.uuid4()
            )

            call_kwargs = mock_dedup.call_args.kwargs
            assert call_kwargs["discovery_method"] == "scouter"
