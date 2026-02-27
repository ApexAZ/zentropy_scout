"""Agent definitions and utilities for Zentropy Scout.

REQ-007 §3: LangGraph Framework

LangGraph is used for the Chat Agent only. Other agents (Onboarding,
Ghostwriter, Scouter, Strategist) have been replaced by direct service
calls in ``app.services``.

Modules:
    base: Agent utilities and API client abstraction
    state: LangGraph state schemas for the Chat Agent (REQ-007 §3.2)
    checkpoint: Checkpointer and graph config utilities (REQ-007 §3.3)
    chat: User-facing conversational interface (REQ-007 §4)
    onboarding: Post-onboarding update utilities (REQ-019 §5)
    ghostwriter: Draft/regeneration detection utilities (REQ-007 §8)
"""

from app.agents.base import (
    AgentAPIClient,
    BaseAgentClient,
    HTTPAgentClient,
    LocalAgentClient,
    get_agent_client,
    reset_agent_client,
)
from app.agents.chat import (
    classify_intent,
    create_chat_graph,
    format_response,
    get_chat_graph,
    needs_clarification,
    request_clarification,
    route_by_intent,
    select_tools,
)
from app.agents.checkpoint import (
    create_checkpointer,
    create_graph_config,
)
from app.agents.ghostwriter import (
    DRAFT_REQUEST_PATTERNS,
    REGENERATION_PATTERNS,
    TriggerType,
    is_draft_request,
    is_regeneration_request,
    should_auto_draft,
)
from app.agents.onboarding import (
    ACHIEVEMENT_STORY_PROMPT,
    SECTIONS_REQUIRING_RESCORE,
    VOICE_PROFILE_DERIVATION_PROMPT,
    WORK_HISTORY_EXPANSION_PROMPT,
    detect_update_section,
    format_gathered_data_summary,
    get_achievement_story_prompt,
    get_affected_embeddings,
    get_update_completion_message,
    get_voice_profile_prompt,
    get_work_history_prompt,
    is_update_request,
    should_start_onboarding,
)
from app.agents.state import (
    BaseAgentState,
    ChatAgentState,
    CheckpointReason,
)
from app.prompts.strategist import (
    NON_NEGOTIABLES_SYSTEM_PROMPT,
    SCORE_RATIONALE_SYSTEM_PROMPT,
    build_non_negotiables_prompt,
    build_score_rationale_prompt,
)

__all__ = [
    # API Client
    "AgentAPIClient",
    "BaseAgentClient",
    "HTTPAgentClient",
    "LocalAgentClient",
    "get_agent_client",
    "reset_agent_client",
    # Checkpointing
    "create_checkpointer",
    "create_graph_config",
    # State Schemas
    "BaseAgentState",
    "ChatAgentState",
    "CheckpointReason",
    # Chat Agent
    "classify_intent",
    "create_chat_graph",
    "format_response",
    "get_chat_graph",
    "needs_clarification",
    "request_clarification",
    "route_by_intent",
    "select_tools",
    # Onboarding Utilities
    "ACHIEVEMENT_STORY_PROMPT",
    "SECTIONS_REQUIRING_RESCORE",
    "VOICE_PROFILE_DERIVATION_PROMPT",
    "WORK_HISTORY_EXPANSION_PROMPT",
    "detect_update_section",
    "format_gathered_data_summary",
    "get_achievement_story_prompt",
    "get_affected_embeddings",
    "get_update_completion_message",
    "get_voice_profile_prompt",
    "get_work_history_prompt",
    "is_update_request",
    "should_start_onboarding",
    # Ghostwriter
    "DRAFT_REQUEST_PATTERNS",
    "REGENERATION_PATTERNS",
    "TriggerType",
    "is_draft_request",
    "is_regeneration_request",
    "should_auto_draft",
    # Strategist Prompts
    "NON_NEGOTIABLES_SYSTEM_PROMPT",
    "SCORE_RATIONALE_SYSTEM_PROMPT",
    "build_non_negotiables_prompt",
    "build_score_rationale_prompt",
]
