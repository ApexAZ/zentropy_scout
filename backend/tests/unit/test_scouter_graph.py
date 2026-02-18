"""Tests for the Scouter Agent LangGraph graph.

REQ-007 §15.3: Graph Spec — Scouter Agent

Tests verify:
1. Graph construction (nodes, edges, entry point)
2. Node function behaviors
3. Routing logic (conditional edges)
4. State transitions through the graph
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.scouter_graph import (
    calculate_ghost_score_node,
    check_new_jobs,
    create_scouter_graph,
    deduplicate_jobs_node,
    extract_skills_node,
    fetch_sources_node,
    get_enabled_sources_node,
    get_scouter_graph,
    invoke_strategist_node,
    merge_results_node,
    reset_scouter_graph,
    save_jobs_node,
    update_poll_state_node,
)
from app.services.scouter_errors import SourceError, SourceErrorType

# =============================================================================
# Graph Construction Tests
# =============================================================================


class TestScouterGraphConstruction:
    """Tests for Scouter graph construction and structure.

    REQ-007 §15.3: Graph must have correct nodes, edges, and entry point.
    """

    def test_graph_has_all_required_nodes_when_created(self) -> None:
        """Graph contains all nodes specified in REQ-007 §15.3."""
        graph = create_scouter_graph()

        # Verify all required nodes exist
        expected_nodes = [
            "get_enabled_sources",
            "fetch_sources",
            "merge_results",
            "deduplicate_jobs",
            "extract_skills",
            "calculate_ghost_score",
            "save_jobs",
            "invoke_strategist",
            "update_poll_state",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_graph_entry_point_is_get_enabled_sources_when_created(self) -> None:
        """Graph entry point is get_enabled_sources as per REQ-007 §15.3."""
        graph = create_scouter_graph()

        # WHY: LangGraph creates an edge from __start__ to the entry node.
        # Verify the entry point by checking for this edge in the graph.
        assert ("__start__", "get_enabled_sources") in graph.edges


# =============================================================================
# Node Function Tests
# =============================================================================


class TestGetEnabledSources:
    """Tests for the get_enabled_sources node.

    REQ-007 §6.2: Get user's enabled sources for polling.
    """

    def test_returns_enabled_sources_when_state_has_sources(self) -> None:
        """Node returns state unchanged when enabled_sources already set."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "enabled_sources": ["Adzuna", "RemoteOK"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "error_sources": [],
        }

        result = get_enabled_sources_node(state)

        assert result["enabled_sources"] == ["Adzuna", "RemoteOK"]


class TestFetchSources:
    """Tests for the fetch_sources node.

    REQ-007 §6.2 + §6.3: Parallel fetch from enabled sources.
    """

    @pytest.mark.asyncio
    async def test_fetches_jobs_when_sources_enabled(self) -> None:
        """Node fetches jobs from all enabled sources and stores in state."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "enabled_sources": ["Adzuna"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "error_sources": [],
        }

        # Mock the adapter to return test jobs
        mock_adapter = MagicMock()
        mock_adapter.source_name = "Adzuna"
        mock_adapter.fetch_jobs = AsyncMock(return_value=[])

        with patch(
            "app.agents.scouter_graph.get_source_adapter",
            return_value=mock_adapter,
        ):
            result = await fetch_sources_node(state)

        # Verify adapter was called
        mock_adapter.fetch_jobs.assert_called_once()
        assert "discovered_jobs" in result

    @pytest.mark.asyncio
    async def test_records_error_when_source_fails(self) -> None:
        """Node records source in error_sources when fetch fails."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "enabled_sources": ["Adzuna"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "error_sources": [],
        }

        # Mock adapter to raise SourceError
        mock_adapter = MagicMock()
        mock_adapter.source_name = "Adzuna"
        mock_adapter.fetch_jobs = AsyncMock(
            side_effect=SourceError(
                source_name="Adzuna",
                error_type=SourceErrorType.API_DOWN,
                message="Connection failed",
            )
        )

        with patch(
            "app.agents.scouter_graph.get_source_adapter",
            return_value=mock_adapter,
        ):
            result = await fetch_sources_node(state)

        # Source error should be recorded (fail-forward)
        assert "Adzuna" in result["error_sources"]


class TestMergeResults:
    """Tests for the merge_results node.

    REQ-007 §6.2: Merge jobs from multiple sources.
    """

    def test_flattens_jobs_when_multiple_sources_fetched(self) -> None:
        """Node flattens discovered_jobs dict into single list."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "discovered_jobs": {
                "Adzuna": [{"external_id": "az-1", "title": "Job A"}],
                "RemoteOK": [{"external_id": "rok-1", "title": "Job B"}],
            },
            "processed_jobs": [],
            "error_sources": [],
        }

        result = merge_results_node(state)

        # Jobs should be merged into a single list
        assert len(result["discovered_jobs"]) == 2


class TestDeduplicateJobs:
    """Tests for the deduplicate_jobs node.

    REQ-007 §6.6: Deduplication logic.
    """

    def test_filters_duplicates_when_jobs_have_same_external_id(self) -> None:
        """Node removes duplicate jobs keeping first occurrence."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "discovered_jobs": [
                {"external_id": "az-1", "source_name": "Adzuna", "title": "Job A"},
                {"external_id": "az-1", "source_name": "Adzuna", "title": "Job A Dupe"},
                {"external_id": "az-2", "source_name": "Adzuna", "title": "Job B"},
            ],
            "processed_jobs": [],
            "error_sources": [],
        }

        result = deduplicate_jobs_node(state)

        # Only unique jobs should remain in processed_jobs
        assert len(result["processed_jobs"]) == 2
        # First occurrence should be kept
        titles = [j["title"] for j in result["processed_jobs"]]
        assert "Job A" in titles
        assert "Job A Dupe" not in titles


# =============================================================================
# Routing Tests
# =============================================================================


class TestCheckNewJobs:
    """Tests for the check_new_jobs routing function.

    REQ-007 §15.3: Route based on whether new jobs were found.
    """

    def test_returns_has_new_jobs_when_processed_jobs_not_empty(self) -> None:
        """Routing returns 'has_new_jobs' when jobs found."""
        state: dict[str, Any] = {
            "processed_jobs": [{"external_id": "az-1", "title": "Job A"}],
        }

        result = check_new_jobs(state)

        assert result == "has_new_jobs"

    def test_returns_no_new_jobs_when_processed_jobs_empty(self) -> None:
        """Routing returns 'no_new_jobs' when no jobs found."""
        state: dict[str, Any] = {
            "processed_jobs": [],
        }

        result = check_new_jobs(state)

        assert result == "no_new_jobs"


# =============================================================================
# Processing Pipeline Tests
# =============================================================================


class TestExtractSkills:
    """Tests for the extract_skills node.

    REQ-007 §6.4: Skill & culture extraction using LLM.
    """

    @pytest.mark.asyncio
    async def test_extracts_skills_when_jobs_have_descriptions(self) -> None:
        """Node extracts skills from job descriptions using LLM."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Python Developer",
                    "description": "Need Python, Django, PostgreSQL experience.",
                }
            ],
            "error_sources": [],
        }

        # Mock the LLM extraction
        with patch(
            "app.agents.scouter_graph.extract_skills_and_culture",
            return_value={
                "required_skills": [{"name": "Python", "level": "Required"}],
                "culture_text": "Fast-paced environment",
            },
        ):
            result = extract_skills_node(state)

        # Jobs should have extracted skills
        assert "required_skills" in result["processed_jobs"][0]


class TestCalculateGhostScore:
    """Tests for the calculate_ghost_score node.

    REQ-007 §6.5: Ghost score calculation.
    """

    @pytest.mark.asyncio
    async def test_calculates_ghost_score_when_jobs_processed(self) -> None:
        """Node calculates ghost score for each processed job."""
        state: dict[str, Any] = {
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Python Developer",
                    "description": "Job description here",
                    "posted_date": None,
                    "salary_min": None,
                    "salary_max": None,
                    "application_deadline": None,
                    "location": None,
                    "seniority_level": None,
                    "years_experience_min": None,
                }
            ],
            "error_sources": [],
        }

        # Mock the ghost score calculation
        with patch(
            "app.agents.scouter_graph.calculate_ghost_score",
            new_callable=AsyncMock,
        ) as mock_ghost:
            mock_ghost.return_value = MagicMock(
                ghost_score=45,
                to_dict=MagicMock(return_value={"ghost_score": 45}),
            )

            result = await calculate_ghost_score_node(state)

        # Jobs should have ghost_score
        assert "ghost_score" in result["processed_jobs"][0]


class TestSaveJobs:
    """Tests for the save_jobs node.

    REQ-007 §6.2: Save jobs via API.
    """

    @pytest.mark.asyncio
    async def test_saves_jobs_when_processed_jobs_exist(self) -> None:
        """Node calls API to save each processed job."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Python Developer",
                    "required_skills": [],
                    "ghost_score": 25,
                }
            ],
            "saved_job_ids": [],
            "error_sources": [],
        }

        # Mock the agent client
        mock_client = MagicMock()
        mock_client.create_job_posting = AsyncMock(
            return_value={"data": {"id": "job-uuid-1"}}
        )

        with patch(
            "app.agents.scouter_graph.get_agent_client",
            return_value=mock_client,
        ):
            result = await save_jobs_node(state)

        # Job IDs should be recorded
        assert "saved_job_ids" in result
        mock_client.create_job_posting.assert_called()


class TestInvokeStrategist:
    """Tests for the invoke_strategist node.

    REQ-007 §15.3: Invoke Strategist sub-graph for scoring.
    """

    def test_invokes_strategist_when_jobs_saved(self) -> None:
        """Node triggers Strategist agent for saved jobs."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "saved_job_ids": ["job-uuid-1", "job-uuid-2"],
            "error_sources": [],
        }

        # Strategist invocation is a placeholder for now
        result = invoke_strategist_node(state)

        # State should be unchanged (placeholder)
        assert result["saved_job_ids"] == ["job-uuid-1", "job-uuid-2"]


class TestUpdatePollState:
    """Tests for the update_poll_state node.

    REQ-007 §6.2: Update polling state after completion.
    """

    def test_updates_poll_state_when_poll_completes(self) -> None:
        """Node updates last_polled_at and next_poll_at timestamps."""
        state: dict[str, Any] = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "polling_frequency": "daily",
            "saved_job_ids": ["job-uuid-1"],
            "error_sources": [],
        }

        result = update_poll_state_node(state)

        # Poll state should be updated
        assert "last_polled_at" in result
        assert "next_poll_at" in result


# =============================================================================
# Graph Compilation Tests
# =============================================================================


class TestScouterGraphCompilation:
    """Tests for graph compilation and execution readiness."""

    def test_graph_compiles_without_error_when_created(self) -> None:
        """Graph compiles successfully into executable form."""
        graph = create_scouter_graph()

        # Compilation should not raise
        compiled = graph.compile()
        assert compiled is not None

    def test_get_scouter_graph_returns_singleton_when_called_multiple_times(
        self,
    ) -> None:
        """get_scouter_graph returns same compiled instance."""
        # Reset to ensure clean state
        reset_scouter_graph()

        graph1 = get_scouter_graph()
        graph2 = get_scouter_graph()

        assert graph1 is graph2
