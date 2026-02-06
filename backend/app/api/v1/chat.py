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

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserId
from app.core.config import settings
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse
from app.schemas.chat import ChatMessageRequest, HeartbeatEvent

router = APIRouter()


@router.post("/messages")
@limiter.limit(settings.rate_limit_llm)
async def send_chat_message(
    request: Request,  # noqa: ARG001 - Required by rate limiter
    body: ChatMessageRequest,  # noqa: ARG001 - will be used in Phase 2
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

    Args:
        user_id: Current authenticated user (injected).

    Returns:
        StreamingResponse with text/event-stream content type.
    """

    async def event_generator():
        """Generate SSE events for the connected client.

        WHY async generator: Allows yielding events as they occur
        without blocking other requests.
        """
        # Send initial heartbeat to confirm connection
        yield HeartbeatEvent().to_sse()

        # Phase 2: Will subscribe to agent events for this user and yield
        # chat_token, tool_start, tool_result, data_changed events.
        # For now, we send periodic heartbeats to keep connection alive.
        while True:
            # Wait for next heartbeat interval
            # WHY 30s: Balances keepalive with reduced overhead
            await asyncio.sleep(30)
            yield HeartbeatEvent().to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
