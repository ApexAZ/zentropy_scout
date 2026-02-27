"""Chat API router.

REQ-006 §2.5, §5.2: Chat endpoints and SSE for agent interaction.

This module provides:
- POST /messages: Send a message to the chat agent
- GET /stream: SSE connection for real-time agent responses and data events

Event Types (REQ-006 §2.5):
- chat_token: Streaming LLM output token-by-token
- chat_done: Message complete marker
- tool_start: Agent starting a tool call
- tool_result: Agent tool call completed
- data_changed: Data modification notification for UI refresh
- heartbeat: Keepalive for SSE connection
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserId
from app.core.config import settings
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse
from app.schemas.chat import ChatMessageRequest, HeartbeatEvent

router = APIRouter()

# Defense-in-depth: Bound SSE connection lifetime to prevent resource exhaustion.
# Without these limits, abandoned clients hold server resources indefinitely.
_SSE_MAX_CONNECTION_SECONDS: float = 30 * 60  # 30 minutes
_SSE_HEARTBEAT_INTERVAL_SECONDS: float = 30


@router.post("/messages")
@limiter.limit(settings.rate_limit_llm)
async def send_chat_message(
    request: Request,  # noqa: ARG001
    body: ChatMessageRequest,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Send a message to the chat agent.

    REQ-006 §5.2: Send message to agent for processing.
    The message is queued for processing by the LangGraph agent.
    Responses will be streamed via the SSE /stream endpoint.
    Security: Rate limited to prevent LLM cost abuse.

    Args:
        request: The chat message request body.
        user_id: Current authenticated user (injected).

    Returns:
        DataResponse with message_id and processing status.
    """
    # Generate a unique message ID
    # WHY: This ID is used to correlate the request with SSE events
    message_id = uuid.uuid4()

    # Phase 2: LangGraph agent will process the message and stream responses
    # via the SSE /stream endpoint. For now, we return immediately.

    return DataResponse(
        data={
            "message_id": str(message_id),
            "status": "processing",
        }
    )


async def event_generator(
    max_duration: float = _SSE_MAX_CONNECTION_SECONDS,
    heartbeat_interval: float = _SSE_HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncIterator[str]:
    """Generate SSE events for the connected client.

    Yields heartbeat events periodically and terminates after max_duration
    seconds. The initial heartbeat is sent immediately to confirm connection.
    After max_duration, the generator exits cleanly via asyncio.timeout().

    Args:
        max_duration: Maximum connection lifetime in seconds (default 30 min).
            Must be positive.
        heartbeat_interval: Seconds between heartbeat events (default 30s).
            Must be positive.

    Yields:
        SSE-formatted event strings.

    Raises:
        ValueError: If max_duration or heartbeat_interval is not positive.
    """
    if max_duration <= 0:
        raise ValueError("max_duration must be positive")
    if heartbeat_interval <= 0:
        raise ValueError("heartbeat_interval must be positive")

    # Send initial heartbeat to confirm connection
    yield HeartbeatEvent().to_sse()

    # Phase 2: Will subscribe to agent events for this user and yield
    # chat_token, tool_start, tool_result, data_changed events.
    # For now, we send periodic heartbeats to keep connection alive.
    try:
        async with asyncio.timeout(max_duration):
            while True:
                await asyncio.sleep(heartbeat_interval)
                yield HeartbeatEvent().to_sse()
    except TimeoutError:
        # Max connection duration reached — terminate cleanly
        pass


@router.get("/stream")
async def chat_stream(
    _user_id: CurrentUserId,
) -> StreamingResponse:
    """Establish SSE connection for chat and data events.

    REQ-006 §2.5: Server-Sent Events for real-time agent communication.

    This endpoint provides a long-lived SSE connection that streams:
    - chat_token: LLM output tokens during agent responses
    - chat_done: Marks message completion
    - tool_start/tool_result: Agent tool execution feedback
    - data_changed: Notifications when data is modified
    - heartbeat: Periodic keepalive events

    Connection is bounded to _SSE_MAX_CONNECTION_SECONDS (30 min) to prevent
    resource exhaustion from abandoned clients.

    Args:
        user_id: Current authenticated user (injected).

    Returns:
        StreamingResponse with text/event-stream content type.
    """
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
