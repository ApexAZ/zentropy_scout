"""Tests for Claude LLM adapter (REQ-009 §4.2).

Tests the ClaudeAdapter implementation with mocked Anthropic client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.config import ProviderConfig
from app.providers.llm.base import (
    LLMMessage,
    TaskType,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from app.providers.llm.claude_adapter import ClaudeAdapter

# Default model routing for tests
DEFAULT_CLAUDE_ROUTING = {
    "chat_response": "claude-3-5-sonnet-20241022",
    "onboarding": "claude-3-5-sonnet-20241022",
    "extraction": "claude-3-5-haiku-20241022",
    "skill_extraction": "claude-3-5-haiku-20241022",
    "ghost_detection": "claude-3-5-haiku-20241022",
    "score_rationale": "claude-3-5-sonnet-20241022",
    "cover_letter": "claude-3-5-sonnet-20241022",
    "resume_tailoring": "claude-3-5-sonnet-20241022",
    "story_selection": "claude-3-5-sonnet-20241022",
}


@pytest.fixture
def config():
    """Create a test provider config."""
    return ProviderConfig(
        llm_provider="claude",
        anthropic_api_key="test-api-key",
        claude_model_routing=DEFAULT_CLAUDE_ROUTING,
        default_max_tokens=4096,
        default_temperature=0.7,
    )


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(type="text", text="Hello, I'm Claude!")]
    response.usage = MagicMock(input_tokens=10, output_tokens=20)
    response.stop_reason = "end_turn"
    return response


@pytest.fixture
def mock_anthropic_tool_response():
    """Create a mock Anthropic API response with tool use."""
    response = MagicMock()

    # Tool use block
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_123"
    tool_block.name = "favorite_job"
    tool_block.input = {"job_id": "job-uuid-456"}

    response.content = [tool_block]
    response.usage = MagicMock(input_tokens=15, output_tokens=25)
    response.stop_reason = "tool_use"
    return response


class TestClaudeAdapterInit:
    """Test ClaudeAdapter initialization."""

    def test_init_creates_anthropic_client(self, config):
        """ClaudeAdapter should create an AsyncAnthropic client."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client:
            adapter = ClaudeAdapter(config)
            mock_client.assert_called_once_with(api_key="test-api-key")
            assert adapter.client is not None

    def test_init_stores_config(self, config):
        """ClaudeAdapter should store the config."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            assert adapter.config is config

    def test_init_stores_model_routing(self, config):
        """ClaudeAdapter should store model routing from config."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            assert adapter.model_routing == DEFAULT_CLAUDE_ROUTING


class TestClaudeAdapterGetModelForTask:
    """Test ClaudeAdapter.get_model_for_task()."""

    def test_returns_correct_model_for_extraction(self, config):
        """Should return Haiku for extraction tasks."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            assert model == "claude-3-5-haiku-20241022"

    def test_returns_correct_model_for_chat(self, config):
        """Should return Sonnet for chat tasks."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            assert model == "claude-3-5-sonnet-20241022"

    def test_uses_default_model_when_task_not_in_routing(self, config):
        """Should use default model when task not in routing table."""
        config.claude_model_routing = {}  # Empty routing
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            # Should fall back to default Sonnet
            assert "sonnet" in model.lower() or "claude" in model.lower()


class TestClaudeAdapterComplete:
    """Test ClaudeAdapter.complete() method."""

    @pytest.mark.asyncio
    async def test_complete_basic_message(self, config, mock_anthropic_response):
        """Should make API call and return LLMResponse."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.content == "Hello, I'm Claude!"
            assert response.input_tokens == 10
            assert response.output_tokens == 20
            assert response.finish_reason == "end_turn"
            assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_complete_extracts_system_message(self, config, mock_anthropic_response):
        """Should extract system message and pass separately to API."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="system", content="You are a helpful assistant."),
                LLMMessage(role="user", content="Hello!"),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify system was passed separately
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["system"] == "You are a helpful assistant."
            # User message should be in messages array
            assert len(call_kwargs["messages"]) == 1
            assert call_kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_with_tool_response(self, config, mock_anthropic_tool_response):
        """Should parse tool calls from response."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_tool_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Star this job")]
            tools = [
                ToolDefinition(
                    name="favorite_job",
                    description="Mark a job as favorite",
                    parameters=[
                        ToolParameter(
                            name="job_id",
                            param_type="string",
                            description="Job ID",
                        ),
                    ],
                ),
            ]

            response = await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, tools=tools
            )

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].id == "toolu_123"
            assert response.tool_calls[0].name == "favorite_job"
            assert response.tool_calls[0].arguments == {"job_id": "job-uuid-456"}

    @pytest.mark.asyncio
    async def test_complete_converts_tools_to_anthropic_format(self, config, mock_anthropic_response):
        """Should convert ToolDefinition to Anthropic tool format."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]
            tools = [
                ToolDefinition(
                    name="test_tool",
                    description="A test tool",
                    parameters=[
                        ToolParameter(
                            name="param1",
                            param_type="string",
                            description="First param",
                        ),
                    ],
                ),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE, tools=tools)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "tools" in call_kwargs
            assert call_kwargs["tools"][0]["name"] == "test_tool"
            assert call_kwargs["tools"][0]["description"] == "A test tool"
            assert "input_schema" in call_kwargs["tools"][0]

    @pytest.mark.asyncio
    async def test_complete_handles_tool_result_message(self, config, mock_anthropic_response):
        """Should convert tool result messages to Anthropic format."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="user", content="Star this job"),
                LLMMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="toolu_123",
                            name="favorite_job",
                            arguments={"job_id": "uuid"},
                        ),
                    ],
                ),
                LLMMessage(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id="toolu_123",
                        content='{"success": true}',
                    ),
                ),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            api_messages = call_kwargs["messages"]

            # Tool result should be converted to user message with tool_result block
            tool_result_msg = api_messages[-1]
            assert tool_result_msg["role"] == "user"
            assert tool_result_msg["content"][0]["type"] == "tool_result"
            assert tool_result_msg["content"][0]["tool_use_id"] == "toolu_123"

    @pytest.mark.asyncio
    async def test_complete_json_mode_modifies_system_prompt(self, config, mock_anthropic_response):
        """JSON mode should append instruction to system prompt."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="system", content="Extract skills."),
                LLMMessage(role="user", content="Python, JavaScript"),
            ]

            await adapter.complete(
                messages, TaskType.EXTRACTION, json_mode=True
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "JSON" in call_kwargs["system"]
            assert "Extract skills." in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_complete_json_mode_without_system_message(self, config, mock_anthropic_response):
        """JSON mode should work even without system message."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Extract: Python")]

            await adapter.complete(
                messages, TaskType.EXTRACTION, json_mode=True
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "JSON" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_complete_uses_config_defaults(self, config, mock_anthropic_response):
        """Should use config defaults when not overridden."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 4096
            assert call_kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_complete_allows_override_max_tokens(self, config, mock_anthropic_response):
        """Should allow overriding max_tokens."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, max_tokens=1000
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_complete_allows_override_temperature(self, config, mock_anthropic_response):
        """Should allow overriding temperature."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, temperature=0.0
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_complete_passes_stop_sequences(self, config, mock_anthropic_response):
        """Should pass stop_sequences to API."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, stop_sequences=["END", "STOP"]
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["stop_sequences"] == ["END", "STOP"]

    @pytest.mark.asyncio
    async def test_complete_records_latency(self, config, mock_anthropic_response):
        """Should record response latency."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            # Simulate some latency
            async def slow_create(**_kwargs):
                await asyncio.sleep(0.01)  # 10ms
                return mock_anthropic_response
            mock_client.messages.create = slow_create
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            import asyncio
            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.latency_ms >= 10  # At least 10ms

    @pytest.mark.asyncio
    async def test_complete_includes_model_in_response(self, config, mock_anthropic_response):
        """Response should include the model used."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.model == "claude-3-5-sonnet-20241022"


class TestClaudeAdapterStream:
    """Test ClaudeAdapter.stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self, config):
        """Should yield text chunks from stream."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()

            # Create async context manager for stream
            class MockStreamContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                @property
                def text_stream(self):
                    async def gen():
                        for chunk in ["Hello", ", ", "world", "!"]:
                            yield chunk
                    return gen()

            mock_client.messages.stream = MagicMock(return_value=MockStreamContext())
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Say hello")]

            chunks = []
            async for chunk in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                chunks.append(chunk)

            assert chunks == ["Hello", ", ", "world", "!"]

    @pytest.mark.asyncio
    async def test_stream_uses_correct_model(self, config):
        """Should use model from routing table."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()

            class MockStreamContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                @property
                def text_stream(self):
                    async def gen():
                        yield "text"
                    return gen()

            mock_client.messages.stream = MagicMock(return_value=MockStreamContext())
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            async for _ in adapter.stream(messages, TaskType.EXTRACTION):
                pass

            call_kwargs = mock_client.messages.stream.call_args.kwargs
            assert call_kwargs["model"] == "claude-3-5-haiku-20241022"

    @pytest.mark.asyncio
    async def test_stream_extracts_system_message(self, config):
        """Should extract system message like complete()."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()

            class MockStreamContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                @property
                def text_stream(self):
                    async def gen():
                        yield "text"
                    return gen()

            mock_client.messages.stream = MagicMock(return_value=MockStreamContext())
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="system", content="Be helpful."),
                LLMMessage(role="user", content="Hello"),
            ]

            async for _ in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                pass

            call_kwargs = mock_client.messages.stream.call_args.kwargs
            assert call_kwargs["system"] == "Be helpful."
            assert len(call_kwargs["messages"]) == 1


class TestClaudeAdapterMessageConversion:
    """Test message conversion to Anthropic format."""

    @pytest.mark.asyncio
    async def test_converts_assistant_message_with_tool_calls(self, config, mock_anthropic_response):
        """Should convert assistant messages with tool calls to content blocks."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="user", content="Star job"),
                LLMMessage(
                    role="assistant",
                    content="I'll star that job for you.",
                    tool_calls=[
                        ToolCall(
                            id="toolu_123",
                            name="favorite_job",
                            arguments={"job_id": "uuid"},
                        ),
                    ],
                ),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assistant_msg = call_kwargs["messages"][1]

            # Should have both text and tool_use blocks
            assert assistant_msg["role"] == "assistant"
            assert isinstance(assistant_msg["content"], list)

            text_block = next(b for b in assistant_msg["content"] if b["type"] == "text")
            tool_block = next(b for b in assistant_msg["content"] if b["type"] == "tool_use")

            assert text_block["text"] == "I'll star that job for you."
            assert tool_block["id"] == "toolu_123"
            assert tool_block["name"] == "favorite_job"
            assert tool_block["input"] == {"job_id": "uuid"}

    @pytest.mark.asyncio
    async def test_handles_tool_result_error(self, config, mock_anthropic_response):
        """Should pass is_error flag for tool results."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="user", content="Star job"),
                LLMMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(id="toolu_123", name="favorite_job", arguments={}),
                    ],
                ),
                LLMMessage(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id="toolu_123",
                        content="Job not found",
                        is_error=True,
                    ),
                ),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            tool_result_msg = call_kwargs["messages"][-1]

            assert tool_result_msg["content"][0]["is_error"] is True
