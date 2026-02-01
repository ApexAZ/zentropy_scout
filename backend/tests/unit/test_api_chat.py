"""Tests for Chat API endpoints.

REQ-006 §2.5: Real-Time Communication via SSE.
REQ-006 §5.2: Chat endpoints.

These tests verify:
- GET /api/v1/chat/stream (SSE connection)
- POST /api/v1/chat/messages (send message to agent)
- Event type schemas and formatting
"""

import json
import uuid

import pytest
from httpx import AsyncClient

from app.schemas.chat import (
    ChatDoneEvent,
    ChatMessageRequest,
    ChatTokenEvent,
    DataChangedEvent,
    HeartbeatEvent,
    ToolResultEvent,
    ToolStartEvent,
)

# =============================================================================
# Schema Tests - Event Type Validation
# =============================================================================


class TestSSEEventSchemas:
    """Tests for SSE event Pydantic models."""

    def test_chat_token_event_schema(self):
        """ChatTokenEvent has correct structure."""
        event = ChatTokenEvent(text="Hello")
        assert event.type == "chat_token"
        assert event.text == "Hello"
        # Should serialize to JSON correctly
        data = event.model_dump()
        assert data == {"type": "chat_token", "text": "Hello"}

    def test_chat_done_event_schema(self):
        """ChatDoneEvent has correct structure."""
        msg_id = uuid.uuid4()
        event = ChatDoneEvent(message_id=str(msg_id))
        assert event.type == "chat_done"
        assert event.message_id == str(msg_id)

    def test_tool_start_event_schema(self):
        """ToolStartEvent has correct structure."""
        event = ToolStartEvent(tool="favorite_job", args={"id": "123"})
        assert event.type == "tool_start"
        assert event.tool == "favorite_job"
        assert event.args == {"id": "123"}

    def test_tool_result_event_schema(self):
        """ToolResultEvent has correct structure."""
        event = ToolResultEvent(
            tool="favorite_job", success=True, result={"status": "ok"}
        )
        assert event.type == "tool_result"
        assert event.tool == "favorite_job"
        assert event.success is True
        assert event.result == {"status": "ok"}

    def test_tool_result_event_with_error(self):
        """ToolResultEvent can include error message."""
        event = ToolResultEvent(
            tool="favorite_job", success=False, error="Job not found"
        )
        assert event.success is False
        assert event.error == "Job not found"
        assert event.result is None

    def test_data_changed_event_schema(self):
        """DataChangedEvent has correct structure."""
        event = DataChangedEvent(
            resource="job-posting",
            id="29583",
            action="updated",
        )
        assert event.type == "data_changed"
        assert event.resource == "job-posting"
        assert event.id == "29583"
        assert event.action == "updated"

    def test_data_changed_event_actions(self):
        """DataChangedEvent supports all action types."""
        for action in ["created", "updated", "deleted"]:
            event = DataChangedEvent(resource="application", id="1", action=action)
            assert event.action == action

    def test_sse_event_serialization(self):
        """SSE events serialize to proper format."""
        event = ChatTokenEvent(text="Hello")
        sse_line = event.to_sse()
        # SSE format: "data: {...}\n\n"
        assert sse_line.startswith("data: ")
        assert sse_line.endswith("\n\n")
        # Parse the JSON portion
        json_str = sse_line[6:-2]  # Strip "data: " and "\n\n"
        parsed = json.loads(json_str)
        assert parsed["type"] == "chat_token"
        assert parsed["text"] == "Hello"


# =============================================================================
# SSE Stream Tests - GET /api/v1/chat/stream
# =============================================================================


class TestChatStreamEndpoint:
    """Tests for GET /api/v1/chat/stream.

    NOTE: Full SSE streaming behavior is tested via integration tests.
    Unit tests verify authentication and basic endpoint setup.
    """

    @pytest.mark.asyncio
    async def test_stream_requires_auth(self, unauthenticated_client: AsyncClient):
        """Stream endpoint returns 401 without authentication."""
        response = await unauthenticated_client.get("/api/v1/chat/stream")
        assert response.status_code == 401


class TestHeartbeatEvent:
    """Tests for HeartbeatEvent SSE formatting."""

    def test_heartbeat_event_type(self):
        """HeartbeatEvent has correct type."""
        event = HeartbeatEvent()
        assert event.type == "heartbeat"

    def test_heartbeat_event_to_sse(self):
        """HeartbeatEvent serializes to SSE format."""
        event = HeartbeatEvent()
        sse = event.to_sse()
        assert sse == 'data: {"type":"heartbeat"}\n\n'


# =============================================================================
# Send Message Tests - POST /api/v1/chat/messages
# =============================================================================


class TestSendChatMessage:
    """Tests for POST /api/v1/chat/messages."""

    @pytest.mark.asyncio
    async def test_send_message_requires_auth(
        self, unauthenticated_client: AsyncClient
    ):
        """Send message endpoint returns 401 without authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/chat/messages",
            json={"content": "Hello"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_send_message_success(self, client: AsyncClient):
        """Send message returns message ID and status."""
        response = await client.post(
            "/api/v1/chat/messages",
            json={"content": "Hello, can you help me?"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "data" in result
        assert "message_id" in result["data"]
        assert result["data"]["message_id"] is not None
        assert result["data"]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_send_message_returns_uuid(self, client: AsyncClient):
        """Send message returns a valid UUID for message_id."""
        response = await client.post(
            "/api/v1/chat/messages",
            json={"content": "Test message"},
        )

        result = response.json()
        message_id = result["data"]["message_id"]
        # Should be a valid UUID string
        uuid.UUID(message_id)  # Raises if invalid

    @pytest.mark.asyncio
    async def test_send_message_requires_content(self, client: AsyncClient):
        """Send message requires content field."""
        response = await client.post(
            "/api/v1/chat/messages",
            json={},  # Missing content
        )

        # Pydantic validation error returns 400
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_content_not_empty(self, client: AsyncClient):
        """Send message content cannot be empty."""
        response = await client.post(
            "/api/v1/chat/messages",
            json={"content": ""},
        )

        # Empty content should return 400
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_content_whitespace_only(self, client: AsyncClient):
        """Send message content cannot be whitespace only."""
        response = await client.post(
            "/api/v1/chat/messages",
            json={"content": "   "},
        )

        # Whitespace-only content should return 400
        assert response.status_code == 400


# =============================================================================
# Request Schema Tests
# =============================================================================


class TestChatMessageRequest:
    """Tests for ChatMessageRequest Pydantic schema validation."""

    def test_valid_message(self):
        """Valid message content passes validation."""
        request = ChatMessageRequest(content="Hello, can you help me?")
        assert request.content == "Hello, can you help me?"

    def test_message_with_context(self):
        """Message can include optional context field."""
        request = ChatMessageRequest(
            content="Help me with this job",
            context={"job_id": "123"},
        )
        assert request.content == "Help me with this job"
        assert request.context == {"job_id": "123"}

    def test_content_stripped(self):
        """Content is stripped of leading/trailing whitespace."""
        request = ChatMessageRequest(content="  Hello  ")
        assert request.content == "Hello"

    def test_empty_content_invalid(self):
        """Empty content raises validation error."""
        with pytest.raises(ValueError):
            ChatMessageRequest(content="")

    def test_whitespace_only_content_invalid(self):
        """Whitespace-only content raises validation error."""
        with pytest.raises(ValueError):
            ChatMessageRequest(content="   ")

    def test_content_exceeds_max_length_invalid(self):
        """Content exceeding 50,000 characters raises validation error."""
        with pytest.raises(ValueError):
            ChatMessageRequest(content="x" * 50001)

    def test_content_at_max_length_valid(self):
        """Content at exactly 50,000 characters passes validation."""
        request = ChatMessageRequest(content="x" * 50000)
        assert len(request.content) == 50000
