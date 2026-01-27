"""Tests for OpenAI LLM adapter (REQ-009 §4.2).

Tests the OpenAIAdapter implementation with mocked OpenAI client.
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
from app.providers.llm.openai_adapter import OpenAIAdapter

# Default model routing for tests
DEFAULT_OPENAI_ROUTING = {
    "chat_response": "gpt-4o",
    "onboarding": "gpt-4o",
    "extraction": "gpt-4o-mini",
    "skill_extraction": "gpt-4o-mini",
    "ghost_detection": "gpt-4o-mini",
    "score_rationale": "gpt-4o",
    "cover_letter": "gpt-4o",
    "resume_tailoring": "gpt-4o",
    "story_selection": "gpt-4o",
}


@pytest.fixture
def config():
    """Create a test provider config."""
    return ProviderConfig(
        llm_provider="openai",
        openai_api_key="test-api-key",
        openai_model_routing=DEFAULT_OPENAI_ROUTING,
        default_max_tokens=4096,
        default_temperature=0.7,
    )


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    response = MagicMock()
    choice = MagicMock()
    choice.message = MagicMock()
    choice.message.content = "Hello from GPT!"
    choice.message.tool_calls = None
    choice.finish_reason = "stop"
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    return response


@pytest.fixture
def mock_openai_tool_response():
    """Create a mock OpenAI API response with tool calls."""
    response = MagicMock()
    choice = MagicMock()
    choice.message = MagicMock()
    choice.message.content = None

    # Tool call
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function = MagicMock()
    tool_call.function.name = "favorite_job"
    tool_call.function.arguments = '{"job_id": "job-uuid-456"}'

    choice.message.tool_calls = [tool_call]
    choice.finish_reason = "tool_calls"
    response.choices = [choice]
    response.usage = MagicMock(prompt_tokens=15, completion_tokens=25)
    return response


class TestOpenAIAdapterInit:
    """Test OpenAIAdapter initialization."""

    def test_init_creates_openai_client(self, config):
        """OpenAIAdapter should create an AsyncOpenAI client."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client:
            adapter = OpenAIAdapter(config)
            mock_client.assert_called_once_with(api_key="test-api-key")
            assert adapter.client is not None

    def test_init_stores_config(self, config):
        """OpenAIAdapter should store the config."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI"):
            adapter = OpenAIAdapter(config)
            assert adapter.config is config

    def test_init_stores_model_routing(self, config):
        """OpenAIAdapter should store model routing from config."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI"):
            adapter = OpenAIAdapter(config)
            assert adapter.model_routing == DEFAULT_OPENAI_ROUTING


class TestOpenAIAdapterGetModelForTask:
    """Test OpenAIAdapter.get_model_for_task()."""

    def test_returns_correct_model_for_extraction(self, config):
        """Should return gpt-4o-mini for extraction tasks."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI"):
            adapter = OpenAIAdapter(config)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            assert model == "gpt-4o-mini"

    def test_returns_correct_model_for_chat(self, config):
        """Should return gpt-4o for chat tasks."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI"):
            adapter = OpenAIAdapter(config)
            model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            assert model == "gpt-4o"

    def test_uses_default_model_when_task_not_in_routing(self, config):
        """Should use default model when task not in routing table."""
        config.openai_model_routing = {}  # Empty routing
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI"):
            adapter = OpenAIAdapter(config)
            model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            # Should fall back to default gpt-4o
            assert "gpt" in model.lower()


class TestOpenAIAdapterComplete:
    """Test OpenAIAdapter.complete() method."""

    @pytest.mark.asyncio
    async def test_complete_basic_message(self, config, mock_openai_response):
        """Should make API call and return LLMResponse."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.content == "Hello from GPT!"
            assert response.input_tokens == 10
            assert response.output_tokens == 20
            assert response.finish_reason == "stop"
            assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_complete_keeps_system_message_in_array(self, config, mock_openai_response):
        """OpenAI keeps system message in messages array (unlike Claude)."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [
                LLMMessage(role="system", content="You are a helpful assistant."),
                LLMMessage(role="user", content="Hello!"),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            # System message should be in messages array
            assert len(call_kwargs["messages"]) == 2
            assert call_kwargs["messages"][0]["role"] == "system"
            assert call_kwargs["messages"][0]["content"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_complete_with_tool_response(self, config, mock_openai_tool_response):
        """Should parse tool calls from response."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_tool_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
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
            assert response.tool_calls[0].id == "call_123"
            assert response.tool_calls[0].name == "favorite_job"
            assert response.tool_calls[0].arguments == {"job_id": "job-uuid-456"}

    @pytest.mark.asyncio
    async def test_complete_converts_tools_to_openai_format(self, config, mock_openai_response):
        """Should convert ToolDefinition to OpenAI function format."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
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

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert "tools" in call_kwargs
            assert call_kwargs["tools"][0]["type"] == "function"
            assert call_kwargs["tools"][0]["function"]["name"] == "test_tool"
            assert call_kwargs["tools"][0]["function"]["description"] == "A test tool"
            assert "parameters" in call_kwargs["tools"][0]["function"]

    @pytest.mark.asyncio
    async def test_complete_handles_tool_result_message(self, config, mock_openai_response):
        """Should convert tool result messages to OpenAI format."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [
                LLMMessage(role="user", content="Star this job"),
                LLMMessage(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call_123",
                            name="favorite_job",
                            arguments={"job_id": "uuid"},
                        ),
                    ],
                ),
                LLMMessage(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id="call_123",
                        content='{"success": true}',
                    ),
                ),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            api_messages = call_kwargs["messages"]

            # Tool result should have tool role with tool_call_id
            tool_result_msg = api_messages[-1]
            assert tool_result_msg["role"] == "tool"
            assert tool_result_msg["tool_call_id"] == "call_123"
            assert tool_result_msg["content"] == '{"success": true}'

    @pytest.mark.asyncio
    async def test_complete_json_mode_uses_response_format(self, config, mock_openai_response):
        """JSON mode should use native response_format."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [
                LLMMessage(role="system", content="Extract skills."),
                LLMMessage(role="user", content="Python, JavaScript"),
            ]

            await adapter.complete(
                messages, TaskType.EXTRACTION, json_mode=True
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_complete_no_response_format_when_json_mode_false(self, config, mock_openai_response):
        """Should not set response_format when json_mode is False."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE, json_mode=False)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs.get("response_format") is None

    @pytest.mark.asyncio
    async def test_complete_uses_config_defaults(self, config, mock_openai_response):
        """Should use config defaults when not overridden."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 4096
            assert call_kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_complete_allows_override_max_tokens(self, config, mock_openai_response):
        """Should allow overriding max_tokens."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, max_tokens=1000
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_complete_passes_stop_sequences(self, config, mock_openai_response):
        """Should pass stop_sequences to API as 'stop' parameter."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, stop_sequences=["END", "STOP"]
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["stop"] == ["END", "STOP"]

    @pytest.mark.asyncio
    async def test_complete_includes_model_in_response(self, config, mock_openai_response):
        """Response should include the model used."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.model == "gpt-4o"


class TestOpenAIAdapterStream:
    """Test OpenAIAdapter.stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self, config):
        """Should yield text chunks from stream."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()

            # Create async generator for stream
            async def mock_stream():
                for text in ["Hello", ", ", "world", "!"]:
                    chunk = MagicMock()
                    chunk.choices = [MagicMock()]
                    chunk.choices[0].delta = MagicMock()
                    chunk.choices[0].delta.content = text
                    yield chunk

            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Say hello")]

            chunks = []
            async for chunk in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                chunks.append(chunk)

            assert chunks == ["Hello", ", ", "world", "!"]

    @pytest.mark.asyncio
    async def test_stream_uses_correct_model(self, config):
        """Should use model from routing table."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()

            async def mock_stream():
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta = MagicMock()
                chunk.choices[0].delta.content = "text"
                yield chunk

            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            async for _ in adapter.stream(messages, TaskType.EXTRACTION):
                pass

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_stream_skips_none_content(self, config):
        """Should skip chunks with None content."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()

            async def mock_stream():
                for text in ["Hello", None, "world"]:
                    chunk = MagicMock()
                    chunk.choices = [MagicMock()]
                    chunk.choices[0].delta = MagicMock()
                    chunk.choices[0].delta.content = text
                    yield chunk

            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            chunks = []
            async for chunk in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                chunks.append(chunk)

            assert chunks == ["Hello", "world"]


class TestOpenAIAdapterMessageConversion:
    """Test message conversion to OpenAI format."""

    @pytest.mark.asyncio
    async def test_converts_assistant_message_with_tool_calls(self, config, mock_openai_response):
        """Should convert assistant messages with tool calls to OpenAI format."""
        with patch("app.providers.llm.openai_adapter.AsyncOpenAI") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_cls.return_value = mock_client

            adapter = OpenAIAdapter(config)
            messages = [
                LLMMessage(role="user", content="Star job"),
                LLMMessage(
                    role="assistant",
                    content="I'll star that job for you.",
                    tool_calls=[
                        ToolCall(
                            id="call_123",
                            name="favorite_job",
                            arguments={"job_id": "uuid"},
                        ),
                    ],
                ),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assistant_msg = call_kwargs["messages"][1]

            assert assistant_msg["role"] == "assistant"
            assert assistant_msg["content"] == "I'll star that job for you."
            assert len(assistant_msg["tool_calls"]) == 1
            assert assistant_msg["tool_calls"][0]["id"] == "call_123"
            assert assistant_msg["tool_calls"][0]["type"] == "function"
            assert assistant_msg["tool_calls"][0]["function"]["name"] == "favorite_job"
            # Arguments should be JSON-encoded string
            assert assistant_msg["tool_calls"][0]["function"]["arguments"] == '{"job_id": "uuid"}'
