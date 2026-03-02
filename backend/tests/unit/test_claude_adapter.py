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


@pytest.fixture
def config():
    """Create a test provider config using built-in defaults."""
    return ProviderConfig(
        llm_provider="claude",
        anthropic_api_key="test-api-key",
        # No custom routing - use built-in defaults
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

    def test_init_routes_extraction_to_cheaper_model_by_default(self):
        """Without custom routing, extraction tasks should use a cheaper model."""
        config_no_routing = ProviderConfig(
            llm_provider="claude",
            anthropic_api_key="test-api-key",
            claude_model_routing=None,
            default_max_tokens=4096,
            default_temperature=0.7,
        )
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config_no_routing)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            # Behavior: extraction uses Haiku (cheaper model)
            assert "haiku" in model.lower()

    def test_init_config_routing_overrides_defaults(self):
        """Custom config routing should override default model selection."""
        custom_routing = {"extraction": "my-custom-model"}
        config_with_override = ProviderConfig(
            llm_provider="claude",
            anthropic_api_key="test-api-key",
            claude_model_routing=custom_routing,
            default_max_tokens=4096,
            default_temperature=0.7,
        )
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config_with_override)
            # Behavior: custom routing takes effect
            assert adapter.get_model_for_task(TaskType.EXTRACTION) == "my-custom-model"
            # Non-overridden tasks still use sensible defaults
            chat_model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            assert "sonnet" in chat_model.lower()


class TestClaudeAdapterGetModelForTask:
    """Test ClaudeAdapter.get_model_for_task() behavior."""

    def test_extraction_tasks_use_cost_effective_model(self, config):
        """Extraction tasks should route to cheaper/faster model (Haiku)."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            # Behavior: extraction uses Haiku for cost optimization
            assert "haiku" in model.lower()

    def test_chat_tasks_use_quality_model(self, config):
        """Chat/conversation tasks should route to higher quality model (Sonnet)."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            # Behavior: chat uses Sonnet for better reasoning
            assert "sonnet" in model.lower()

    def test_all_task_types_return_valid_model(self, config):
        """Every TaskType should return a valid Claude model identifier."""
        with patch("app.providers.llm.claude_adapter.AsyncAnthropic"):
            adapter = ClaudeAdapter(config)
            for task_type in TaskType:
                model = adapter.get_model_for_task(task_type)
                # Behavior: all tasks return a model (no None, no empty string)
                assert model is not None
                assert len(model) > 0
                assert "claude" in model.lower()


class TestClaudeAdapterComplete:
    """Test ClaudeAdapter.complete() method."""

    @pytest.mark.asyncio
    async def test_complete_basic_message(self, config, mock_anthropic_response):
        """Should make API call and return LLMResponse."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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
    async def test_complete_extracts_system_message(
        self, config, mock_anthropic_response
    ):
        """Should extract system message and pass separately to API."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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
    async def test_complete_with_tool_response(
        self, config, mock_anthropic_tool_response
    ):
        """Should parse tool calls from response."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_tool_response
            )
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
    async def test_complete_converts_tools_to_anthropic_format(
        self, config, mock_anthropic_response
    ):
        """Should convert ToolDefinition to Anthropic tool format."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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
    async def test_complete_handles_tool_result_message(
        self, config, mock_anthropic_response
    ):
        """Should convert tool result messages to Anthropic format."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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
    async def test_complete_json_mode_modifies_system_prompt(
        self, config, mock_anthropic_response
    ):
        """JSON mode should append instruction to system prompt."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [
                LLMMessage(role="system", content="Extract skills."),
                LLMMessage(role="user", content="Python, JavaScript"),
            ]

            await adapter.complete(messages, TaskType.EXTRACTION, json_mode=True)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "JSON" in call_kwargs["system"]
            assert "Extract skills." in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_complete_json_mode_without_system_message(
        self, config, mock_anthropic_response
    ):
        """JSON mode should work even without system message."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Extract: Python")]

            await adapter.complete(messages, TaskType.EXTRACTION, json_mode=True)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "JSON" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_complete_uses_config_defaults(self, config, mock_anthropic_response):
        """Should use config defaults when not overridden."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 4096
            assert call_kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_complete_allows_override_max_tokens(
        self, config, mock_anthropic_response
    ):
        """Should allow overriding max_tokens."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE, max_tokens=1000)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_complete_allows_override_temperature(
        self, config, mock_anthropic_response
    ):
        """Should allow overriding temperature."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE, temperature=0.0)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_complete_passes_stop_sequences(
        self, config, mock_anthropic_response
    ):
        """Should pass stop_sequences to API."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
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
    async def test_complete_includes_model_in_response(
        self, config, mock_anthropic_response
    ):
        """Response should include the model used."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Behavior: response includes the model that was used
            assert response.model is not None
            assert "sonnet" in response.model.lower()


class TestClaudeAdapterStream:
    """Test ClaudeAdapter.stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self, config):
        """Should yield text chunks from stream."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
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
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
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
            # Behavior: extraction tasks use cheaper model
            assert "haiku" in call_kwargs["model"].lower()

    @pytest.mark.asyncio
    async def test_stream_extracts_system_message(self, config):
        """Should extract system message like complete()."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
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
    async def test_converts_assistant_message_with_tool_calls(
        self, config, mock_anthropic_response
    ):
        """Should convert assistant messages with tool calls to content blocks."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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

            text_block = next(
                b for b in assistant_msg["content"] if b["type"] == "text"
            )
            tool_block = next(
                b for b in assistant_msg["content"] if b["type"] == "tool_use"
            )

            assert text_block["text"] == "I'll star that job for you."
            assert tool_block["id"] == "toolu_123"
            assert tool_block["name"] == "favorite_job"
            assert tool_block["input"] == {"job_id": "uuid"}

    @pytest.mark.asyncio
    async def test_handles_tool_result_error(self, config, mock_anthropic_response):
        """Should pass is_error flag for tool results."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
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


class TestClaudeAdapterErrorMapping:
    """Test error mapping from Anthropic SDK to unified errors (REQ-009 §7.3)."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_mapped(self, config):
        """Should map anthropic.RateLimitError to RateLimitError."""
        import anthropic

        from app.providers.errors import RateLimitError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_rate_limit_error_includes_retry_after(self, config):
        """Should include retry_after_seconds from Anthropic error."""
        import anthropic

        from app.providers.errors import RateLimitError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock(status_code=429)
            mock_response.headers = {"retry-after": "30"}
            mock_error = anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body={"error": {"message": "Rate limit exceeded"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(RateLimitError) as exc_info:
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Should extract retry_after from headers if available
            assert exc_info.value.retry_after_seconds is not None

    @pytest.mark.asyncio
    async def test_authentication_error_mapped(self, config):
        """Should map anthropic.AuthenticationError to AuthenticationError."""
        import anthropic

        from app.providers.errors import AuthenticationError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401),
                body={"error": {"message": "Invalid API key"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_context_length_error_mapped(self, config):
        """Should map BadRequestError with 'context_length' to ContextLengthError."""
        import anthropic

        from app.providers.errors import ContextLengthError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.BadRequestError(
                message="Request exceeds context_length limit",
                response=MagicMock(status_code=400),
                body={"error": {"message": "Request exceeds context_length limit"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ContextLengthError, match="context_length"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_content_filter_error_mapped(self, config):
        """Should map BadRequestError with 'content_policy' to ContentFilterError."""
        import anthropic

        from app.providers.errors import ContentFilterError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.BadRequestError(
                message="Blocked due to content_policy violation",
                response=MagicMock(status_code=400),
                body={"error": {"message": "Blocked due to content_policy violation"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ContentFilterError, match="content_policy"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_generic_bad_request_mapped_to_provider_error(self, config):
        """Should map generic BadRequestError to ProviderError."""
        import anthropic

        from app.providers.errors import ProviderError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.BadRequestError(
                message="Invalid request parameters",
                response=MagicMock(status_code=400),
                body={"error": {"message": "Invalid request parameters"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ProviderError, match="Invalid request parameters"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_api_error_mapped_to_transient_error(self, config):
        """Should map anthropic.APIError to TransientError (safe to retry)."""
        import anthropic

        from app.providers.errors import TransientError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.APIConnectionError(
                message="Connection failed",
                request=MagicMock(),
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(TransientError, match="Connection failed"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_stream_maps_errors_same_as_complete(self, config):
        """stream() should map errors the same way as complete()."""
        import anthropic

        from app.providers.errors import RateLimitError

        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_error = anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )

            class MockStreamContext:
                async def __aenter__(self):
                    raise mock_error

                async def __aexit__(self, *args):
                    pass

            mock_client.messages.stream = MagicMock(return_value=MockStreamContext())
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(RateLimitError):
                async for _ in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                    pass


class TestClaudeAdapterLogging:
    """Test structured logging in Claude adapter (REQ-009 §8.1)."""

    @pytest.mark.asyncio
    async def test_logs_request_start(self, config, mock_anthropic_response):
        """Should log llm_request_start before making API call."""
        with (
            patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls,
            patch("app.providers.llm.claude_adapter.logger") as mock_logger,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify llm_request_start was logged with correct fields
            mock_logger.info.assert_any_call(
                "llm_request_start",
                provider="claude",
                model=adapter.get_model_for_task(TaskType.CHAT_RESPONSE),
                task="chat_response",
                message_count=1,
            )

    @pytest.mark.asyncio
    async def test_logs_request_complete(self, config, mock_anthropic_response):
        """Should log llm_request_complete after successful API call."""
        with (
            patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls,
            patch("app.providers.llm.claude_adapter.logger") as mock_logger,
        ):
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Find the llm_request_complete call
            complete_calls = [
                call
                for call in mock_logger.info.call_args_list
                if call[0][0] == "llm_request_complete"
            ]
            assert len(complete_calls) == 1

            call_kwargs = complete_calls[0][1]
            assert call_kwargs["provider"] == "claude"
            assert "sonnet" in call_kwargs["model"].lower()
            assert call_kwargs["task"] == "chat_response"
            assert call_kwargs["input_tokens"] == 10
            assert call_kwargs["output_tokens"] == 20
            assert "latency_ms" in call_kwargs

    @pytest.mark.asyncio
    async def test_logs_request_failed_on_error(self, config):
        """Should log llm_request_failed when API call fails."""
        import anthropic

        with (
            patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls,
            patch("app.providers.llm.claude_adapter.logger") as mock_logger,
        ):
            mock_client = AsyncMock()
            mock_error = anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )
            mock_client.messages.create = AsyncMock(side_effect=mock_error)
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            from app.providers.errors import RateLimitError as ZentropyRateLimitError

            with pytest.raises(ZentropyRateLimitError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify llm_request_failed was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "llm_request_failed"
            assert call_args[1]["provider"] == "claude"
            assert call_args[1]["task"] == "chat_response"
            assert "error" in call_args[1]
            assert call_args[1]["error_type"] == "RateLimitError"

    @pytest.mark.asyncio
    async def test_stream_logs_request_start(self, config):
        """stream() should log llm_request_start."""
        with (
            patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls,
            patch("app.providers.llm.claude_adapter.logger") as mock_logger,
        ):
            mock_client = AsyncMock()

            class MockStreamContext:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                @property
                def text_stream(self):
                    async def gen():
                        yield "Hello"

                    return gen()

            mock_client.messages.stream = MagicMock(return_value=MockStreamContext())
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            async for _ in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                pass

            # Verify llm_request_start was logged
            mock_logger.info.assert_any_call(
                "llm_request_start",
                provider="claude",
                model=adapter.get_model_for_task(TaskType.CHAT_RESPONSE),
                task="chat_response",
                message_count=1,
            )

    @pytest.mark.asyncio
    async def test_stream_logs_request_failed_on_error(self, config):
        """stream() should log llm_request_failed on error."""
        import anthropic

        with (
            patch("app.providers.llm.claude_adapter.AsyncAnthropic") as mock_client_cls,
            patch("app.providers.llm.claude_adapter.logger") as mock_logger,
        ):
            mock_client = AsyncMock()
            mock_error = anthropic.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )

            class MockStreamContext:
                async def __aenter__(self):
                    raise mock_error

                async def __aexit__(self, *args):
                    pass

            mock_client.messages.stream = MagicMock(return_value=MockStreamContext())
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            from app.providers.errors import RateLimitError as ZentropyRateLimitError

            with pytest.raises(ZentropyRateLimitError):
                async for _ in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                    pass

            # Verify llm_request_failed was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "llm_request_failed"


class TestClaudeAdapterModelOverride:
    """Test model_override parameter (REQ-022 §8.2)."""

    @pytest.mark.asyncio
    async def test_model_override_used_when_provided(
        self, config, mock_anthropic_response
    ):
        """complete() uses model_override instead of routing table."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            response = await adapter.complete(
                messages,
                TaskType.EXTRACTION,
                model_override="claude-3-opus-20240229",
            )

            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["model"] == "claude-3-opus-20240229"
            assert response.model == "claude-3-opus-20240229"

    @pytest.mark.asyncio
    async def test_model_override_none_falls_back_to_routing(
        self, config, mock_anthropic_response
    ):
        """complete() falls back to routing table when model_override is None."""
        with patch(
            "app.providers.llm.claude_adapter.AsyncAnthropic"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=mock_anthropic_response
            )
            mock_client_cls.return_value = mock_client

            adapter = ClaudeAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.EXTRACTION, model_override=None)

            call_kwargs = mock_client.messages.create.call_args.kwargs
            # Extraction routes to Haiku in DEFAULT_CLAUDE_ROUTING
            assert "haiku" in call_kwargs["model"].lower()
