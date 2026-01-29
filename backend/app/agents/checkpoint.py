"""LangGraph checkpointing and HITL utilities.

REQ-007 §3.3: Checkpointing & HITL

This module provides utilities for:
- Creating checkpointers for state persistence
- Configuring graph execution
- Implementing Human-in-the-Loop (HITL) interrupt/resume patterns

Checkpoint Storage:
    MVP uses PostgreSQL for checkpoint storage via langgraph-checkpoint-postgres.
    This integrates with the existing database infrastructure and keeps all
    data in a single location for simpler backups and deployment.

    For development/testing, MemorySaver can be used instead (no persistence).

HITL Pattern:
    Agents pause execution when human input is needed by setting:
    - requires_human_input = True
    - checkpoint_reason = <why paused>

    The graph checkpoints automatically when requires_human_input is True.
    To resume, call resume_from_checkpoint() with the user's response.
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import BaseAgentState, CheckpointReason


def create_checkpointer() -> BaseCheckpointSaver:
    """Create a checkpointer for LangGraph state persistence.

    REQ-007 §3.3: Checkpoint storage uses PostgreSQL for production
    and MemorySaver for development/testing.

    Returns:
        Configured checkpointer instance.

    Note:
        PostgreSQL checkpointer requires async context management.
        For MVP, we use MemorySaver which is simpler and sufficient
        for single-user local deployment. PostgreSQL checkpointing
        will be enabled when distributed/multi-user mode is needed.

        The PostgresCheckpoint requires connection pool setup:
        ```python
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        async with AsyncConnectionPool(conninfo=DATABASE_URL) as pool:
            checkpointer = AsyncPostgresSaver(pool)
            # Use checkpointer with graphs
        ```
    """
    # WHY: MVP uses MemorySaver for simplicity. PostgreSQL checkpointing
    # adds complexity (connection pooling, async context managers) that
    # isn't needed for single-user local deployment. The abstraction
    # allows easy switch to PostgreSQL when multi-user support is added.
    #
    # TODO: Enable PostgreSQL checkpointing for hosted/multi-user mode
    # when that feature is implemented (REQ-007 §3.3 notes TTL of 24h
    # for incomplete flows, 7 days for conversation history).

    return MemorySaver()


def create_graph_config(
    thread_id: str,
    user_id: str,
    *,
    checkpoint_ns: str = "",
) -> dict[str, Any]:
    """Create configuration dict for graph execution.

    The config is passed to graph.invoke() or graph.ainvoke() and provides:
    - Thread ID for checkpoint identification
    - User ID for tenant isolation
    - Checkpoint namespace for partitioning (optional)

    Args:
        thread_id: Unique identifier for this conversation/workflow thread.
            Used to retrieve and resume checkpoints.
        user_id: User's ID for tenant isolation. Stored with checkpoint
            to ensure users can only access their own checkpoints.
        checkpoint_ns: Optional namespace for checkpoint partitioning.
            Useful for separating different agent types or flows.

    Returns:
        Configuration dict compatible with LangGraph's invoke/ainvoke.

    Example:
        config = create_graph_config(
            thread_id="conv-abc123",
            user_id="user-456",
        )
        result = await chat_graph.ainvoke(state, config)
    """
    return {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }


def request_human_input(
    state: BaseAgentState,
    *,
    reason: CheckpointReason,
    message: str,
) -> BaseAgentState:
    """Prepare state for HITL checkpoint.

    Call this from a graph node when human input is needed. The graph
    will checkpoint after this node returns, pausing execution until
    resume_from_checkpoint() is called.

    Args:
        state: Current agent state.
        reason: Why the graph is pausing (for context on resume).
        message: Message to show the user (added to conversation).

    Returns:
        Updated state with HITL flags set and message added.

    Example:
        def approval_node(state: GhostwriterState) -> GhostwriterState:
            if state.get("generated_resume"):
                return request_human_input(
                    state,
                    reason=CheckpointReason.APPROVAL_NEEDED,
                    message="Please review the generated resume. Reply 'approve' to continue.",
                )
            return state
    """
    # Copy state to avoid mutating input
    new_state: BaseAgentState = dict(state)  # type: ignore[assignment]

    # Set HITL flags
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = reason.value

    # Add assistant message to conversation
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "assistant",
            "content": message,
        }
    )
    new_state["messages"] = messages

    return new_state


def resume_from_checkpoint(
    state: BaseAgentState,
    *,
    user_response: str,
) -> BaseAgentState:
    """Prepare state for resuming after HITL checkpoint.

    Call this with the loaded checkpoint state and user's response
    before re-invoking the graph.

    Args:
        state: Checkpoint state loaded from storage.
        user_response: User's response to the HITL prompt.

    Returns:
        Updated state ready for graph resumption.

    Example:
        # Load checkpoint
        state = await checkpointer.aget(thread_id)

        # Prepare for resume
        state = resume_from_checkpoint(state, user_response="approve")

        # Continue execution
        result = await graph.ainvoke(state, config)
    """
    # Copy state to avoid mutating input
    new_state: BaseAgentState = dict(state)  # type: ignore[assignment]

    # Clear HITL flags
    new_state["requires_human_input"] = False
    new_state["checkpoint_reason"] = None

    # Add user response to conversation
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "user",
            "content": user_response,
        }
    )
    new_state["messages"] = messages

    # Set current message for processing
    new_state["current_message"] = user_response

    return new_state
