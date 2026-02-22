"""Tests for the Scouter Agent LangGraph graph.

REQ-007 §15.3 + REQ-015 §10: Graph Spec — Scouter Agent

Tests verify:
1. Graph construction (nodes, edges, entry point)
2. Node function behaviors (check_shared_pool, save_to_pool, etc.)
3. Routing logic (conditional edges)
4. State transitions through the graph
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.scouter_graph import (
    _build_dedup_job_data,
    _check_single_job_in_pool,
    _compute_description_hash,
    _link_existing_job,
    _resolve_source_id,
    _save_single_job,
    calculate_ghost_score_node,
    check_new_jobs,
    check_shared_pool_node,
    create_scouter_graph,
    extract_skills_node,
    fetch_sources_node,
    get_enabled_sources_node,
    get_scouter_graph,
    invoke_strategist_node,
    merge_results_node,
    notify_surfacing_worker_node,
    reset_scouter_graph,
    save_to_pool_node,
    update_poll_state_node,
)
from app.services.scouter_errors import SourceError, SourceErrorType

_PATCH_SESSION = "app.agents.scouter_graph.async_session_factory"
_PATCH_JP_REPO = "app.agents.scouter_graph.JobPostingRepository"
_PATCH_DEDUP = "app.agents.scouter_graph.deduplicate_and_save"
_PATCH_RESOLVE = "app.agents.scouter_graph._resolve_source_id"

_USER_ID = str(uuid.uuid4())
_PERSONA_ID = str(uuid.uuid4())
_SOURCE_ID = uuid.uuid4()
_JOB_ID = uuid.uuid4()


def _make_mock_session() -> MagicMock:
    """Create a mock async session with context manager support."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()  # add() is synchronous in SQLAlchemy
    return mock_session


def _mock_session_factory(mock_session: MagicMock) -> MagicMock:
    """Create a mock session factory returning the given session."""
    return MagicMock(return_value=mock_session)


# =============================================================================
# Graph Construction Tests
# =============================================================================


class TestScouterGraphConstruction:
    """Tests for Scouter graph construction and structure.

    REQ-007 §15.3 + REQ-015 §10.1: Graph must have correct nodes and edges.
    """

    def test_graph_has_all_required_nodes_when_created(self) -> None:
        """Graph contains all nodes per REQ-015 §10.1 node mapping."""
        graph = create_scouter_graph()

        expected_nodes = [
            "get_enabled_sources",
            "fetch_sources",
            "merge_results",
            "check_shared_pool",
            "extract_skills",
            "calculate_ghost_score",
            "save_to_pool",
            "notify_surfacing_worker",
            "invoke_strategist",
            "update_poll_state",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_graph_does_not_have_old_nodes(self) -> None:
        """Old deduplicate_jobs and save_jobs nodes removed per REQ-015 §10."""
        graph = create_scouter_graph()

        assert "deduplicate_jobs" not in graph.nodes
        assert "save_jobs" not in graph.nodes

    def test_graph_entry_point_is_get_enabled_sources_when_created(self) -> None:
        """Graph entry point is get_enabled_sources as per REQ-007 §15.3."""
        graph = create_scouter_graph()
        assert ("__start__", "get_enabled_sources") in graph.edges

    def test_graph_has_correct_linear_edges(self) -> None:
        """Verify the linear edge sequence through the graph."""
        graph = create_scouter_graph()

        linear_edges = [
            ("get_enabled_sources", "fetch_sources"),
            ("fetch_sources", "merge_results"),
            ("merge_results", "check_shared_pool"),
            ("extract_skills", "calculate_ghost_score"),
            ("calculate_ghost_score", "save_to_pool"),
            ("save_to_pool", "notify_surfacing_worker"),
            ("notify_surfacing_worker", "invoke_strategist"),
            ("invoke_strategist", "update_poll_state"),
        ]

        for edge in linear_edges:
            assert edge in graph.edges, f"Missing edge: {edge[0]} → {edge[1]}"


# =============================================================================
# Node Function Tests
# =============================================================================


class TestGetEnabledSources:
    """Tests for the get_enabled_sources node."""

    def test_returns_enabled_sources_when_state_has_sources(self) -> None:
        """Node returns state unchanged when enabled_sources already set."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "enabled_sources": ["Adzuna", "RemoteOK"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        result = get_enabled_sources_node(state)

        assert result["enabled_sources"] == ["Adzuna", "RemoteOK"]


class TestFetchSources:
    """Tests for the fetch_sources node."""

    @pytest.mark.asyncio
    async def test_fetches_jobs_when_sources_enabled(self) -> None:
        """Node fetches jobs from all enabled sources and stores in state."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "enabled_sources": ["Adzuna"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_adapter = MagicMock()
        mock_adapter.source_name = "Adzuna"
        mock_adapter.fetch_jobs = AsyncMock(return_value=[])

        with patch(
            "app.agents.scouter_graph.get_source_adapter",
            return_value=mock_adapter,
        ):
            result = await fetch_sources_node(state)

        mock_adapter.fetch_jobs.assert_called_once()
        assert "discovered_jobs" in result

    @pytest.mark.asyncio
    async def test_records_error_when_source_fails(self) -> None:
        """Node records source in error_sources when fetch fails."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "enabled_sources": ["Adzuna"],
            "discovered_jobs": [],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

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

        assert "Adzuna" in result["error_sources"]


class TestMergeResults:
    """Tests for the merge_results node."""

    def test_flattens_jobs_when_multiple_sources_fetched(self) -> None:
        """Node flattens discovered_jobs dict into single list."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "discovered_jobs": {
                "Adzuna": [{"external_id": "az-1", "title": "Job A"}],
                "RemoteOK": [{"external_id": "rok-1", "title": "Job B"}],
            },
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        result = merge_results_node(state)

        assert len(result["discovered_jobs"]) == 2


# =============================================================================
# check_shared_pool Tests (REQ-015 §10.3)
# =============================================================================


class TestCheckSharedPool:
    """Tests for check_shared_pool_node — replaces deduplicate_jobs.

    REQ-015 §10.3: Check pool by source+external_id and description_hash.
    """

    @pytest.mark.asyncio
    async def test_new_jobs_go_to_processed_when_not_in_pool(self) -> None:
        """Jobs not found in pool are added to processed_jobs."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "discovered_jobs": [
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Job A",
                    "description": "Build Python apps",
                },
            ],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_RESOLVE, new_callable=AsyncMock, return_value=_SOURCE_ID),
            patch(_PATCH_JP_REPO) as mock_repo,
        ):
            mock_repo.get_by_source_and_external_id = AsyncMock(return_value=None)
            mock_repo.get_by_description_hash = AsyncMock(return_value=None)

            result = await check_shared_pool_node(state)

        assert len(result["processed_jobs"]) == 1
        assert len(result["existing_pool_jobs"]) == 0

    @pytest.mark.asyncio
    async def test_existing_jobs_go_to_existing_pool(self) -> None:
        """Jobs found in pool are added to existing_pool_jobs."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "discovered_jobs": [
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Job A",
                    "description": "Build Python apps",
                },
            ],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        existing_job = MagicMock(id=_JOB_ID)

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_RESOLVE, new_callable=AsyncMock, return_value=_SOURCE_ID),
            patch(_PATCH_JP_REPO) as mock_repo,
        ):
            mock_repo.get_by_source_and_external_id = AsyncMock(
                return_value=existing_job
            )

            result = await check_shared_pool_node(state)

        assert len(result["processed_jobs"]) == 0
        assert len(result["existing_pool_jobs"]) == 1
        assert result["existing_pool_jobs"][0]["pool_job_posting_id"] == str(_JOB_ID)

    @pytest.mark.asyncio
    async def test_splits_existing_and_new_jobs(self) -> None:
        """Mix of existing and new jobs are correctly separated."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "discovered_jobs": [
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Existing Job",
                    "description": "Already in pool",
                },
                {
                    "external_id": "az-2",
                    "source_name": "Adzuna",
                    "title": "New Job",
                    "description": "Not in pool yet",
                },
            ],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        existing_job = MagicMock(id=_JOB_ID)

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_RESOLVE, new_callable=AsyncMock, return_value=_SOURCE_ID),
            patch(_PATCH_JP_REPO) as mock_repo,
        ):
            # First job found by external_id, second not found
            mock_repo.get_by_source_and_external_id = AsyncMock(
                side_effect=[existing_job, None]
            )
            mock_repo.get_by_description_hash = AsyncMock(return_value=None)

            result = await check_shared_pool_node(state)

        assert len(result["existing_pool_jobs"]) == 1
        assert len(result["processed_jobs"]) == 1
        assert result["processed_jobs"][0]["title"] == "New Job"

    @pytest.mark.asyncio
    async def test_deduplicates_within_batch(self) -> None:
        """Duplicate jobs within batch are removed before pool check."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "discovered_jobs": [
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Job A",
                    "description": "desc",
                },
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Job A Dupe",
                    "description": "desc dupe",
                },
            ],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_RESOLVE, new_callable=AsyncMock, return_value=_SOURCE_ID),
            patch(_PATCH_JP_REPO) as mock_repo,
        ):
            mock_repo.get_by_source_and_external_id = AsyncMock(return_value=None)
            mock_repo.get_by_description_hash = AsyncMock(return_value=None)

            result = await check_shared_pool_node(state)

        # Only first occurrence should be processed
        assert len(result["processed_jobs"]) == 1
        assert result["processed_jobs"][0]["title"] == "Job A"

    @pytest.mark.asyncio
    async def test_finds_existing_by_description_hash(self) -> None:
        """Job matched by description_hash is added to existing_pool_jobs."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "discovered_jobs": [
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Job A",
                    "description": "Unique description text",
                },
            ],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        existing_job = MagicMock(id=_JOB_ID)

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_RESOLVE, new_callable=AsyncMock, return_value=_SOURCE_ID),
            patch(_PATCH_JP_REPO) as mock_repo,
        ):
            # Not found by external_id, but found by description_hash
            mock_repo.get_by_source_and_external_id = AsyncMock(return_value=None)
            mock_repo.get_by_description_hash = AsyncMock(return_value=existing_job)

            result = await check_shared_pool_node(state)

        assert len(result["existing_pool_jobs"]) == 1
        assert len(result["processed_jobs"]) == 0

    @pytest.mark.asyncio
    async def test_caches_source_id_lookups(self) -> None:
        """Source name → ID resolution is cached across jobs from same source."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "discovered_jobs": [
                {
                    "external_id": "az-1",
                    "source_name": "Adzuna",
                    "title": "Job A",
                    "description": "desc A",
                },
                {
                    "external_id": "az-2",
                    "source_name": "Adzuna",
                    "title": "Job B",
                    "description": "desc B",
                },
            ],
            "processed_jobs": [],
            "existing_pool_jobs": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(
                _PATCH_RESOLVE, new_callable=AsyncMock, return_value=_SOURCE_ID
            ) as mock_resolve,
            patch(_PATCH_JP_REPO) as mock_repo,
        ):
            mock_repo.get_by_source_and_external_id = AsyncMock(return_value=None)
            mock_repo.get_by_description_hash = AsyncMock(return_value=None)

            await check_shared_pool_node(state)

        # _resolve_source_id should only be called once (cached)
        mock_resolve.assert_called_once_with(mock_session, "Adzuna")


# =============================================================================
# Routing Tests
# =============================================================================


class TestCheckNewJobs:
    """Tests for the check_new_jobs routing function."""

    def test_returns_has_new_jobs_when_processed_jobs_not_empty(self) -> None:
        """Routing returns 'has_new_jobs' when jobs found."""
        state: dict[str, Any] = {
            "processed_jobs": [{"external_id": "az-1", "title": "Job A"}],
        }
        assert check_new_jobs(state) == "has_new_jobs"

    def test_returns_no_new_jobs_when_processed_jobs_empty(self) -> None:
        """Routing returns 'no_new_jobs' when no jobs found."""
        state: dict[str, Any] = {
            "processed_jobs": [],
        }
        assert check_new_jobs(state) == "no_new_jobs"


# =============================================================================
# Processing Pipeline Tests
# =============================================================================


class TestExtractSkills:
    """Tests for the extract_skills node."""

    def test_extracts_skills_when_jobs_have_descriptions(self) -> None:
        """Node extracts skills from job descriptions using LLM."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Python Developer",
                    "description": "Need Python, Django, PostgreSQL experience.",
                }
            ],
            "error_sources": [],
        }

        with patch(
            "app.agents.scouter_graph.extract_skills_and_culture",
            return_value={
                "required_skills": [{"name": "Python", "level": "Required"}],
                "culture_text": "Fast-paced environment",
            },
        ):
            result = extract_skills_node(state)

        assert "required_skills" in result["processed_jobs"][0]


class TestCalculateGhostScore:
    """Tests for the calculate_ghost_score node."""

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

        with patch(
            "app.agents.scouter_graph.calculate_ghost_score",
            new_callable=AsyncMock,
        ) as mock_ghost:
            mock_ghost.return_value = MagicMock(
                ghost_score=45,
                to_dict=MagicMock(return_value={"ghost_score": 45}),
            )

            result = await calculate_ghost_score_node(state)

        assert "ghost_score" in result["processed_jobs"][0]


# =============================================================================
# save_to_pool Tests (REQ-015 §10.1)
# =============================================================================


class TestSaveToPool:
    """Tests for save_to_pool_node — replaces save_jobs.

    REQ-015 §10.1: Save to shared pool + create persona_jobs link.
    """

    @pytest.mark.asyncio
    async def test_saves_new_jobs_via_dedup_service(self) -> None:
        """New processed_jobs are saved through deduplicate_and_save."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Python Developer",
                    "company": "Acme",
                    "description": "Build stuff",
                    "source_id": str(_SOURCE_ID),
                    "source_name": "Adzuna",
                },
            ],
            "existing_pool_jobs": [],
            "saved_job_ids": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = _JOB_ID
        mock_outcome.action = "create_new"

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(
                _PATCH_DEDUP, new_callable=AsyncMock, return_value=mock_outcome
            ) as mock_dedup,
        ):
            result = await save_to_pool_node(state)

        mock_dedup.assert_called_once()
        assert str(_JOB_ID) in result["saved_job_ids"]

    @pytest.mark.asyncio
    async def test_creates_links_for_existing_pool_jobs(self) -> None:
        """Existing pool jobs get persona_jobs links via dedup service."""
        pool_job_id = uuid.uuid4()
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "processed_jobs": [],
            "existing_pool_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Existing Job",
                    "company": "Acme",
                    "description": "Already in pool",
                    "source_name": "Adzuna",
                    "pool_job_posting_id": str(pool_job_id),
                    "source_id": str(_SOURCE_ID),
                },
            ],
            "saved_job_ids": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = pool_job_id
        mock_outcome.action = "update_existing"

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_DEDUP, new_callable=AsyncMock, return_value=mock_outcome),
        ):
            result = await save_to_pool_node(state)

        assert str(pool_job_id) in result["saved_job_ids"]

    @pytest.mark.asyncio
    async def test_handles_save_failure_gracefully(self) -> None:
        """Failed saves are logged but don't fail the entire batch."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Job A",
                    "company": "Acme",
                    "description": "desc",
                    "source_id": str(_SOURCE_ID),
                    "source_name": "Adzuna",
                },
                {
                    "external_id": "az-2",
                    "title": "Job B",
                    "company": "Acme",
                    "description": "desc 2",
                    "source_id": str(_SOURCE_ID),
                    "source_name": "Adzuna",
                },
            ],
            "existing_pool_jobs": [],
            "saved_job_ids": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = _JOB_ID
        mock_outcome.action = "create_new"

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(
                _PATCH_DEDUP,
                new_callable=AsyncMock,
                side_effect=[Exception("DB error"), mock_outcome],
            ),
        ):
            result = await save_to_pool_node(state)

        # First job failed, second succeeded
        assert len(result["saved_job_ids"]) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_when_missing_user_id(self) -> None:
        """Returns empty saved_job_ids when user_id is missing."""
        state: dict[str, Any] = {
            "user_id": "",
            "persona_id": "",
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Job A",
                    "description": "desc",
                    "source_id": str(_SOURCE_ID),
                }
            ],
            "existing_pool_jobs": [],
            "saved_job_ids": [],
        }

        result = await save_to_pool_node(state)

        assert result["saved_job_ids"] == []

    @pytest.mark.asyncio
    async def test_commits_transaction_after_all_saves(self) -> None:
        """DB transaction is committed after all saves complete."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Job A",
                    "company": "Acme",
                    "description": "desc",
                    "source_id": str(_SOURCE_ID),
                    "source_name": "Adzuna",
                },
            ],
            "existing_pool_jobs": [],
            "saved_job_ids": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = _JOB_ID
        mock_outcome.action = "create_new"

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_DEDUP, new_callable=AsyncMock, return_value=mock_outcome),
        ):
            await save_to_pool_node(state)

        mock_session.commit.assert_called_once()


# =============================================================================
# notify_surfacing_worker Tests (REQ-015 §10.1)
# =============================================================================


class TestNotifySurfacingWorker:
    """Tests for notify_surfacing_worker_node."""

    def test_returns_state_unchanged(self) -> None:
        """Node does not modify state."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "saved_job_ids": ["job-1", "job-2"],
            "error_sources": [],
        }

        result = notify_surfacing_worker_node(state)

        assert result is state

    def test_does_not_raise_when_no_jobs(self) -> None:
        """Node handles empty saved_job_ids without error."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "saved_job_ids": [],
            "error_sources": [],
        }

        result = notify_surfacing_worker_node(state)

        assert result is state


# =============================================================================
# Remaining Node Tests
# =============================================================================


class TestInvokeStrategist:
    """Tests for the invoke_strategist node."""

    def test_invokes_strategist_when_jobs_saved(self) -> None:
        """Node triggers Strategist agent for saved jobs."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "saved_job_ids": ["job-uuid-1", "job-uuid-2"],
            "error_sources": [],
        }

        result = invoke_strategist_node(state)
        assert result["saved_job_ids"] == ["job-uuid-1", "job-uuid-2"]


class TestUpdatePollState:
    """Tests for the update_poll_state node."""

    def test_updates_poll_state_when_poll_completes(self) -> None:
        """Node updates last_polled_at and next_poll_at timestamps."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "polling_frequency": "daily",
            "saved_job_ids": ["job-uuid-1"],
            "error_sources": [],
        }

        result = update_poll_state_node(state)

        assert "last_polled_at" in result
        assert "next_poll_at" in result


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_compute_description_hash_is_deterministic(self) -> None:
        """Same input always produces same hash."""
        text = "Build Python applications"
        hash1 = _compute_description_hash(text)
        hash2 = _compute_description_hash(text)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_build_dedup_job_data_transforms_correctly(self) -> None:
        """Scouter job dict is transformed to dedup service format."""
        job: dict[str, Any] = {
            "title": "Python Developer",
            "company": "Acme Corp",
            "description": "Build great software",
            "external_id": "az-123",
            "source_url": "https://example.com/job/123",
            "location": "Remote",
            "salary_min": 80000,
            "salary_max": 120000,
        }
        source_id = uuid.uuid4()

        result = _build_dedup_job_data(job, source_id)

        assert result["source_id"] == source_id
        assert result["job_title"] == "Python Developer"
        assert result["company_name"] == "Acme Corp"
        assert result["description"] == "Build great software"
        assert result["external_id"] == "az-123"
        assert result["salary_min"] == 80000
        assert result["salary_max"] == 120000
        assert "description_hash" in result


# =============================================================================
# _check_single_job_in_pool Tests
# =============================================================================


class TestCheckSingleJobInPool:
    """Tests for _check_single_job_in_pool helper."""

    @pytest.mark.asyncio
    async def test_returns_existing_when_found_by_external_id(self) -> None:
        """Job found by source_id + external_id is classified as existing."""
        mock_session = _make_mock_session()
        existing_job = MagicMock(id=_JOB_ID)
        job: dict[str, Any] = {
            "external_id": "az-1",
            "source_name": "Adzuna",
            "description": "desc",
        }

        with patch(_PATCH_JP_REPO) as mock_repo:
            mock_repo.get_by_source_and_external_id = AsyncMock(
                return_value=existing_job
            )

            is_existing, enriched = await _check_single_job_in_pool(
                mock_session, job, _SOURCE_ID
            )

        assert is_existing is True
        assert enriched["pool_job_posting_id"] == str(_JOB_ID)

    @pytest.mark.asyncio
    async def test_returns_new_when_not_found(self) -> None:
        """Job not found in pool is classified as new."""
        mock_session = _make_mock_session()
        job: dict[str, Any] = {
            "external_id": "az-1",
            "source_name": "Adzuna",
            "description": "desc",
        }

        with patch(_PATCH_JP_REPO) as mock_repo:
            mock_repo.get_by_source_and_external_id = AsyncMock(return_value=None)
            mock_repo.get_by_description_hash = AsyncMock(return_value=None)

            is_existing, enriched = await _check_single_job_in_pool(
                mock_session, job, _SOURCE_ID
            )

        assert is_existing is False
        assert "pool_job_posting_id" not in enriched
        assert enriched["source_id"] == str(_SOURCE_ID)


# =============================================================================
# _resolve_source_id Tests
# =============================================================================


class TestResolveSourceId:
    """Tests for _resolve_source_id with allowlist enforcement."""

    @pytest.mark.asyncio
    async def test_returns_existing_source_id(self) -> None:
        """Existing source is looked up and returned."""
        mock_session = _make_mock_session()
        mock_source = MagicMock(id=_SOURCE_ID)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_source
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await _resolve_source_id(mock_session, "Adzuna")

        assert result == _SOURCE_ID

    @pytest.mark.asyncio
    async def test_creates_source_for_known_name(self) -> None:
        """Known source name not in DB is auto-created."""
        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        await _resolve_source_id(mock_session, "Adzuna")

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_unknown_source_name(self) -> None:
        """Unknown source name is rejected (returns None)."""
        mock_session = _make_mock_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await _resolve_source_id(mock_session, "MaliciousSource")

        assert result is None
        mock_session.add.assert_not_called()


# =============================================================================
# _save_single_job / _link_existing_job Tests
# =============================================================================


class TestSaveAndLinkHelpers:
    """Tests for _save_single_job and _link_existing_job helpers."""

    @pytest.mark.asyncio
    async def test_save_single_job_returns_id_on_success(self) -> None:
        """Successful save returns job posting ID."""
        mock_session = _make_mock_session()
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = _JOB_ID
        mock_outcome.action = "create_new"

        job: dict[str, Any] = {
            "external_id": "az-1",
            "title": "Job A",
            "company": "Acme",
            "description": "desc",
            "source_id": str(_SOURCE_ID),
        }

        with patch(_PATCH_DEDUP, new_callable=AsyncMock, return_value=mock_outcome):
            result = await _save_single_job(
                mock_session, job, uuid.uuid4(), uuid.uuid4()
            )

        assert result == str(_JOB_ID)

    @pytest.mark.asyncio
    async def test_save_single_job_returns_none_on_invalid_uuid(self) -> None:
        """Invalid source_id UUID returns None instead of crashing."""
        mock_session = _make_mock_session()
        job: dict[str, Any] = {
            "external_id": "az-1",
            "description": "desc",
            "source_id": "not-a-uuid",
        }

        result = await _save_single_job(mock_session, job, uuid.uuid4(), uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_link_existing_job_returns_pool_id(self) -> None:
        """Successful link returns pool job posting ID."""
        mock_session = _make_mock_session()
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = _JOB_ID

        pool_id = str(uuid.uuid4())
        job: dict[str, Any] = {
            "external_id": "az-1",
            "title": "Job A",
            "company": "Acme",
            "description": "desc",
            "source_id": str(_SOURCE_ID),
            "pool_job_posting_id": pool_id,
        }

        with patch(_PATCH_DEDUP, new_callable=AsyncMock, return_value=mock_outcome):
            result = await _link_existing_job(
                mock_session, job, uuid.uuid4(), uuid.uuid4()
            )

        assert result == pool_id

    @pytest.mark.asyncio
    async def test_link_existing_job_returns_none_on_missing_source_id(
        self,
    ) -> None:
        """Missing source_id key returns None instead of crashing."""
        mock_session = _make_mock_session()
        job: dict[str, Any] = {
            "external_id": "az-1",
            "description": "desc",
            "pool_job_posting_id": str(uuid.uuid4()),
        }

        result = await _link_existing_job(mock_session, job, uuid.uuid4(), uuid.uuid4())

        assert result is None


# =============================================================================
# save_to_pool UUID validation Tests
# =============================================================================


class TestSaveToPoolValidation:
    """Tests for save_to_pool_node input validation."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_user_id_is_invalid_uuid(self) -> None:
        """Invalid user_id UUID format returns empty saved_job_ids."""
        state: dict[str, Any] = {
            "user_id": "not-a-uuid",
            "persona_id": _PERSONA_ID,
            "processed_jobs": [{"external_id": "az-1", "source_id": str(_SOURCE_ID)}],
            "existing_pool_jobs": [],
        }

        result = await save_to_pool_node(state)

        assert result["saved_job_ids"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_commit_fails(self) -> None:
        """Failed commit returns empty saved_job_ids."""
        state: dict[str, Any] = {
            "user_id": _USER_ID,
            "persona_id": _PERSONA_ID,
            "processed_jobs": [
                {
                    "external_id": "az-1",
                    "title": "Job A",
                    "company": "Acme",
                    "description": "desc",
                    "source_id": str(_SOURCE_ID),
                    "source_name": "Adzuna",
                },
            ],
            "existing_pool_jobs": [],
            "saved_job_ids": [],
            "error_sources": [],
        }

        mock_session = _make_mock_session()
        mock_session.commit = AsyncMock(side_effect=Exception("DB commit error"))
        mock_outcome = MagicMock()
        mock_outcome.job_posting.id = _JOB_ID
        mock_outcome.action = "create_new"

        with (
            patch(_PATCH_SESSION, _mock_session_factory(mock_session)),
            patch(_PATCH_DEDUP, new_callable=AsyncMock, return_value=mock_outcome),
        ):
            result = await save_to_pool_node(state)

        assert result["saved_job_ids"] == []


# =============================================================================
# Graph Compilation Tests
# =============================================================================


class TestScouterGraphCompilation:
    """Tests for graph compilation and execution readiness."""

    def test_graph_compiles_without_error_when_created(self) -> None:
        """Graph compiles successfully into executable form."""
        graph = create_scouter_graph()

        compiled = graph.compile()
        assert compiled is not None

    def test_get_scouter_graph_returns_singleton_when_called_multiple_times(
        self,
    ) -> None:
        """get_scouter_graph returns same compiled instance."""
        reset_scouter_graph()

        graph1 = get_scouter_graph()
        graph2 = get_scouter_graph()

        assert graph1 is graph2
