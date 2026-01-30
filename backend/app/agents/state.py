"""LangGraph agent state schemas.

REQ-007 §3: LangGraph Framework

WHY LANGGRAPH:
LangGraph is chosen for the agent framework because it provides:

1. HITL Checkpointing - Built-in state persistence allows pausing and resuming
   workflows when human input is needed (e.g., approving generated content,
   clarifying requirements, handling errors).

2. Tool Calling - Native tool/function binding integrates with the Claude API's
   tool calling feature, allowing agents to invoke API endpoints as tools.

3. Streaming - Token-by-token streaming support for chat responses, providing
   responsive UX during generation.

4. Sub-graphs - Agents can invoke other agents as nodes, enabling the Chat Agent
   to delegate to specialized agents (Onboarding, Ghostwriter, etc.).

5. State Management - Typed state schemas with automatic serialization ensure
   consistent state across checkpoints and provide type safety.

This module defines the state schemas used by all agents. Each agent extends
BaseAgentState with agent-specific fields while maintaining compatibility with
LangGraph's state management.

Architecture:
    ┌─────────────────┐
    │  BaseAgentState │  Common fields for all agents
    └────────┬────────┘
             │
    ┌────────┼────────┬────────────┬────────────┐
    ▼        ▼        ▼            ▼            ▼
  Chat   Onboarding  Scouter  Strategist  Ghostwriter
  State    State     State      State       State
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


class OnboardingState(BaseAgentState, total=False):
    """State schema for the Onboarding Agent.

    REQ-007 §5: Creates Persona from user interview. Persists step for
    resume after HITL interrupts.

    Extends BaseAgentState with:
        current_step: Current step in the onboarding flow. Persisted for
            resumption. Values: "resume_upload", "basic_info", "work_history",
            "skills", "achievement_stories", "non_negotiables", "voice_profile",
            "base_resume_setup".
        gathered_data: Data accumulated from user responses. Keyed by step name.
        skipped_sections: List of optional sections the user chose to skip.
        pending_question: Question waiting for user response. Set when paused.
        user_response: User's response to pending_question. Set when resuming.
        is_partial_update: True if this is a post-onboarding partial update
            (REQ-007 §5.5) vs. full onboarding flow. Affects completion behavior.
    """

    current_step: str
    # Any: Accumulated interview responses vary by step (text, lists, nested objects).
    # Each step's data is validated when used, not at state level.
    gathered_data: dict[str, Any]
    skipped_sections: list[str]
    pending_question: str | None
    user_response: str | None
    is_partial_update: bool


class ScouterState(BaseAgentState, total=False):
    """State schema for the Scouter Agent.

    REQ-007 §6: Discovers and ingests jobs from configured sources.

    Extends BaseAgentState with:
        enabled_sources: List of enabled job sources for this user.
            E.g., ["LinkedIn", "Indeed", "Manual"].
        discovered_jobs: Jobs found during the current polling cycle.
            Includes raw data before deduplication.
        processed_jobs: Jobs after deduplication and validation.
        error_sources: Sources that failed during polling.
    """

    enabled_sources: list[str]
    # Any: Raw job data varies by source (LinkedIn, Indeed, Manual) and includes
    # source-specific fields. Normalized to JobPosting schema during processing.
    discovered_jobs: list[dict[str, Any]]
    processed_jobs: list[dict[str, Any]]
    error_sources: list[str]


class ScoreResult(TypedDict, total=False):
    """Score result for a single job posting.

    Attributes:
        job_posting_id: The scored job's ID.
        fit_score: Fit score (0-100).
        stretch_score: Stretch score (0-100).
        explanation: Human-readable explanation of scores.
        filtered_reason: If filtered out, why (e.g., "salary_below_minimum").
    """

    job_posting_id: str
    fit_score: float | None
    stretch_score: float | None
    explanation: str | None
    filtered_reason: str | None


class StrategistState(BaseAgentState, total=False):
    """State schema for the Strategist Agent.

    REQ-007 §7: Applies scoring to jobs. Depends on REQ-008 (Scoring Engine).

    Extends BaseAgentState with:
        persona_embedding_version: Embedding version for freshness check.
            If this doesn't match the persona's current version, embeddings
            are stale and need regeneration.
        jobs_to_score: Job posting IDs awaiting scoring.
        scored_jobs: Scoring results for processed jobs.
        filtered_jobs: Jobs filtered out by non-negotiables.
    """

    persona_embedding_version: int | None
    jobs_to_score: list[str]
    scored_jobs: list[ScoreResult]
    filtered_jobs: list[str]


class GeneratedContent(TypedDict, total=False):
    """Generated resume or cover letter content.

    Attributes:
        content: The generated content (markdown or structured).
        reasoning: Agent's reasoning for choices made.
        stories_used: Achievement story IDs incorporated.
    """

    content: str
    reasoning: str
    stories_used: list[str]


class GhostwriterState(BaseAgentState, total=False):
    """State schema for the Ghostwriter Agent.

    REQ-007 §8: Generates tailored resumes and cover letters.

    Extends BaseAgentState with:
        job_posting_id: Target job for content generation.
        selected_base_resume_id: Base resume selected for tailoring.
        existing_variant_id: Existing JobVariant if one exists (race condition
            prevention per REQ-007 §10.4.2).
        generated_resume: Generated/tailored resume content.
        generated_cover_letter: Generated cover letter content.
        feedback: User feedback for regeneration (if any).
    """

    job_posting_id: str | None
    selected_base_resume_id: str | None
    existing_variant_id: str | None
    generated_resume: GeneratedContent | None
    generated_cover_letter: GeneratedContent | None
    feedback: str | None
