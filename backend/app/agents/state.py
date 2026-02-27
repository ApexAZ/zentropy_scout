"""LangGraph state schemas for the Chat Agent.

REQ-007 §3: LangGraph Framework

LangGraph is used for the Chat Agent, which is the only graph-based agent.
Other agents (Onboarding, Ghostwriter, Scouter, Strategist) have been replaced
by direct service calls — see ``app.services`` for those implementations.

The Chat Agent uses LangGraph for:

1. Streaming - Token-by-token streaming support for chat responses, providing
   responsive UX during generation.

2. State Management - Typed state schemas with automatic serialization ensure
   consistent state across checkpoints and provide type safety.

3. Tool Calling - Native tool/function binding integrates with the Claude API's
   tool calling feature, allowing the agent to invoke API endpoints as tools.

Architecture:
    ┌─────────────────┐
    │  BaseAgentState │  Common fields (user context, messages, control flow)
    └────────┬────────┘
             │
             ▼
        ChatAgentState    Extends with classified_intent, target_job_id
"""

from enum import Enum
from typing import Any, TypedDict


class CheckpointReason(str, Enum):
    """Reasons for checkpointing and pausing graph execution.

    REQ-007 §3.3: Checkpoint Triggers

    These reasons are stored in state to communicate why the graph paused
    and what action is needed to resume.
    """

    APPROVAL_NEEDED = "approval_needed"
    """User must approve generated content before proceeding."""

    CLARIFICATION_NEEDED = "clarification_needed"
    """User must answer a question to continue."""

    LONG_RUNNING_TASK = "long_running_task"
    """Task checkpoint for resumption after long-running operation."""

    ERROR = "error"
    """Error occurred; user guidance needed to proceed."""


class BaseAgentState(TypedDict, total=False):
    """Base state schema shared by all agents.

    REQ-007 §3.2: All agents share this common state structure with
    agent-specific extensions.

    Attributes:
        user_id: User's ID for tenant isolation. All operations filter by this.
        persona_id: Active persona for the user. Determines context for
            job matching, generation, etc.
        messages: Conversation history as list of message dicts.
            Format: [{"role": "user"|"assistant", "content": str}]
        current_message: The current message being processed. None if no
            active message.
        tool_calls: List of tool call requests made by the agent.
            Format: [{"tool": str, "arguments": dict}]
        tool_results: Results from tool executions.
            Format: [{"tool": str, "result": Any, "error": str|None}]
        next_action: Optional hint for the next node to execute.
            Used for explicit routing when conditional edges aren't sufficient.
        requires_human_input: Flag indicating the graph should pause for HITL.
            When True, the graph checkpoints and waits for user input.
        checkpoint_reason: Why the graph paused. Stored for context when
            resuming. Should be a CheckpointReason value or descriptive string.
    """

    # User context
    user_id: str
    persona_id: str

    # Conversation
    # Any: Message format follows LLM provider conventions (role, content, etc.)
    # and may include provider-specific fields. Defining a strict TypedDict would
    # couple us to a specific provider's message format.
    messages: list[dict[str, Any]]
    current_message: str | None

    # Tool execution
    # Any: Tool call/result structures vary by tool and may include dynamic arguments.
    # The agent framework handles these generically; specific tools validate their own args.
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]

    # Control flow
    next_action: str | None
    requires_human_input: bool
    checkpoint_reason: str | None


class ClassifiedIntent(TypedDict, total=False):
    """Classified user intent from the Chat Agent.

    Attributes:
        type: Intent type (e.g., "onboarding_request", "draft_materials",
            "job_search", "direct_question").
        confidence: Classification confidence (0.0-1.0).
        requires_tools: Whether this intent requires tool execution.
        target_resource: Optional target resource ID (job posting, persona, etc.).
    """

    type: str
    confidence: float
    requires_tools: bool
    target_resource: str | None


class ChatAgentState(BaseAgentState, total=False):
    """State schema for the Chat Agent.

    REQ-007 §4: User-facing conversational interface. Routes to tools
    or sub-graphs based on classified intent.

    Extends BaseAgentState with:
        classified_intent: Result of intent classification. Determines routing
            to tools vs sub-graphs.
        target_job_id: Job posting ID when delegating to Ghostwriter.
            Set when user requests materials for a specific job.
    """

    classified_intent: ClassifiedIntent | None
    target_job_id: str | None
