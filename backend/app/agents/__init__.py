"""Agent definitions and utilities for Zentropy Scout.

REQ-007 §3: LangGraph Framework

LangGraph is used for the Chat Agent only. Other agents (Onboarding,
Ghostwriter, Scouter, Strategist) have been replaced by direct service
calls in ``app.services``.

Modules:
    state: LangGraph state schemas for the Chat Agent (REQ-007 §3.2)
    checkpoint: Checkpointer and graph config utilities (REQ-007 §3.3)
    chat: User-facing conversational interface (REQ-007 §4)
"""

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
    # Strategist Prompts
    "NON_NEGOTIABLES_SYSTEM_PROMPT",
    "SCORE_RATIONALE_SYSTEM_PROMPT",
    "build_non_negotiables_prompt",
    "build_score_rationale_prompt",
]
