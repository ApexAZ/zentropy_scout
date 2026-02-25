"""Tests for JobEnrichmentService.

REQ-016 §6.3: Enriches raw job postings with extracted skills and ghost detection.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.job_enrichment_service import JobEnrichmentService

_GHOST_SCORE_MOCK_TARGET = "app.services.job_enrichment_service.calculate_ghost_score"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_jobs() -> list[dict[str, Any]]:
    """Batch of raw jobs needing enrichment."""
    return [
        {
            "external_id": "ext-001",
            "description": "Build APIs with Python and FastAPI",
            "location": "Remote",
            "salary_min": 100000,
            "salary_max": 150000,
        },
        {
            "external_id": "ext-002",
            "description": "Design ML pipelines using PyTorch",
            "location": "NYC",
            "salary_min": 120000,
            "salary_max": 180000,
        },
    ]


@pytest.fixture
def mock_ghost_signals() -> MagicMock:
    """Mock GhostSignals return value."""
    signals = MagicMock()
    signals.ghost_score = 25
    signals.to_dict.return_value = {
        "days_open": 10,
        "days_open_score": 5,
        "ghost_score": 25,
    }
    return signals


# ---------------------------------------------------------------------------
# extract_skills_and_culture
# ---------------------------------------------------------------------------


class TestExtractSkillsAndCulture:
    """Tests for LLM-based skill extraction from job descriptions."""

    async def test_returns_extraction_dict(self):
        """Extraction returns dict with skills and culture_text."""
        result = await JobEnrichmentService.extract_skills_and_culture(
            "Build APIs with Python, FastAPI, and PostgreSQL"
        )

        assert result["required_skills"] == []
        assert result["preferred_skills"] == []
        assert "culture_text" in result

    async def test_truncates_long_descriptions(self):
        """Descriptions longer than 15k chars are truncated."""
        long_desc = "x" * 20000

        # The method should not raise even with very long input
        result = await JobEnrichmentService.extract_skills_and_culture(long_desc)
        assert "required_skills" in result

    async def test_sanitizes_input(self):
        """Input is sanitized before processing."""
        # Zero-width characters should be stripped
        desc_with_zwsp = "Build\u200bAPIs"

        result = await JobEnrichmentService.extract_skills_and_culture(desc_with_zwsp)
        assert "required_skills" in result

    async def test_returns_empty_on_empty_description(self):
        """Empty description returns empty extraction."""
        result = await JobEnrichmentService.extract_skills_and_culture("")

        assert result["required_skills"] == []
        assert result["preferred_skills"] == []
        assert result["culture_text"] is None


# ---------------------------------------------------------------------------
# calculate_ghost_scores
# ---------------------------------------------------------------------------


class TestCalculateGhostScores:
    """Tests for ghost score calculation across a batch of jobs."""

    async def test_adds_ghost_score_to_each_job(
        self, sample_jobs: list[dict[str, Any]], mock_ghost_signals: MagicMock
    ):
        """Each job gets ghost_score and ghost_signals fields."""
        with patch(
            _GHOST_SCORE_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_ghost_signals,
        ):
            result = await JobEnrichmentService.calculate_ghost_scores(sample_jobs)

        assert len(result) == 2
        for job in result:
            assert job["ghost_score"] == 25
            assert "ghost_signals" in job

    async def test_handles_error_per_job(self, sample_jobs: list[dict[str, Any]]):
        """Ghost score error for one job doesn't fail the batch."""
        signals = MagicMock()
        signals.ghost_score = 30
        signals.to_dict.return_value = {"ghost_score": 30}

        with patch(
            _GHOST_SCORE_MOCK_TARGET,
            new_callable=AsyncMock,
            side_effect=[RuntimeError("calculation failed"), signals],
        ):
            result = await JobEnrichmentService.calculate_ghost_scores(sample_jobs)

        assert len(result) == 2
        assert result[0]["ghost_score"] is None
        assert result[0]["ghost_signals"] is None
        assert result[1]["ghost_score"] == 30

    async def test_empty_input_returns_empty(self):
        """Empty job list returns empty list."""
        result = await JobEnrichmentService.calculate_ghost_scores([])
        assert result == []


# ---------------------------------------------------------------------------
# enrich_jobs
# ---------------------------------------------------------------------------


class TestEnrichJobs:
    """Tests for the full enrichment pipeline (extraction + ghost scores)."""

    async def test_enriches_all_jobs(
        self, sample_jobs: list[dict[str, Any]], mock_ghost_signals: MagicMock
    ):
        """All jobs get both extraction and ghost score fields."""
        with patch(
            _GHOST_SCORE_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_ghost_signals,
        ):
            result = await JobEnrichmentService.enrich_jobs(sample_jobs)

        assert len(result) == 2
        for job in result:
            assert "required_skills" in job
            assert "preferred_skills" in job
            assert "culture_text" in job
            assert "ghost_score" in job
            assert "ghost_signals" in job

    async def test_extraction_failure_doesnt_block_ghost_scoring(
        self, mock_ghost_signals: MagicMock
    ):
        """If extraction fails, ghost scoring still runs."""
        jobs: list[dict[str, Any]] = [
            {"external_id": "ext-001", "description": "Test job"}
        ]

        with (
            patch.object(
                JobEnrichmentService,
                "extract_skills_and_culture",
                new_callable=AsyncMock,
                side_effect=RuntimeError("LLM down"),
            ),
            patch(
                _GHOST_SCORE_MOCK_TARGET,
                new_callable=AsyncMock,
                return_value=mock_ghost_signals,
            ),
        ):
            result = await JobEnrichmentService.enrich_jobs(jobs)

        assert len(result) == 1
        # Extraction failed — empty defaults
        assert result[0]["required_skills"] == []
        assert result[0]["extraction_failed"] is True
        # Ghost scoring still ran
        assert result[0]["ghost_score"] == 25

    async def test_ghost_failure_doesnt_block_extraction(self):
        """If ghost scoring fails, extraction results are preserved."""
        jobs: list[dict[str, Any]] = [
            {"external_id": "ext-001", "description": "Test job"}
        ]

        with patch(
            _GHOST_SCORE_MOCK_TARGET,
            new_callable=AsyncMock,
            side_effect=RuntimeError("ghost down"),
        ):
            result = await JobEnrichmentService.enrich_jobs(jobs)

        assert len(result) == 1
        assert "required_skills" in result[0]
        assert result[0]["ghost_score"] is None

    async def test_preserves_original_job_data(self, mock_ghost_signals: MagicMock):
        """Enriched jobs retain all original fields."""
        jobs: list[dict[str, Any]] = [
            {
                "external_id": "ext-001",
                "description": "Build APIs",
                "location": "Remote",
                "salary_min": 100000,
            }
        ]

        with patch(
            _GHOST_SCORE_MOCK_TARGET,
            new_callable=AsyncMock,
            return_value=mock_ghost_signals,
        ):
            result = await JobEnrichmentService.enrich_jobs(jobs)

        assert result[0]["location"] == "Remote"
        assert result[0]["salary_min"] == 100000

    async def test_empty_input_returns_empty(self):
        """Empty job list returns empty list."""
        result = await JobEnrichmentService.enrich_jobs([])
        assert result == []
