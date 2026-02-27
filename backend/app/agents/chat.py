"""Chat Agent implementation.

REQ-007 §4: Chat Agent

The Chat Agent is the user-facing conversational interface that:
- Recognizes user intent from natural language
- Selects appropriate tools or delegates to sub-graphs
- Manages conversation context
- Streams responses via SSE
- Asks clarifying questions when needed

Architecture:
    User Message → classify_intent → route_by_intent →
        ├─ tool_call → select_tools → execute_tools → generate_response
        ├─ onboarding → delegate_onboarding → generate_response
        ├─ ghostwriter → delegate_ghostwriter → generate_response
        ├─ clarification_needed → request_clarification
        └─ direct_response → generate_response
    → stream_response → END

Tool Categories (REQ-007 §4.2):
    - Job Management: list_jobs, get_job, favorite_job, dismiss_job
    - Application: list_applications, get_application, mark_applied
    - Resume/Cover Letter: list_base_resumes, approve_variant, etc.
    - Persona: get_persona, update_persona, add_skill
    - Search/Query: find_jobs_by_company, find_high_match_jobs
    - Agent Invocation: invoke_onboarding, invoke_ghostwriter

Intent Types (REQ-007 §4.3):
    - list_jobs: "Show me new jobs"
    - get_job: "What's my fit for job 123?"
    - favorite_job: "Favorite the Acme one"
    - dismiss_job: "Dismiss that one"
    - draft_materials: "Draft materials for this job"
    - onboarding_request: "Update my skills"
    - direct_question: "How does job matching work?"
"""

import logging
import re
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.state import ChatAgentState, CheckpointReason, ClassifiedIntent
from app.core.errors import APIError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# =============================================================================
# Intent Patterns
# =============================================================================

# WHY: Pattern-based classification for MVP. This provides fast, deterministic
# intent recognition without requiring LLM calls. Future enhancement: use LLM
# for ambiguous cases or complex intent recognition.

INTENT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    # (intent_type, pattern, base_confidence)
    ("list_jobs", re.compile(r"show\s+(?:me\s+)?(?:new\s+)?jobs?", re.IGNORECASE), 0.9),
    ("list_jobs", re.compile(r"list\s+(?:all\s+)?jobs?", re.IGNORECASE), 0.9),
    (
        "list_jobs",
        re.compile(r"what\s+jobs?\s+(?:do\s+i\s+have|are\s+there)", re.IGNORECASE),
        0.85,
    ),
    (
        "get_job",
        re.compile(r"(?:tell\s+me\s+about|show|get)\s+job\s+(\S+)", re.IGNORECASE),
        0.9,
    ),
    (
        "get_job",
        re.compile(
            r"what(?:'s|\s+is)\s+(?:my\s+)?fit\s+for\s+job\s+(\S+)", re.IGNORECASE
        ),
        0.85,
    ),
    (
        "favorite_job",
        re.compile(r"favorite\s+(?:the\s+)?(?:job\s+)?(\S+)?", re.IGNORECASE),
        0.85,
    ),
    (
        "favorite_job",
        re.compile(r"(?:add|mark)\s+(?:to\s+)?favorites?", re.IGNORECASE),
        0.8,
    ),
    (
        "dismiss_job",
        re.compile(r"dismiss\s+(?:the\s+)?(?:job\s+)?(\S+)?", re.IGNORECASE),
        0.85,
    ),
    (
        "dismiss_job",
        re.compile(r"(?:remove|hide)\s+(?:the\s+)?(?:job\s+)?(\S+)?", re.IGNORECASE),
        0.8,
    ),
    (
        "draft_materials",
        re.compile(
            r"draft\s+(?:materials?\s+)?(?:for\s+)?(?:job\s+)?(\S+)?", re.IGNORECASE
        ),
        0.9,
    ),
    (
        "draft_materials",
        re.compile(
            r"(?:generate|create|write)\s+(?:a\s+)?(?:resume|cover\s+letter)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    (
        "onboarding_request",
        re.compile(r"update\s+my\s+(?:skills?|profile|info)", re.IGNORECASE),
        0.9,
    ),
    (
        "onboarding_request",
        re.compile(r"(?:add|edit)\s+(?:my\s+)?(?:skills?|experience)", re.IGNORECASE),
        0.85,
    ),
    (
        "onboarding_request",
        re.compile(r"start\s+(?:the\s+)?onboarding", re.IGNORECASE),
        0.95,
    ),
    (
        "direct_question",
        re.compile(
            r"(?:how|what|why|when|where)\s+(?:does|is|are|do|can)", re.IGNORECASE
        ),
        0.8,
    ),
    (
        "direct_question",
        re.compile(r"(?:explain|tell\s+me\s+about)\s+(?:how|what)", re.IGNORECASE),
        0.8,
    ),
]

# Intent types that require tools vs. sub-graph delegation
TOOL_INTENTS = {"list_jobs", "get_job", "favorite_job", "dismiss_job"}
SUBGRAPH_INTENTS = {"draft_materials", "onboarding_request"}

# Confidence threshold for routing (below this, ask for clarification)
CONFIDENCE_THRESHOLD = 0.7

# Defense-in-depth: bound regex input to prevent ReDoS on unbounded messages
_MAX_REGEX_INPUT_LENGTH = 2000

_TOOL_GHOSTWRITER = "invoke_ghostwriter"


# =============================================================================
# Intent Classification (§4.3)
# =============================================================================


def _extract_target_resource(match: re.Match[str]) -> str | None:
    """Extract and clean target resource from regex match."""
    if not match.groups():
        return None
    target = match.group(1)
    if target and target.lower() in ("the", "it", "that", "this", "one"):
        return None
    return target


def classify_intent(state: ChatAgentState) -> ChatAgentState:
    """Classify user intent from the current message.

    REQ-007 §4.3: Intent Recognition

    Uses pattern matching to classify user messages into known intent types.
    Returns a ClassifiedIntent with type, confidence, and whether tools are
    required. Messages are truncated to _MAX_REGEX_INPUT_LENGTH characters
    before matching (ReDoS defense-in-depth).

    Args:
        state: Current chat agent state with current_message set.

    Returns:
        Updated state with classified_intent populated.
    """
    message = state.get("current_message") or ""
    message = message.strip()[:_MAX_REGEX_INPUT_LENGTH]

    best_intent: ClassifiedIntent = {
        "type": "unknown",
        "confidence": 0.0,
        "requires_tools": False,
        "target_resource": None,
    }

    # Try each pattern and keep the best match
    for intent_type, pattern, base_confidence in INTENT_PATTERNS:
        match = pattern.search(message)
        if not match or base_confidence <= best_intent["confidence"]:
            continue
        best_intent = {
            "type": intent_type,
            "confidence": base_confidence,
            "requires_tools": intent_type in TOOL_INTENTS,
            "target_resource": _extract_target_resource(match),
        }

    # Copy state and update with intent
    # Type annotation: dict() returns dict[str, Any] which matches ChatAgentState
    # structure since we're copying from a TypedDict. TypedDict doesn't support
    # copy() directly, so dict() is the cleanest approach.
    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]
    new_state["classified_intent"] = best_intent

    # Also set target_job_id if a job-related intent with target
    if best_intent["target_resource"] and best_intent["type"] in (
        "get_job",
        "favorite_job",
        "dismiss_job",
        "draft_materials",
    ):
        new_state["target_job_id"] = best_intent["target_resource"]

    return new_state


# =============================================================================
# Routing Logic (§15.1)
# =============================================================================


def route_by_intent(state: ChatAgentState) -> str:
    """Route to the appropriate next node based on classified intent.

    REQ-007 §15.1: Graph Spec - Chat Agent routing

    Routing logic:
    - onboarding_request → "onboarding" (delegate to Onboarding Agent)
    - draft_materials → "ghostwriter" (delegate to Ghostwriter Agent)
    - confidence < 0.7 → "clarification_needed" (ask user to clarify)
    - requires_tools → "tool_call" (execute tools)
    - else → "direct_response" (answer directly)

    Args:
        state: Current state with classified_intent set.

    Returns:
        Next node name as string.
    """
    intent = state.get("classified_intent")

    if not intent:
        return "clarification_needed"

    intent_type = intent.get("type", "unknown")
    confidence = intent.get("confidence", 0.0)
    requires_tools = intent.get("requires_tools", False)

    # Route to sub-graphs for specific intents
    if intent_type == "onboarding_request":
        return "onboarding"

    if intent_type == "draft_materials":
        return "ghostwriter"

    # Low confidence → ask for clarification
    if confidence < CONFIDENCE_THRESHOLD:
        return "clarification_needed"

    # Tool-based intents
    if requires_tools:
        return "tool_call"

    # Default to direct response
    return "direct_response"


# =============================================================================
# Tool Selection (§4.2)
# =============================================================================


def select_tools(state: ChatAgentState) -> ChatAgentState:
    """Select appropriate tools based on the classified intent.

    REQ-007 §4.2: Tool Categories

    Maps intent types to specific tool calls with arguments.

    Args:
        state: Current state with classified_intent set.

    Returns:
        Updated state with tool_calls populated.
    """
    intent = state.get("classified_intent")
    if not intent:
        return state

    intent_type = intent.get("type", "unknown")
    target = intent.get("target_resource")

    # Build tool call based on intent
    # Any: Tool arguments vary by tool type and are validated by tool implementations.
    # The structure follows {"tool": str, "arguments": dict} where arguments differ per tool.
    tool_calls: list[dict[str, Any]] = []

    if intent_type == "list_jobs":
        tool_calls.append(
            {
                "tool": "list_job_postings",
                "arguments": {
                    "status": "Discovered",
                    "sort": "-fit_score",
                },
            }
        )

    elif intent_type == "get_job":
        tool_calls.append(
            {
                "tool": "get_job_posting",
                "arguments": {
                    "job_posting_id": target or state.get("target_job_id"),
                },
            }
        )

    elif intent_type == "favorite_job":
        tool_calls.append(
            {
                "tool": "update_job_posting",
                "arguments": {
                    "job_posting_id": target or state.get("target_job_id"),
                    "is_favorite": True,
                },
            }
        )

    elif intent_type == "dismiss_job":
        tool_calls.append(
            {
                "tool": "update_job_posting",
                "arguments": {
                    "job_posting_id": target or state.get("target_job_id"),
                    "status": "Dismissed",
                },
            }
        )

    # Copy state and update
    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]
    new_state["tool_calls"] = tool_calls
    return new_state


# =============================================================================
# Ambiguity Resolution (§4.4)
# =============================================================================


def needs_clarification(state: ChatAgentState) -> bool:
    """Check if the current state requires user clarification.

    REQ-007 §4.4: Ambiguity Resolution

    Clarification is needed when:
    - Intent confidence is too low
    - Action requires a target but none was specified
    - Intent is completely unknown

    Args:
        state: Current chat agent state.

    Returns:
        True if clarification is needed.
    """
    intent = state.get("classified_intent")
    if not intent:
        return True

    # Low confidence
    if intent.get("confidence", 0.0) < CONFIDENCE_THRESHOLD:
        return True

    # Action requires target but none specified
    target_required_intents = {
        "favorite_job",
        "dismiss_job",
        "get_job",
        "draft_materials",
    }
    return (
        intent.get("type") in target_required_intents
        and not intent.get("target_resource")
        and not state.get("target_job_id")
    )


def request_clarification(state: ChatAgentState) -> ChatAgentState:
    """Request clarification from the user.

    REQ-007 §4.4: Ambiguity Resolution

    Generates an appropriate clarification message based on what's unclear
    and sets the requires_human_input flag to pause the graph.

    Args:
        state: Current state requiring clarification.

    Returns:
        Updated state with clarification message and HITL flags set.
    """
    intent = state.get("classified_intent")
    intent_type = intent.get("type") if intent else "unknown"

    # Build clarification message based on what's unclear
    # WHY: Check for missing target FIRST, since this is more specific than low
    # confidence. A dismiss_job intent with 0.5 confidence but missing target
    # should ask "which job" not "please rephrase".
    target_required_intents = {"favorite_job", "dismiss_job", "get_job"}
    has_target = intent and (
        intent.get("target_resource") or state.get("target_job_id")
    )

    if intent_type in target_required_intents and not has_target:
        message = "Which job would you like me to work with? You can specify the job ID or company name."
    elif intent_type == "draft_materials" and not has_target:
        message = "Which job would you like me to draft materials for? Please specify the job ID or company name."
    elif intent_type == "unknown" or (
        intent and intent.get("confidence", 0.0) < CONFIDENCE_THRESHOLD
    ):
        message = "I'm not sure what you'd like to do. Could you please rephrase your request?"
    else:
        message = "Could you provide more details about what you'd like me to do?"

    # Copy state and update
    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]

    # Add clarification message
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "assistant",
            "content": message,
        }
    )
    new_state["messages"] = messages

    # Set HITL flags
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value

    return new_state


# =============================================================================
# Response Formatting (§4.5)
# =============================================================================


def _format_job_list(data: dict) -> str:
    """Format job listing results into a readable list."""
    jobs = data.get("data", [])
    if not jobs:
        return "No jobs found matching your criteria."
    lines = ["Here are your jobs:\n"]
    for job in jobs[:10]:
        score = job.get("fit_score", "N/A")
        company = job.get("company_name", "Unknown")
        title = job.get("title", "Untitled")
        lines.append(f"- {company}: {title} (Fit: {score}%)")
    return "\n".join(lines)


def _format_job_details(data: dict) -> str:
    """Format single job posting details."""
    job = data.get("data", data)
    company = job.get("company_name", "Unknown")
    title = job.get("title", "Untitled")
    score = job.get("fit_score", "N/A")
    return f"**{title}** at **{company}**\nFit Score: {score}%"


def _format_job_update(data: dict, intent_type: str) -> str:
    """Format job update confirmation."""
    job = data.get("data", data)
    title = job.get("title", "Job")
    company = job.get("company_name", "")
    if intent_type == "favorite_job":
        return f"Added {title} at {company} to your favorites."
    if intent_type == "dismiss_job":
        return f"Dismissed {title} at {company}."
    return f"Updated {title} at {company}."


def format_response(state: ChatAgentState) -> ChatAgentState:
    """Format the response based on tool results.

    REQ-007 §4.5: Response Formatting

    Formats tool results into human-readable responses:
    - Job lists: compact list with score, company, title
    - Single job: structured details
    - Confirmations: brief acknowledgment
    - Errors: explanation with suggested action

    Args:
        state: Current state with tool_results populated.

    Returns:
        Updated state with formatted response message.
    """
    tool_results = state.get("tool_results", [])
    intent = state.get("classified_intent")
    intent_type = intent.get("type") if intent else "unknown"

    response = ""
    for result in tool_results:
        tool = result.get("tool", "")
        data = result.get("result")
        error = result.get("error")

        if error:
            response = f"I couldn't complete that request. {error}"
            break
        if tool == "list_job_postings" and data:
            response = _format_job_list(data)
        elif tool == "get_job_posting" and data:
            response = _format_job_details(data)
        elif tool == "update_job_posting" and data:
            response = _format_job_update(data, intent_type or "")

    if not response:
        response = "Done."

    # Copy state and add response message
    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "assistant",
            "content": response,
        }
    )
    new_state["messages"] = messages

    return new_state


# =============================================================================
# Graph Node Functions
# =============================================================================


def receive_message(state: ChatAgentState) -> ChatAgentState:
    """Parse and store the incoming user message.

    Entry point for the chat graph. Extracts the current message from
    the conversation history if not already set.

    Args:
        state: Incoming chat state.

    Returns:
        State with current_message set.
    """
    # If current_message is already set, use it
    if state.get("current_message"):
        return state

    # Otherwise, extract from the last user message
    messages = state.get("messages", [])
    current_message = None

    for msg in reversed(messages):
        if msg.get("role") == "user":
            current_message = msg.get("content", "")
            break

    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_message"] = current_message
    return new_state


def execute_tools(state: ChatAgentState) -> ChatAgentState:
    """Execute the selected tools.

    Note: This is a placeholder. Actual tool execution will be implemented
    when the service layer is complete. For now, this just marks the tools
    as executed with empty results.

    Args:
        state: State with tool_calls populated.

    Returns:
        State with tool_results populated.
    """
    # WHY: Placeholder for tool execution. The actual implementation will use
    # the AgentAPIClient to execute tools. This is structured so tests can
    # mock tool_results directly.
    # FUTURE: Implement tool execution via AgentAPIClient in Phase 2.3+

    # Mark tools as "executed" (results will be mocked in tests or filled
    # by actual service calls in production)
    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]
    new_state["tool_results"] = state.get("tool_results", [])

    return new_state


def generate_response(state: ChatAgentState) -> ChatAgentState:
    """Generate response from tool results or direct answer.

    This is a pass-through to format_response for now. Future enhancement
    will add LLM-based response generation.

    Args:
        state: State with tool_results or ready for direct response.

    Returns:
        State with response message added.
    """
    return format_response(state)


def stream_response(state: ChatAgentState) -> ChatAgentState:
    """Prepare response for SSE streaming.

    Note: This is a placeholder. Actual SSE streaming is handled by the
    API layer (REQ-006 §2.5). This node marks the response as ready.

    Args:
        state: State with response message.

    Returns:
        State unchanged (streaming handled externally).
    """
    return state


async def delegate_onboarding(state: ChatAgentState) -> ChatAgentState:  # noqa: RUF029
    """Handle onboarding-related requests via chat.

    REQ-019 §5: Onboarding is now form-based (frontend wizard). Chat requests
    for onboarding or profile updates are redirected to the appropriate page.

    Note: async required by LangGraph graph node registration (ainvoke).

    Args:
        state: Current chat state.

    Returns:
        State with redirect message in tool_results.
    """
    from app.agents.onboarding import detect_update_section, is_update_request

    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]
    message = state.get("current_message") or ""

    if is_update_request(message):
        section = detect_update_section(message)
        if section:
            section_display = section.replace("_", " ")
            response_msg = (
                f"To update your {section_display}, head over to the "
                "Persona Management page where you can edit each section directly."
            )
        else:
            response_msg = (
                "To update your profile, head over to the Persona Management "
                "page where you can edit each section directly."
            )
    else:
        response_msg = (
            "Onboarding is handled through the setup wizard. "
            "You can access it from the onboarding page."
        )

    new_state["tool_results"] = [
        {
            "tool": "invoke_onboarding",
            "result": {"status": "redirected", "message": response_msg},
            "error": None,
        }
    ]

    return new_state


async def delegate_ghostwriter(state: ChatAgentState) -> ChatAgentState:
    """Delegate to ContentGenerationService for material generation.

    REQ-018 §7: Replaces ghostwriter graph invocation with direct service call.

    Args:
        state: Current chat state.

    Returns:
        State with ghostwriter result in tool_results.
    """
    from app.services.content_generation_service import ContentGenerationService

    new_state: ChatAgentState = dict(state)  # type: ignore[assignment]

    target_job_id = state.get("target_job_id")
    if not target_job_id:
        new_state["tool_results"] = [
            {
                "tool": _TOOL_GHOSTWRITER,
                "result": None,
                "error": "No target job specified for material generation.",
            }
        ]
        return new_state

    try:
        service = ContentGenerationService()
        result = await service.generate(
            user_id=state["user_id"],
            persona_id=state["persona_id"],
            job_posting_id=target_job_id,
        )
        new_state["tool_results"] = [
            {
                "tool": _TOOL_GHOSTWRITER,
                "result": {
                    "status": "completed",
                    "has_cover_letter": result.cover_letter is not None,
                },
                "error": None,
            }
        ]
    # SECURITY: e.message is safe to forward — NotFoundError/ValidationError/APIError
    # messages are developer-authored, user-facing strings (no paths, SQL, or stack traces).
    except NotFoundError as e:
        logger.warning("Content generation resource not found: %s", e.message)
        new_state["tool_results"] = [
            {
                "tool": _TOOL_GHOSTWRITER,
                "result": None,
                "error": e.message,
            }
        ]
    except ValidationError as e:
        logger.warning("Content generation validation error: %s", e.message)
        new_state["tool_results"] = [
            {
                "tool": _TOOL_GHOSTWRITER,
                "result": None,
                "error": e.message,
            }
        ]
    except APIError as e:
        logger.error("Content generation API error: %s", e.message)
        new_state["tool_results"] = [
            {
                "tool": _TOOL_GHOSTWRITER,
                "result": None,
                "error": e.message,
            }
        ]
    except Exception:
        logger.exception("Content generation failed unexpectedly")
        new_state["tool_results"] = [
            {
                "tool": _TOOL_GHOSTWRITER,
                "result": None,
                "error": "Material generation could not be completed. Please try again.",
            }
        ]

    return new_state


def check_tool_result(state: ChatAgentState) -> str:
    """Check tool execution result for routing.

    Routes based on tool execution outcome:
    - success: proceed to generate_response
    - needs_more_tools: loop back to select_tools (not currently used)
    - error: proceed to generate_response (which will format error)

    Args:
        state: State after tool execution.

    Returns:
        Next node name.
    """
    tool_results = state.get("tool_results", [])

    for result in tool_results:
        if result.get("error"):
            return "error"

    return "success"


# =============================================================================
# Graph Construction (§15.1)
# =============================================================================


def create_chat_graph() -> StateGraph:
    """Create the Chat Agent LangGraph graph.

    REQ-007 §15.1: Graph Spec - Chat Agent

    Graph structure:
        receive_message → classify_intent → [conditional routing] →
            ├─ tool_call → select_tools → execute_tools → generate_response
            ├─ onboarding → delegate_onboarding → generate_response
            ├─ ghostwriter → delegate_ghostwriter → generate_response
            ├─ clarification_needed → request_clarification → END
            └─ direct_response → generate_response
        → stream_response → END

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(ChatAgentState)

    # Add nodes
    graph.add_node("receive_message", receive_message)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("select_tools", select_tools)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("generate_response", generate_response)
    graph.add_node("stream_response", stream_response)
    graph.add_node("delegate_onboarding", delegate_onboarding)
    graph.add_node("delegate_ghostwriter", delegate_ghostwriter)
    graph.add_node("request_clarification", request_clarification)

    # Set entry point
    graph.set_entry_point("receive_message")

    # Linear edges
    graph.add_edge("receive_message", "classify_intent")

    # Conditional routing from classify_intent
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "tool_call": "select_tools",
            "onboarding": "delegate_onboarding",
            "ghostwriter": "delegate_ghostwriter",
            "clarification_needed": "request_clarification",
            "direct_response": "generate_response",
        },
    )

    # Tool execution flow
    graph.add_edge("select_tools", "execute_tools")
    graph.add_conditional_edges(
        "execute_tools",
        check_tool_result,
        {
            "success": "generate_response",
            "error": "generate_response",
        },
    )

    # Sub-graph returns
    graph.add_edge("delegate_onboarding", "generate_response")
    graph.add_edge("delegate_ghostwriter", "generate_response")

    # Clarification ends the flow (HITL checkpoint)
    graph.add_edge("request_clarification", "stream_response")

    # Final output
    graph.add_edge("generate_response", "stream_response")
    graph.add_edge("stream_response", END)

    return graph


# Compiled graph singleton
_chat_graph: StateGraph | None = None


def get_chat_graph() -> StateGraph:
    """Get the compiled chat graph.

    Returns a singleton compiled graph instance for use in the API.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = create_chat_graph().compile()  # type: ignore[assignment]
    return _chat_graph  # type: ignore[return-value]
