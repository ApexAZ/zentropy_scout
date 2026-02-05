"""Tests for Ghostwriter Agent graph.

REQ-007 §8: Ghostwriter Agent — Generates tailored application materials.
REQ-007 §15.5: Graph Spec — Ghostwriter Agent (9-node graph)

The Ghostwriter orchestrates:
1. Duplicate prevention (check existing variant)
2. Base resume selection
3. Tailoring evaluation and job variant creation
4. Achievement story selection
5. Cover letter generation
6. Job freshness check
7. Presenting results for user review
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.ghostwriter_graph import (
    check_existing_variant_node,
    check_job_still_active_node,
    create_ghostwriter_graph,
    create_job_variant_node,
    evaluate_tailoring_need_node,
    generate_cover_letter_node,
    generate_materials,
    get_ghostwriter_graph,
    handle_duplicate_node,
    is_job_active,
    needs_tailoring,
    present_for_review_node,
    reset_ghostwriter_graph,
    route_existing_variant,
    select_achievement_stories_node,
    select_base_resume_node,
)
from app.agents.state import GhostwriterState
from app.services.cover_letter_generation import CoverLetterResult

# =============================================================================
# Graph Structure Tests (§15.5)
# =============================================================================


class TestGhostwriterGraphStructure:
    """Tests for Ghostwriter graph structure per REQ-007 §15.5."""

    def test_graph_has_nine_nodes(self) -> None:
        """Graph should have exactly 9 nodes per §15.5 spec."""

        graph = create_ghostwriter_graph()
        compiled = graph.compile()
        node_names = set(compiled.get_graph().nodes.keys())
        # LangGraph adds __start__ and __end__ nodes automatically
        non_internal = {n for n in node_names if not n.startswith("__")}

        expected_nodes = {
            "check_existing_variant",
            "handle_duplicate",
            "select_base_resume",
            "evaluate_tailoring_need",
            "create_job_variant",
            "select_achievement_stories",
            "generate_cover_letter",
            "check_job_still_active",
            "present_for_review",
        }

        assert non_internal == expected_nodes

    def test_entry_point_is_check_existing_variant(self) -> None:
        """Entry point should be check_existing_variant per §15.5."""

        graph = create_ghostwriter_graph()
        compiled = graph.compile()
        graph_repr = compiled.get_graph()
        # __start__ should connect to check_existing_variant
        start_edges = [e.target for e in graph_repr.edges if e.source == "__start__"]

        assert "check_existing_variant" in start_edges

    def test_graph_compiles_without_error(self) -> None:
        """Graph should compile successfully."""

        graph = create_ghostwriter_graph()
        compiled = graph.compile()

        assert compiled is not None

    def test_singleton_pattern_returns_same_instance(self) -> None:
        """get_ghostwriter_graph should return same instance on repeated calls."""
        reset_ghostwriter_graph()
        graph1 = get_ghostwriter_graph()
        graph2 = get_ghostwriter_graph()

        assert graph1 is graph2

        reset_ghostwriter_graph()

    def test_reset_clears_singleton(self) -> None:
        """reset_ghostwriter_graph should clear the singleton."""
        reset_ghostwriter_graph()
        graph1 = get_ghostwriter_graph()
        reset_ghostwriter_graph()
        graph2 = get_ghostwriter_graph()

        assert graph1 is not graph2

        reset_ghostwriter_graph()


# =============================================================================
# Routing Function Tests (§15.5)
# =============================================================================


class TestRouteExistingVariant:
    """Tests for route_existing_variant routing function."""

    def test_none_exists_when_status_is_none(self) -> None:
        """Should return 'none_exists' when existing_variant_status is None."""

        state: GhostwriterState = {"existing_variant_status": None}
        assert route_existing_variant(state) == "none_exists"

    def test_none_exists_when_status_missing(self) -> None:
        """Should return 'none_exists' when existing_variant_status not in state."""

        state: GhostwriterState = {}
        assert route_existing_variant(state) == "none_exists"

    def test_draft_exists_when_status_is_draft(self) -> None:
        """Should return 'draft_exists' when existing_variant_status is 'draft'."""

        state: GhostwriterState = {"existing_variant_status": "draft"}
        assert route_existing_variant(state) == "draft_exists"

    def test_approved_exists_when_status_is_approved(self) -> None:
        """Should return 'approved_exists' when existing_variant_status is 'approved'."""

        state: GhostwriterState = {"existing_variant_status": "approved"}
        assert route_existing_variant(state) == "approved_exists"


class TestNeedsTailoring:
    """Tests for needs_tailoring routing function."""

    def test_needs_tailoring_when_true(self) -> None:
        """Should return 'needs_tailoring' when tailoring_needed is True."""

        state: GhostwriterState = {"tailoring_needed": True}
        assert needs_tailoring(state) == "needs_tailoring"

    def test_no_tailoring_when_false(self) -> None:
        """Should return 'no_tailoring' when tailoring_needed is False."""

        state: GhostwriterState = {"tailoring_needed": False}
        assert needs_tailoring(state) == "no_tailoring"

    def test_no_tailoring_when_missing(self) -> None:
        """Should return 'no_tailoring' when tailoring_needed not in state."""

        state: GhostwriterState = {}
        assert needs_tailoring(state) == "no_tailoring"


class TestIsJobActive:
    """Tests for is_job_active routing function."""

    def test_active_when_job_active_true(self) -> None:
        """Should return 'active' when job_active is True."""

        state: GhostwriterState = {"job_active": True}
        assert is_job_active(state) == "active"

    def test_expired_when_job_active_false(self) -> None:
        """Should return 'expired' when job_active is False."""

        state: GhostwriterState = {"job_active": False}
        assert is_job_active(state) == "expired"

    def test_active_when_job_active_missing(self) -> None:
        """Should return 'active' when job_active not in state (optimistic)."""

        state: GhostwriterState = {}
        assert is_job_active(state) == "active"


# =============================================================================
# Node Function Tests (§15.5)
# =============================================================================


class TestCheckExistingVariantNode:
    """Tests for check_existing_variant_node."""

    @pytest.mark.asyncio
    async def test_sets_existing_variant_status(self) -> None:
        """Node should set existing_variant_status in state."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
        }
        result = await check_existing_variant_node(state)

        assert "existing_variant_status" in result

    @pytest.mark.asyncio
    async def test_placeholder_returns_none_status(self) -> None:
        """Placeholder should assume no existing variant."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
        }
        result = await check_existing_variant_node(state)

        assert result["existing_variant_status"] is None

    @pytest.mark.asyncio
    async def test_uses_existing_variant_id_from_state(self) -> None:
        """Node should check existing_variant_id if present in state."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "existing_variant_id": "variant-1",
        }
        result = await check_existing_variant_node(state)

        assert "existing_variant_status" in result


class TestHandleDuplicateNode:
    """Tests for handle_duplicate_node."""

    @pytest.mark.asyncio
    async def test_sets_duplicate_message(self) -> None:
        """Node should set duplicate_message in state."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "job_posting_id": "job-1",
            "existing_variant_status": "draft",
        }
        result = await handle_duplicate_node(state)

        assert "duplicate_message" in result
        assert result["duplicate_message"] is not None

    @pytest.mark.asyncio
    async def test_draft_message_differs_from_approved(self) -> None:
        """Draft duplicate message should differ from approved."""

        draft_state: GhostwriterState = {
            "user_id": "user-1",
            "job_posting_id": "job-1",
            "existing_variant_status": "draft",
        }
        approved_state: GhostwriterState = {
            "user_id": "user-1",
            "job_posting_id": "job-1",
            "existing_variant_status": "approved",
        }

        draft_result = await handle_duplicate_node(draft_state)
        approved_result = await handle_duplicate_node(approved_state)

        assert draft_result["duplicate_message"] != approved_result["duplicate_message"]


class TestSelectBaseResumeNode:
    """Tests for select_base_resume_node."""

    @pytest.mark.asyncio
    async def test_sets_selected_base_resume_id(self) -> None:
        """Node should set selected_base_resume_id in state."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
        }
        result = await select_base_resume_node(state)

        assert "selected_base_resume_id" in result

    @pytest.mark.asyncio
    async def test_preserves_existing_state(self) -> None:
        """Node should preserve existing state fields."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "trigger_type": "manual_request",
        }
        result = await select_base_resume_node(state)

        assert result["user_id"] == "user-1"
        assert result["trigger_type"] == "manual_request"


class TestEvaluateTailoringNeedNode:
    """Tests for evaluate_tailoring_need_node."""

    @pytest.mark.asyncio
    async def test_sets_tailoring_needed_bool(self) -> None:
        """Node should set tailoring_needed as a bool from service result."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_base_resume_id": "resume-1",
        }
        result = await evaluate_tailoring_need_node(state)

        assert "tailoring_needed" in result
        assert isinstance(result["tailoring_needed"], bool)

    @pytest.mark.asyncio
    async def test_sets_tailoring_analysis_dict(self) -> None:
        """Node should set tailoring_analysis dict from service result."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_base_resume_id": "resume-1",
        }
        result = await evaluate_tailoring_need_node(state)

        assert "tailoring_analysis" in result
        analysis = result["tailoring_analysis"]
        assert isinstance(analysis, dict)
        assert "action" in analysis
        assert "signals" in analysis
        assert "reasoning" in analysis

    @pytest.mark.asyncio
    async def test_tailoring_analysis_action_matches_bool(self) -> None:
        """tailoring_needed bool should match tailoring_analysis action."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_base_resume_id": "resume-1",
        }
        result = await evaluate_tailoring_need_node(state)

        analysis = result["tailoring_analysis"]
        if result["tailoring_needed"]:
            assert analysis["action"] == "create_variant"
        else:
            assert analysis["action"] == "use_base"

    @pytest.mark.asyncio
    async def test_preserves_existing_state(self) -> None:
        """Node should preserve existing state fields."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_base_resume_id": "resume-1",
            "trigger_type": "manual_request",
        }
        result = await evaluate_tailoring_need_node(state)

        assert result["user_id"] == "user-1"
        assert result["trigger_type"] == "manual_request"


class TestCreateJobVariantNode:
    """Tests for create_job_variant_node."""

    @pytest.mark.asyncio
    async def test_sets_generated_resume(self) -> None:
        """Node should set generated_resume in state."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_base_resume_id": "resume-1",
        }
        result = await create_job_variant_node(state)

        assert "generated_resume" in result


class TestSelectAchievementStoriesNode:
    """Tests for select_achievement_stories_node.

    REQ-007 §8.6: Story selection wired to story_selection service.
    """

    @pytest.mark.asyncio
    async def test_sets_selected_stories(self) -> None:
        """Node should set selected_stories in state."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
        }
        result = await select_achievement_stories_node(state)

        assert "selected_stories" in result
        assert isinstance(result["selected_stories"], list)

    @pytest.mark.asyncio
    async def test_delegates_to_story_selection_service(self) -> None:
        """Node should call select_achievement_stories from the service."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
        }

        with patch(
            "app.agents.ghostwriter_graph.select_achievement_stories",
            return_value=[],
        ) as mock_service:
            await select_achievement_stories_node(state)

        mock_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_extracts_story_ids_from_scored_results(self) -> None:
        """Node should extract story_id from ScoredStory results."""
        from app.services.story_selection import ScoredStory

        mock_results = [
            ScoredStory(
                story_id="story-1",
                title="Migration",
                context="ctx",
                action="act",
                outcome="out",
                score=50,
                rationale="Skills match",
            ),
            ScoredStory(
                story_id="story-2",
                title="Pipeline",
                context="ctx",
                action="act",
                outcome="out",
                score=30,
                rationale="Recency",
            ),
        ]

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
        }

        with patch(
            "app.agents.ghostwriter_graph.select_achievement_stories",
            return_value=mock_results,
        ):
            result = await select_achievement_stories_node(state)

        assert result["selected_stories"] == ["story-1", "story-2"]


class TestGenerateCoverLetterNode:
    """Tests for generate_cover_letter_node.

    REQ-007 §8.5: Cover letter generation wired to LLM service.
    """

    def _mock_cover_letter_result(self) -> CoverLetterResult:
        """Create a mock CoverLetterResult for testing."""
        return CoverLetterResult(
            content="Dear Hiring Manager, ...",
            reasoning="Selected story for relevance.",
            word_count=42,
            stories_used=["story-1", "story-2"],
        )

    @pytest.mark.asyncio
    async def test_sets_generated_cover_letter_as_dict(self) -> None:
        """Node should set generated_cover_letter as a GeneratedContent dict."""

        mock_result = self._mock_cover_letter_result()

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_stories": ["story-1", "story-2"],
        }

        with patch(
            "app.agents.ghostwriter_graph.generate_cover_letter",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generate_cover_letter_node(state)

        letter = result["generated_cover_letter"]
        assert isinstance(letter, dict)
        assert letter["content"] == "Dear Hiring Manager, ..."
        assert letter["reasoning"] == "Selected story for relevance."
        assert letter["stories_used"] == ["story-1", "story-2"]

    @pytest.mark.asyncio
    async def test_preserves_existing_state(self) -> None:
        """Node should preserve existing state fields."""

        mock_result = self._mock_cover_letter_result()

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "trigger_type": "manual_request",
            "selected_stories": ["story-1"],
        }

        with patch(
            "app.agents.ghostwriter_graph.generate_cover_letter",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generate_cover_letter_node(state)

        assert result["user_id"] == "user-1"
        assert result["trigger_type"] == "manual_request"

    @pytest.mark.asyncio
    async def test_handles_empty_selected_stories(self) -> None:
        """Node should work with empty selected_stories."""

        mock_result = CoverLetterResult(
            content="Dear Hiring Manager, ...",
            reasoning="No stories available.",
            word_count=42,
            stories_used=[],
        )

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_stories": [],
        }

        with patch(
            "app.agents.ghostwriter_graph.generate_cover_letter",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await generate_cover_letter_node(state)

        letter = result["generated_cover_letter"]
        assert letter["stories_used"] == []

    @pytest.mark.asyncio
    async def test_passes_state_data_to_service(self) -> None:
        """Node should pass state data to the generate_cover_letter service."""

        mock_result = self._mock_cover_letter_result()

        state: GhostwriterState = {
            "user_id": "user-1",
            "persona_id": "persona-1",
            "job_posting_id": "job-1",
            "selected_stories": ["story-1"],
        }

        with patch(
            "app.agents.ghostwriter_graph.generate_cover_letter",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_service:
            await generate_cover_letter_node(state)

        mock_service.assert_called_once()
        call_kwargs = mock_service.call_args[1]
        assert call_kwargs["stories_used"] == ["story-1"]


class TestCheckJobStillActiveNode:
    """Tests for check_job_still_active_node."""

    @pytest.mark.asyncio
    async def test_sets_job_active(self) -> None:
        """Node should set job_active in state."""

        state: GhostwriterState = {
            "job_posting_id": "job-1",
        }
        result = await check_job_still_active_node(state)

        assert "job_active" in result
        assert isinstance(result["job_active"], bool)

    @pytest.mark.asyncio
    async def test_placeholder_assumes_active(self) -> None:
        """Placeholder should assume job is still active."""

        state: GhostwriterState = {
            "job_posting_id": "job-1",
        }
        result = await check_job_still_active_node(state)

        assert result["job_active"] is True


class TestPresentForReviewNode:
    """Tests for present_for_review_node."""

    @pytest.mark.asyncio
    async def test_sets_requires_human_input(self) -> None:
        """Node should set requires_human_input for HITL checkpoint."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "job_posting_id": "job-1",
            "generated_resume": None,
            "generated_cover_letter": None,
            "job_active": True,
        }
        result = await present_for_review_node(state)

        assert result.get("requires_human_input") is True

    @pytest.mark.asyncio
    async def test_sets_review_warning_when_expired(self) -> None:
        """Node should set review_warning when job is expired."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "job_posting_id": "job-1",
            "generated_resume": None,
            "generated_cover_letter": None,
            "job_active": False,
        }
        result = await present_for_review_node(state)

        assert result.get("review_warning") is not None

    @pytest.mark.asyncio
    async def test_no_warning_when_active(self) -> None:
        """Node should not set review_warning when job is active."""

        state: GhostwriterState = {
            "user_id": "user-1",
            "job_posting_id": "job-1",
            "generated_resume": None,
            "generated_cover_letter": None,
            "job_active": True,
        }
        result = await present_for_review_node(state)

        assert result.get("review_warning") is None


# =============================================================================
# Convenience Function Tests (§15.5)
# =============================================================================


class TestGenerateMaterials:
    """Tests for generate_materials convenience function."""

    @pytest.mark.asyncio
    async def test_invokes_graph(self) -> None:
        """generate_materials should invoke the ghostwriter graph."""

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "generated_resume": None,
            "generated_cover_letter": None,
        }

        with patch(
            "app.agents.ghostwriter_graph.get_ghostwriter_graph",
            return_value=mock_graph,
        ):
            result = await generate_materials(
                user_id="user-1",
                persona_id="persona-1",
                job_posting_id="job-1",
                trigger_type="manual_request",
            )

        assert mock_graph.ainvoke.call_count == 1
        assert "generated_resume" in result
        assert "generated_cover_letter" in result

    @pytest.mark.asyncio
    async def test_rejects_empty_user_id(self) -> None:
        """generate_materials should reject empty user_id."""

        with pytest.raises(ValueError, match="user_id.*required"):
            await generate_materials(
                user_id="",
                persona_id="persona-1",
                job_posting_id="job-1",
                trigger_type="manual_request",
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_persona_id(self) -> None:
        """generate_materials should reject empty persona_id."""

        with pytest.raises(ValueError, match="persona_id.*required"):
            await generate_materials(
                user_id="user-1",
                persona_id="",
                job_posting_id="job-1",
                trigger_type="manual_request",
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_job_posting_id(self) -> None:
        """generate_materials should reject empty job_posting_id."""

        with pytest.raises(ValueError, match="job_posting_id.*required"):
            await generate_materials(
                user_id="user-1",
                persona_id="persona-1",
                job_posting_id="",
                trigger_type="manual_request",
            )

    @pytest.mark.asyncio
    async def test_rejects_invalid_trigger_type(self) -> None:
        """generate_materials should reject invalid trigger_type values."""
        with pytest.raises(ValueError, match="trigger_type must be one of"):
            await generate_materials(
                user_id="user-1",
                persona_id="persona-1",
                job_posting_id="job-1",
                trigger_type="invalid_trigger",
            )

    @pytest.mark.asyncio
    async def test_passes_feedback_for_regeneration(self) -> None:
        """generate_materials should pass feedback when trigger is regeneration."""

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "generated_resume": None,
            "generated_cover_letter": None,
        }

        with patch(
            "app.agents.ghostwriter_graph.get_ghostwriter_graph",
            return_value=mock_graph,
        ):
            await generate_materials(
                user_id="user-1",
                persona_id="persona-1",
                job_posting_id="job-1",
                trigger_type="regeneration",
                feedback="Make it more formal",
            )

        # Verify feedback was passed in the initial state
        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["feedback"] == "Make it more formal"

    @pytest.mark.asyncio
    async def test_passes_existing_variant_id(self) -> None:
        """generate_materials should pass existing_variant_id to graph."""

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "generated_resume": None,
            "generated_cover_letter": None,
        }

        with patch(
            "app.agents.ghostwriter_graph.get_ghostwriter_graph",
            return_value=mock_graph,
        ):
            await generate_materials(
                user_id="user-1",
                persona_id="persona-1",
                job_posting_id="job-1",
                trigger_type="manual_request",
                existing_variant_id="variant-1",
            )

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["existing_variant_id"] == "variant-1"
