"""Chat API router.

REQ-006 §5.2: Chat endpoints for agent interaction.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse

router = APIRouter()


@router.post("/messages")
async def send_chat_message(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Send a message to the chat agent.

    REQ-006 §5.2: Send message to agent for processing.
    """
    return DataResponse(data={"message_id": None, "status": "processing"})


@router.get("/stream")
async def chat_stream(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> StreamingResponse:
    """Establish SSE connection for chat and data events.

    REQ-006 §2.5: Server-Sent Events for real-time agent communication.
    """

    async def event_generator():
        # Placeholder - will stream agent responses
        yield "data: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
