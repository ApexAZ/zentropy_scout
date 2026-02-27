"""LangGraph checkpointing utilities for the Chat Agent.

REQ-007 §3.3: Checkpointing

This module provides utilities for:
- Creating checkpointers for state persistence
- Configuring graph execution

Checkpoint Storage:
    MVP uses MemorySaver (no persistence) for single-user local deployment.
    PostgreSQL checkpointing will be enabled when multi-user support is added
    (see feature backlog).
"""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


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
    # FUTURE: PostgreSQL checkpointing for hosted/multi-user mode is tracked
    # in the implementation plan (Phase 2.8, REQ-007 §11). When implemented,
    # use TTL of 24h for incomplete flows, 7 days for conversation history.

    return MemorySaver()


def create_graph_config(
    thread_id: str,
    user_id: str,
    *,
    checkpoint_ns: str = "",
) -> dict[str, Any]:  # Any: LangGraph config structure is library-defined, not typed
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
