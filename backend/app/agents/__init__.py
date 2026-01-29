"""LangGraph agent definitions for Zentropy Scout.

REQ-007 §3: LangGraph Framework

This package contains all agent implementations following the API-mediated
architecture (REQ-006 §2.3). Agents are internal API clients that call the
API layer for all writes - they do NOT access the database directly.

WHY LANGGRAPH (REQ-007 §3.1):
    - HITL Checkpointing: Built-in state persistence for pause/resume
    - Tool Calling: Native tool/function binding for API integration
    - Streaming: Token-by-token streaming for responsive chat UX
    - Sub-graphs: Agents can invoke other agents as nodes
    - State Management: Typed state schemas with automatic serialization

Modules:
    base: Agent utilities and API client abstraction
    state: State schemas for all agents (REQ-007 §3.2)
    checkpoint: Checkpointing and HITL utilities (REQ-007 §3.3)
    chat: User-facing conversational interface (REQ-007 §4)
    onboarding: Persona creation interview (REQ-007 §5)
    scouter: Job discovery and ingestion (REQ-007 §6)
    strategist: Job scoring and matching (REQ-007 §7)
    ghostwriter: Resume/cover letter generation (REQ-007 §8)
"""

from app.agents.base import (
    AgentAPIClient,
    BaseAgentClient,
    HTTPAgentClient,
    LocalAgentClient,
    get_agent_client,
    reset_agent_client,
)
from app.agents.checkpoint import (
    create_checkpointer,
    create_graph_config,
    request_human_input,
    resume_from_checkpoint,
)
from app.agents.state import (
    BaseAgentState,
    ChatAgentState,
    CheckpointReason,
    GhostwriterState,
    OnboardingState,
    ScouterState,
    StrategistState,
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
    "request_human_input",
    "resume_from_checkpoint",
    # State Schemas
    "BaseAgentState",
    "ChatAgentState",
    "CheckpointReason",
    "GhostwriterState",
    "OnboardingState",
    "ScouterState",
    "StrategistState",
]
