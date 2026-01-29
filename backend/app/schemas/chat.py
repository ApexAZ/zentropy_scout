"""Chat API request/response schemas.

REQ-006 §2.5: SSE event types for real-time communication.

Event Types:
- chat_token: Streaming LLM output token-by-token
- chat_done: Message complete marker
- tool_start: Agent starting a tool call
- tool_result: Agent tool call completed
- data_changed: Data modification notification for UI refresh
- heartbeat: Keepalive for SSE connection
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# Request Schemas
# =============================================================================


class ChatMessageRequest(BaseModel):
    """Request body for POST /chat/messages.

    REQ-006 §5.2: Send message to chat agent.

    Attributes:
        content: The user's message text.
        context: Optional context data (e.g., job_id being discussed).
    """

    content: str = Field(..., description="User message content")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional context data for the agent",
    )

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, v: str) -> str:
        """Strip whitespace from content."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Validate content is not empty after stripping."""
        if not v:
            msg = "Content cannot be empty"
            raise ValueError(msg)
        return v


# =============================================================================
# SSE Event Schemas
# =============================================================================


class SSEEvent(BaseModel):
    """Base class for all SSE events.

    All events have a type field and can serialize to SSE format.
    """

    type: str

    def to_sse(self) -> str:
        """Serialize event to SSE wire format.

        Returns:
            String in format: "data: {json}\n\n"
        """
        return f"data: {self.model_dump_json()}\n\n"


class ChatTokenEvent(SSEEvent):
    """Streaming LLM token event.

    REQ-006 §2.5: Frontend appends text to chat message.

    Attributes:
        type: Always "chat_token".
        text: The token text to append.
    """

    type: Literal["chat_token"] = "chat_token"
    text: str = Field(..., description="Token text to append to message")


class ChatDoneEvent(SSEEvent):
    """Message complete event.

    REQ-006 §2.5: Frontend marks message as complete.

    Attributes:
        type: Always "chat_done".
        message_id: UUID of the completed message.
    """

    type: Literal["chat_done"] = "chat_done"
    message_id: str = Field(..., description="UUID of completed message")


class ToolStartEvent(SSEEvent):
    """Agent tool call starting event.

    REQ-006 §2.5: Frontend shows "working..." indicator.

    Attributes:
        type: Always "tool_start".
        tool: Name of the tool being called.
        args: Arguments passed to the tool.
    """

    type: Literal["tool_start"] = "tool_start"
    tool: str = Field(..., description="Tool name being called")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResultEvent(SSEEvent):
    """Agent tool call completed event.

    REQ-006 §2.5: Frontend shows result, clears indicator.

    Attributes:
        type: Always "tool_result".
        tool: Name of the tool that completed.
        success: Whether the tool call succeeded.
        result: Optional result data on success.
        error: Optional error message on failure.
    """

    type: Literal["tool_result"] = "tool_result"
    tool: str = Field(..., description="Tool name that completed")
    success: bool = Field(..., description="Whether tool succeeded")
    result: dict[str, Any] | None = Field(
        default=None, description="Result data on success"
    )
    error: str | None = Field(default=None, description="Error message on failure")


class DataChangedEvent(SSEEvent):
    """Data modification notification event.

    REQ-006 §2.5: Frontend refreshes the specified resource.

    Attributes:
        type: Always "data_changed".
        resource: Resource type that changed (e.g., "job-posting").
        id: UUID of the changed resource.
        action: What happened: created, updated, or deleted.
    """

    type: Literal["data_changed"] = "data_changed"
    resource: str = Field(..., description="Resource type (e.g., job-posting)")
    id: str = Field(..., description="UUID of changed resource")
    action: Literal["created", "updated", "deleted"] = Field(
        ..., description="Action performed"
    )


class HeartbeatEvent(SSEEvent):
    """Keepalive heartbeat event.

    Sent periodically to keep the SSE connection alive.

    Attributes:
        type: Always "heartbeat".
    """

    type: Literal["heartbeat"] = "heartbeat"
