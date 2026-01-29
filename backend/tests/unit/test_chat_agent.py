"""Tests for the Chat Agent.

REQ-007 §4: Chat Agent

Tests verify:
- Intent classification from user messages
- Tool selection based on intent
- Routing logic (tools vs sub-graphs vs clarification)
- Ambiguity resolution
- Response formatting
"""

from app.agents.chat import (
    classify_intent,
    create_chat_graph,
    format_response,
    needs_clarification,
    request_clarification,
    route_by_intent,
    select_tools,
)
from app.agents.state import ChatAgentState

# =============================================================================
# Intent Classification Tests (§4.3)
# =============================================================================


class TestIntentClassification:
    """Tests for intent classification logic."""

    def test_classify_intent_returns_classified_intent(self) -> None:
        """classify_intent should return a ClassifiedIntent dict."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show me new jobs",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": None,
            "target_job_id": None,
        }

        result = classify_intent(state)

        assert "classified_intent" in result
        assert result["classified_intent"] is not None

    def test_classify_job_list_intent(self) -> None:
        """'Show me new jobs' should classify as list_jobs intent."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show me new jobs",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": None,
            "target_job_id": None,
        }

        result = classify_intent(state)
        intent = result["classified_intent"]

        assert intent is not None
        assert intent["type"] == "list_jobs"
        assert intent["requires_tools"] is True

    def test_classify_draft_materials_intent(self) -> None:
        """'Draft materials for this job' should classify as draft_materials."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Draft materials for job 123",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": None,
            "target_job_id": None,
        }

        result = classify_intent(state)
        intent = result["classified_intent"]

        assert intent is not None
        assert intent["type"] == "draft_materials"
        assert intent["requires_tools"] is False  # Delegates to Ghostwriter sub-graph

    def test_classify_onboarding_intent(self) -> None:
        """'Update my skills' should classify as onboarding_request."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Update my skills",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": None,
            "target_job_id": None,
        }

        result = classify_intent(state)
        intent = result["classified_intent"]

        assert intent is not None
        assert intent["type"] == "onboarding_request"

    def test_classify_direct_question(self) -> None:
        """A general question should classify as direct_response."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "How does job matching work?",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": None,
            "target_job_id": None,
        }

        result = classify_intent(state)
        intent = result["classified_intent"]

        assert intent is not None
        assert intent["type"] == "direct_question"
        assert intent["requires_tools"] is False

    def test_intent_has_confidence_score(self) -> None:
        """Classified intent should include confidence score."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show me jobs",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": None,
            "target_job_id": None,
        }

        result = classify_intent(state)
        intent = result["classified_intent"]

        assert intent is not None
        assert "confidence" in intent
        assert 0.0 <= intent["confidence"] <= 1.0


# =============================================================================
# Routing Logic Tests (§15.1)
# =============================================================================


class TestRouting:
    """Tests for intent-based routing."""

    def test_route_tool_call_when_tools_required(self) -> None:
        """High-confidence tool intent should route to tool_call."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show me new jobs",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "list_jobs",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        route = route_by_intent(state)
        assert route == "tool_call"

    def test_route_onboarding_for_onboarding_request(self) -> None:
        """Onboarding request should route to onboarding sub-graph."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Update my skills",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "onboarding_request",
                "confidence": 0.9,
                "requires_tools": False,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        route = route_by_intent(state)
        assert route == "onboarding"

    def test_route_ghostwriter_for_draft_materials(self) -> None:
        """Draft materials request should route to ghostwriter sub-graph."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Draft materials for job 123",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "draft_materials",
                "confidence": 0.85,
                "requires_tools": False,
                "target_resource": "job-123",
            },
            "target_job_id": "job-123",
        }

        route = route_by_intent(state)
        assert route == "ghostwriter"

    def test_route_clarification_when_low_confidence(self) -> None:
        """Low confidence (<0.7) should route to clarification."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Do something with that",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "unknown",
                "confidence": 0.5,
                "requires_tools": False,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        route = route_by_intent(state)
        assert route == "clarification_needed"

    def test_route_direct_response_for_question(self) -> None:
        """Direct question should route to direct_response."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "What is fit score?",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "direct_question",
                "confidence": 0.85,
                "requires_tools": False,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        route = route_by_intent(state)
        assert route == "direct_response"


# =============================================================================
# Tool Selection Tests (§4.2)
# =============================================================================


class TestToolSelection:
    """Tests for tool selection based on intent."""

    def test_select_list_jobs_tool(self) -> None:
        """list_jobs intent should select list_job_postings tool."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show me new jobs",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "list_jobs",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        result = select_tools(state)

        assert "tool_calls" in result
        assert len(result["tool_calls"]) > 0
        assert result["tool_calls"][0]["tool"] == "list_job_postings"

    def test_select_favorite_job_tool(self) -> None:
        """favorite_job intent should select update_job_posting tool."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Favorite job 123",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "favorite_job",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": "job-123",
            },
            "target_job_id": "job-123",
        }

        result = select_tools(state)

        assert "tool_calls" in result
        assert len(result["tool_calls"]) > 0
        assert result["tool_calls"][0]["tool"] == "update_job_posting"
        assert result["tool_calls"][0]["arguments"]["is_favorite"] is True

    def test_select_dismiss_job_tool(self) -> None:
        """dismiss_job intent should select update_job_posting with status."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Dismiss job 123",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "dismiss_job",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": "job-123",
            },
            "target_job_id": "job-123",
        }

        result = select_tools(state)

        assert "tool_calls" in result
        assert len(result["tool_calls"]) > 0
        assert result["tool_calls"][0]["tool"] == "update_job_posting"
        assert result["tool_calls"][0]["arguments"]["status"] == "Dismissed"

    def test_select_get_job_tool(self) -> None:
        """get_job intent should select get_job_posting tool."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Tell me about job 123",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "get_job",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": "job-123",
            },
            "target_job_id": "job-123",
        }

        result = select_tools(state)

        assert "tool_calls" in result
        assert len(result["tool_calls"]) > 0
        assert result["tool_calls"][0]["tool"] == "get_job_posting"


# =============================================================================
# Ambiguity Resolution Tests (§4.4)
# =============================================================================


class TestAmbiguityResolution:
    """Tests for ambiguity resolution and clarification."""

    def test_clarification_sets_human_input_flag(self) -> None:
        """Clarification should set requires_human_input to True."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Dismiss that one",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "dismiss_job",
                "confidence": 0.5,
                "requires_tools": True,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        result = request_clarification(state)

        assert result["requires_human_input"] is True

    def test_clarification_adds_message(self) -> None:
        """Clarification should add assistant message asking for clarification."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Dismiss that one",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "dismiss_job",
                "confidence": 0.5,
                "requires_tools": True,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        result = request_clarification(state)

        assert len(result["messages"]) > 0
        last_message = result["messages"][-1]
        assert last_message["role"] == "assistant"
        # Should ask which job they mean
        assert "which" in last_message["content"].lower()

    def test_missing_target_triggers_clarification(self) -> None:
        """Action on unspecified target should trigger clarification."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Favorite it",
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "favorite_job",
                "confidence": 0.85,
                "requires_tools": True,
                "target_resource": None,  # No target specified
            },
            "target_job_id": None,
        }

        assert needs_clarification(state) is True


# =============================================================================
# Response Formatting Tests (§4.5)
# =============================================================================


class TestResponseFormatting:
    """Tests for response formatting."""

    def test_format_job_list_response(self) -> None:
        """Job list should be formatted compactly."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show me jobs",
            "tool_calls": [],
            "tool_results": [
                {
                    "tool": "list_job_postings",
                    "result": {
                        "data": [
                            {
                                "id": "job-1",
                                "company_name": "Acme Corp",
                                "title": "Software Engineer",
                                "fit_score": 85,
                            },
                            {
                                "id": "job-2",
                                "company_name": "TechCo",
                                "title": "Product Manager",
                                "fit_score": 72,
                            },
                        ]
                    },
                    "error": None,
                }
            ],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "list_jobs",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": None,
            },
            "target_job_id": None,
        }

        result = format_response(state)

        assert "messages" in result
        last_message = result["messages"][-1]
        assert last_message["role"] == "assistant"
        # Should contain job info
        assert (
            "Acme" in last_message["content"]
            or "acme" in last_message["content"].lower()
        )

    def test_format_confirmation_response(self) -> None:
        """Status update should be brief confirmation."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Favorite job 123",
            "tool_calls": [],
            "tool_results": [
                {
                    "tool": "update_job_posting",
                    "result": {
                        "data": {
                            "id": "job-123",
                            "is_favorite": True,
                            "title": "Software Engineer",
                            "company_name": "Acme Corp",
                        }
                    },
                    "error": None,
                }
            ],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "favorite_job",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": "job-123",
            },
            "target_job_id": "job-123",
        }

        result = format_response(state)

        assert "messages" in result
        last_message = result["messages"][-1]
        # Should be a short confirmation
        assert len(last_message["content"]) < 200

    def test_format_error_response(self) -> None:
        """Error should explain what went wrong and suggest action."""
        state: ChatAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": "Show job 999",
            "tool_calls": [],
            "tool_results": [
                {
                    "tool": "get_job_posting",
                    "result": None,
                    "error": "Job posting not found",
                }
            ],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "classified_intent": {
                "type": "get_job",
                "confidence": 0.95,
                "requires_tools": True,
                "target_resource": "job-999",
            },
            "target_job_id": "job-999",
        }

        result = format_response(state)

        assert "messages" in result
        last_message = result["messages"][-1]
        # Should explain the error
        assert (
            "not found" in last_message["content"].lower()
            or "couldn't" in last_message["content"].lower()
        )


# =============================================================================
# Graph Structure Tests (§15.1)
# =============================================================================


class TestGraphStructure:
    """Tests for Chat Agent graph structure."""

    def test_graph_has_required_nodes(self) -> None:
        """Chat graph should have all required nodes."""
        graph = create_chat_graph()

        # Check that expected nodes exist
        expected_nodes = [
            "receive_message",
            "classify_intent",
            "select_tools",
            "execute_tools",
            "generate_response",
            "request_clarification",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_graph_has_entry_point(self) -> None:
        """Chat graph should have entry point set."""
        graph = create_chat_graph()

        # Verify the entry point is set by checking the compiled graph's structure
        compiled = graph.compile()
        # LangGraph compiled graphs have a get_graph() method
        graph_draw = compiled.get_graph()
        # The graph should have receive_message as a node
        assert "receive_message" in graph_draw.nodes
        # Verify there's an edge from __start__ to receive_message by checking
        # that the first real node after __start__ is receive_message
        # The graph structure shows edges as (source, target) tuples
        edges = list(graph_draw.edges)
        start_edge = next((e for e in edges if e[0] == "__start__"), None)
        assert start_edge is not None
        assert start_edge[1] == "receive_message"

    def test_graph_compiles_successfully(self) -> None:
        """Chat graph should compile without errors."""
        graph = create_chat_graph()
        compiled = graph.compile()

        assert compiled is not None
