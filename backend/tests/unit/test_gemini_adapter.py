"""Tests for Gemini LLM adapter (REQ-009 §4.2).

Tests the GeminiAdapter implementation with mocked Google GenAI SDK client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.config import ProviderConfig
from app.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
    TransientError,
)
from app.providers.llm.base import (
    LLMMessage,
    TaskType,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from app.providers.llm.gemini_adapter import GeminiAdapter


@pytest.fixture
def config():
    """Create a test provider config using built-in defaults."""
    return ProviderConfig(
        llm_provider="gemini",
        google_api_key="test-api-key",
        default_max_tokens=4096,
        default_temperature=0.7,
    )


@pytest.fixture
def mock_genai_response():
    """Create a mock Gemini API response."""
    response = MagicMock()

    # Text part
    text_part = MagicMock()
    text_part.text = "Hello from Gemini!"
    text_part.function_call = None

    candidate = MagicMock()
    candidate.content = MagicMock()
    candidate.content.parts = [text_part]
    candidate.finish_reason = MagicMock()
    candidate.finish_reason.name = "STOP"

    response.candidates = [candidate]
    response.usage_metadata = MagicMock(
        prompt_token_count=10,
        candidates_token_count=20,
    )
    return response


@pytest.fixture
def mock_genai_tool_response():
    """Create a mock Gemini API response with function call."""
    response = MagicMock()

    # Function call part
    function_part = MagicMock()
    function_part.text = None
    function_part.function_call = MagicMock()
    function_part.function_call.name = "favorite_job"
    function_part.function_call.args = {"job_id": "job-uuid-456"}

    candidate = MagicMock()
    candidate.content = MagicMock()
    candidate.content.parts = [function_part]
    candidate.finish_reason = MagicMock()
    candidate.finish_reason.name = "STOP"

    response.candidates = [candidate]
    response.usage_metadata = MagicMock(
        prompt_token_count=15,
        candidates_token_count=25,
    )
    return response


@pytest.fixture
def mock_client():
    """Create a mock genai.Client with async methods."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock()
    client.aio.models.generate_content_stream = AsyncMock()
    return client


class TestGeminiAdapterInit:
    """Test GeminiAdapter initialization."""

    def test_init_creates_client_with_api_key(self, config):
        """GeminiAdapter should create a Client with the API key."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            _adapter = GeminiAdapter(config)
            mock_genai.Client.assert_called_once_with(api_key="test-api-key")

    def test_init_stores_config(self, config):
        """GeminiAdapter should store the config."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            adapter = GeminiAdapter(config)
            assert adapter.config is config

    def test_init_routes_extraction_to_cheaper_model_by_default(self):
        """Without custom routing, extraction tasks should use a cheaper model."""
        config_no_routing = ProviderConfig(
            llm_provider="gemini",
            google_api_key="test-api-key",
            gemini_model_routing=None,
            default_max_tokens=4096,
            default_temperature=0.7,
        )
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            adapter = GeminiAdapter(config_no_routing)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            # Behavior: extraction uses Flash model (cheaper)
            assert "flash" in model.lower()

    def test_init_config_routing_overrides_defaults(self):
        """Custom config routing should override default model selection."""
        custom_routing = {"extraction": "my-custom-model"}
        config_with_override = ProviderConfig(
            llm_provider="gemini",
            google_api_key="test-api-key",
            gemini_model_routing=custom_routing,
            default_max_tokens=4096,
            default_temperature=0.7,
        )
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            adapter = GeminiAdapter(config_with_override)
            # Behavior: custom routing takes effect
            assert adapter.get_model_for_task(TaskType.EXTRACTION) == "my-custom-model"


class TestGeminiAdapterGetModelForTask:
    """Test GeminiAdapter.get_model_for_task() behavior."""

    def test_extraction_tasks_use_cost_effective_model(self, config):
        """Extraction tasks should route to cheaper/faster model (Flash)."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            adapter = GeminiAdapter(config)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            # Behavior: extraction uses Flash for cost optimization
            assert "flash" in model.lower()

    def test_all_task_types_return_valid_model(self, config):
        """Every TaskType should return a valid Gemini model identifier."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_genai.Client.return_value = MagicMock()
            adapter = GeminiAdapter(config)
            for task_type in TaskType:
                model = adapter.get_model_for_task(task_type)
                # Behavior: all tasks return a model (no None, no empty string)
                assert model is not None
                assert len(model) > 0
                assert "gemini" in model.lower()


class TestGeminiAdapterComplete:
    """Test GeminiAdapter.complete() method."""

    @pytest.mark.asyncio
    async def test_complete_basic_message(
        self, config, mock_genai_response, mock_client
    ):
        """Should make API call and return LLMResponse."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.return_value = mock_genai_response
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.content == "Hello from Gemini!"
            assert response.input_tokens == 10
            assert response.output_tokens == 20
            assert response.finish_reason == "STOP"
            assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_complete_with_tool_response(
        self, config, mock_genai_tool_response, mock_client
    ):
        """Should parse function calls from response."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.return_value = (
                mock_genai_tool_response
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
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
            assert response.tool_calls[0].name == "favorite_job"
            assert response.tool_calls[0].arguments == {"job_id": "job-uuid-456"}

    @pytest.mark.asyncio
    async def test_complete_includes_model_in_response(
        self, config, mock_genai_response, mock_client
    ):
        """Response should include the model used."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.return_value = mock_genai_response
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert "gemini" in response.model.lower()


class TestGeminiAdapterStream:
    """Test GeminiAdapter.stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self, config, mock_client):
        """Should yield text chunks from stream."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            # Create async generator for stream
            async def mock_stream():
                for text in ["Hello", ", ", "world", "!"]:
                    chunk = MagicMock()
                    chunk.text = text
                    yield chunk

            mock_client.aio.models.generate_content_stream.return_value = mock_stream()
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Say hello")]

            chunks = []
            async for chunk in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                chunks.append(chunk)

            assert chunks == ["Hello", ", ", "world", "!"]


class TestGeminiAdapterMessageConversion:
    """Test message conversion to Gemini format."""

    @pytest.mark.asyncio
    async def test_converts_user_and_assistant_messages(
        self, config, mock_genai_response, mock_client
    ):
        """Should convert role names to Gemini format (assistant -> model)."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.return_value = mock_genai_response
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [
                LLMMessage(role="user", content="Hello"),
                LLMMessage(role="assistant", content="Hi there!"),
                LLMMessage(role="user", content="How are you?"),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify the call was made
            mock_client.aio.models.generate_content.assert_called_once()
            call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
            contents = call_kwargs["contents"]

            # Gemini uses "model" instead of "assistant"
            assert contents[0].role == "user"
            assert contents[1].role == "model"
            assert contents[2].role == "user"

    @pytest.mark.asyncio
    async def test_handles_tool_result_as_function_response(
        self, config, mock_genai_response, mock_client
    ):
        """Should convert tool results to function_response format."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.return_value = mock_genai_response
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
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

            # Verify the call was made with function response
            mock_client.aio.models.generate_content.assert_called_once()


class TestGeminiAdapterErrorMapping:
    """Test error mapping from Google GenAI SDK to unified errors (REQ-009 §7.3)."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_mapped(self, config, mock_client):
        """Should map resource exhausted errors to RateLimitError."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Resource exhausted: Rate limit exceeded"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(RateLimitError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_permission_error_mapped_to_authentication(self, config, mock_client):
        """Should map permission errors to AuthenticationError."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Permission denied: Invalid API key"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(AuthenticationError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_context_length_error_mapped(self, config, mock_client):
        """Should map context/token errors to ContextLengthError."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Request exceeds context window token limit"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ContextLengthError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_safety_error_mapped_to_content_filter(self, config, mock_client):
        """Should map safety/blocked errors to ContentFilterError."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Request blocked due to safety settings"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ContentFilterError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_unavailable_error_mapped_to_transient(self, config, mock_client):
        """Should map unavailable/503 errors to TransientError."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Service unavailable (503)"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(TransientError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_generic_error_mapped_to_provider_error(self, config, mock_client):
        """Should map generic errors to ProviderError."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Unknown error occurred"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ProviderError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)


class TestGeminiAdapterLogging:
    """Test structured logging in Gemini adapter (REQ-009 §8.1)."""

    @pytest.mark.asyncio
    async def test_logs_request_start(self, config, mock_genai_response, mock_client):
        """Should log llm_request_start before making API call."""
        with (
            patch("app.providers.llm.gemini_adapter.genai") as mock_genai,
            patch("app.providers.llm.gemini_adapter.logger") as mock_logger,
        ):
            mock_client.aio.models.generate_content.return_value = mock_genai_response
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify llm_request_start was logged
            mock_logger.info.assert_any_call(
                "llm_request_start",
                provider="gemini",
                model=adapter.get_model_for_task(TaskType.CHAT_RESPONSE),
                task="chat_response",
                message_count=1,
            )

    @pytest.mark.asyncio
    async def test_logs_request_complete(
        self, config, mock_genai_response, mock_client
    ):
        """Should log llm_request_complete after successful API call."""
        with (
            patch("app.providers.llm.gemini_adapter.genai") as mock_genai,
            patch("app.providers.llm.gemini_adapter.logger") as mock_logger,
        ):
            mock_client.aio.models.generate_content.return_value = mock_genai_response
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
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
            assert call_kwargs["provider"] == "gemini"
            assert call_kwargs["task"] == "chat_response"
            assert call_kwargs["input_tokens"] == 10
            assert call_kwargs["output_tokens"] == 20
            assert "latency_ms" in call_kwargs

    @pytest.mark.asyncio
    async def test_logs_request_failed_on_error(self, config, mock_client):
        """Should log llm_request_failed when API call fails."""
        with (
            patch("app.providers.llm.gemini_adapter.genai") as mock_genai,
            patch("app.providers.llm.gemini_adapter.logger") as mock_logger,
        ):
            mock_client.aio.models.generate_content.side_effect = Exception(
                "Resource exhausted: Rate limit"
            )
            mock_genai.Client.return_value = mock_client

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            with pytest.raises(RateLimitError):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify llm_request_failed was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "llm_request_failed"
            assert call_args[1]["provider"] == "gemini"
            assert call_args[1]["task"] == "chat_response"
