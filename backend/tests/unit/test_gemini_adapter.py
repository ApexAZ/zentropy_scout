"""Tests for Gemini LLM adapter (REQ-009 §4.2).

Tests the GeminiAdapter implementation with mocked Google AI client.
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
from app.providers.llm.gemini_adapter import GeminiAdapter


@pytest.fixture
def config():
    """Create a test provider config using built-in defaults."""
    return ProviderConfig(
        llm_provider="gemini",
        google_api_key="test-api-key",
        # No custom routing - use built-in defaults
        default_max_tokens=4096,
        default_temperature=0.7,
    )


@pytest.fixture
def mock_gemini_response():
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
def mock_gemini_tool_response():
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


class TestGeminiAdapterInit:
    """Test GeminiAdapter initialization."""

    def test_init_configures_api_key(self, config):
        """GeminiAdapter should configure the API key."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            _adapter = GeminiAdapter(config)  # noqa: F841
            mock_genai.configure.assert_called_once_with(api_key="test-api-key")

    def test_init_stores_config(self, config):
        """GeminiAdapter should store the config."""
        with patch("app.providers.llm.gemini_adapter.genai"):
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
        with patch("app.providers.llm.gemini_adapter.genai"):
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
        with patch("app.providers.llm.gemini_adapter.genai"):
            adapter = GeminiAdapter(config_with_override)
            # Behavior: custom routing takes effect
            assert adapter.get_model_for_task(TaskType.EXTRACTION) == "my-custom-model"
            # Non-overridden tasks still use quality model
            chat_model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            assert "pro" in chat_model.lower()


class TestGeminiAdapterGetModelForTask:
    """Test GeminiAdapter.get_model_for_task() behavior."""

    def test_extraction_tasks_use_cost_effective_model(self, config):
        """Extraction tasks should route to cheaper/faster model (Flash)."""
        with patch("app.providers.llm.gemini_adapter.genai"):
            adapter = GeminiAdapter(config)
            model = adapter.get_model_for_task(TaskType.EXTRACTION)
            # Behavior: extraction uses Flash for cost optimization
            assert "flash" in model.lower()

    def test_chat_tasks_use_quality_model(self, config):
        """Chat/conversation tasks should route to higher quality model (Pro)."""
        with patch("app.providers.llm.gemini_adapter.genai"):
            adapter = GeminiAdapter(config)
            model = adapter.get_model_for_task(TaskType.CHAT_RESPONSE)
            # Behavior: chat uses Pro for better reasoning
            assert "pro" in model.lower()

    def test_all_task_types_return_valid_model(self, config):
        """Every TaskType should return a valid Gemini model identifier."""
        with patch("app.providers.llm.gemini_adapter.genai"):
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
    async def test_complete_basic_message(self, config, mock_gemini_response):
        """Should make API call and return LLMResponse."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello!")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.content == "Hello from Gemini!"
            assert response.input_tokens == 10
            assert response.output_tokens == 20
            assert response.finish_reason == "STOP"
            assert response.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_complete_extracts_system_message(self, config, mock_gemini_response):
        """Should extract system message and pass as system_instruction."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [
                LLMMessage(role="system", content="You are a helpful assistant."),
                LLMMessage(role="user", content="Hello!"),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            # Verify system instruction was passed to GenerativeModel
            call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
            assert call_kwargs["system_instruction"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_complete_with_tool_response(self, config, mock_gemini_tool_response):
        """Should parse function calls from response."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_tool_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

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
    async def test_complete_converts_tools_to_gemini_format(
        self, config, mock_gemini_response
    ):
        """Should convert ToolDefinition to Gemini function_declarations format."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
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

            # Verify tools were passed to GenerativeModel
            call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
            assert "tools" in call_kwargs
            # Gemini uses function_declarations
            assert (
                call_kwargs["tools"][0]["function_declarations"][0]["name"]
                == "test_tool"
            )

    @pytest.mark.asyncio
    async def test_complete_json_mode_uses_response_mime_type(
        self, config, mock_gemini_response
    ):
        """JSON mode should use response_mime_type for Gemini."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [
                LLMMessage(role="system", content="Extract skills."),
                LLMMessage(role="user", content="Python, JavaScript"),
            ]

            await adapter.complete(messages, TaskType.EXTRACTION, json_mode=True)

            call_kwargs = mock_model.generate_content_async.call_args.kwargs
            # Check generation_config has response_mime_type
            assert (
                call_kwargs["generation_config"]["response_mime_type"]
                == "application/json"
            )

    @pytest.mark.asyncio
    async def test_complete_uses_config_defaults(self, config, mock_gemini_response):
        """Should use config defaults when not overridden."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_kwargs = mock_model.generate_content_async.call_args.kwargs
            assert call_kwargs["generation_config"]["max_output_tokens"] == 4096
            assert call_kwargs["generation_config"]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_complete_allows_override_max_tokens(
        self, config, mock_gemini_response
    ):
        """Should allow overriding max_tokens."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE, max_tokens=1000)

            call_kwargs = mock_model.generate_content_async.call_args.kwargs
            assert call_kwargs["generation_config"]["max_output_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_complete_passes_stop_sequences(self, config, mock_gemini_response):
        """Should pass stop_sequences to generation config."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            await adapter.complete(
                messages, TaskType.CHAT_RESPONSE, stop_sequences=["END", "STOP"]
            )

            call_kwargs = mock_model.generate_content_async.call_args.kwargs
            assert call_kwargs["generation_config"]["stop_sequences"] == ["END", "STOP"]

    @pytest.mark.asyncio
    async def test_complete_includes_model_in_response(
        self, config, mock_gemini_response
    ):
        """Response should include the model used."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            response = await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            assert response.model == "gemini-1.5-pro"


class TestGeminiAdapterStream:
    """Test GeminiAdapter.stream() method."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self, config):
        """Should yield text chunks from stream."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()

            # Create async generator for stream
            async def mock_stream():
                for text in ["Hello", ", ", "world", "!"]:
                    chunk = MagicMock()
                    chunk.text = text
                    yield chunk

            mock_model.generate_content_async = AsyncMock(return_value=mock_stream())
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Say hello")]

            chunks = []
            async for chunk in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                chunks.append(chunk)

            assert chunks == ["Hello", ", ", "world", "!"]

    @pytest.mark.asyncio
    async def test_stream_uses_correct_model(self, config):
        """Should use model from routing table."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()

            async def mock_stream():
                chunk = MagicMock()
                chunk.text = "text"
                yield chunk

            mock_model.generate_content_async = AsyncMock(return_value=mock_stream())
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            async for _ in adapter.stream(messages, TaskType.EXTRACTION):
                pass

            # Check model was created with correct name
            mock_genai.GenerativeModel.assert_called()
            call_args = mock_genai.GenerativeModel.call_args
            assert call_args[0][0] == "gemini-1.5-flash"


class TestGeminiAdapterMessageConversion:
    """Test message conversion to Gemini format."""

    @pytest.mark.asyncio
    async def test_converts_user_and_assistant_messages(
        self, config, mock_gemini_response
    ):
        """Should convert role names to Gemini format (assistant -> model)."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [
                LLMMessage(role="user", content="Hello"),
                LLMMessage(role="assistant", content="Hi there!"),
                LLMMessage(role="user", content="How are you?"),
            ]

            await adapter.complete(messages, TaskType.CHAT_RESPONSE)

            call_args = mock_model.generate_content_async.call_args
            contents = call_args[0][0]

            # Gemini uses "model" instead of "assistant"
            assert contents[0]["role"] == "user"
            assert contents[1]["role"] == "model"
            assert contents[2]["role"] == "user"

    @pytest.mark.asyncio
    async def test_handles_tool_result_as_function_response(
        self, config, mock_gemini_response
    ):
        """Should convert tool results to function_response format."""
        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                return_value=mock_gemini_response
            )
            mock_genai.GenerativeModel.return_value = mock_model

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

            call_args = mock_model.generate_content_async.call_args
            contents = call_args[0][0]

            # Tool result should be function_response in Gemini
            tool_result_msg = contents[-1]
            assert tool_result_msg["role"] == "user"
            assert "function_response" in tool_result_msg["parts"][0]


class TestGeminiAdapterErrorMapping:
    """Test error mapping from Google AI SDK to unified errors (REQ-009 §7.3)."""

    @pytest.mark.asyncio
    async def test_resource_exhausted_error_mapped_to_rate_limit(self, config):
        """Should map ResourceExhausted to RateLimitError."""
        from google.api_core.exceptions import ResourceExhausted

        from app.providers.errors import RateLimitError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=ResourceExhausted("Rate limit exceeded")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_permission_denied_error_mapped_to_authentication(self, config):
        """Should map PermissionDenied to AuthenticationError."""
        from google.api_core.exceptions import PermissionDenied

        from app.providers.errors import AuthenticationError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=PermissionDenied("Invalid API key")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_unauthenticated_error_mapped_to_authentication(self, config):
        """Should map Unauthenticated to AuthenticationError."""
        from google.api_core.exceptions import Unauthenticated

        from app.providers.errors import AuthenticationError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=Unauthenticated("Credentials not valid")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(AuthenticationError, match="Credentials not valid"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_invalid_argument_with_context_length_mapped(self, config):
        """Should map InvalidArgument with 'context' to ContextLengthError."""
        from google.api_core.exceptions import InvalidArgument

        from app.providers.errors import ContextLengthError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=InvalidArgument("Request exceeds context window limit")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ContextLengthError, match="context"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_invalid_argument_with_safety_mapped_to_content_filter(self, config):
        """Should map InvalidArgument with 'safety' to ContentFilterError."""
        from google.api_core.exceptions import InvalidArgument

        from app.providers.errors import ContentFilterError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=InvalidArgument("Blocked due to safety settings")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ContentFilterError, match="safety"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_generic_invalid_argument_mapped_to_provider_error(self, config):
        """Should map generic InvalidArgument to ProviderError."""
        from google.api_core.exceptions import InvalidArgument

        from app.providers.errors import ProviderError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=InvalidArgument("Invalid request parameters")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(ProviderError, match="Invalid request parameters"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_service_unavailable_mapped_to_transient_error(self, config):
        """Should map ServiceUnavailable to TransientError (safe to retry)."""
        from google.api_core.exceptions import ServiceUnavailable

        from app.providers.errors import TransientError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=ServiceUnavailable("Service temporarily unavailable")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(TransientError, match="Service temporarily unavailable"):
                await adapter.complete(messages, TaskType.CHAT_RESPONSE)

    @pytest.mark.asyncio
    async def test_stream_maps_errors_same_as_complete(self, config):
        """stream() should map errors the same way as complete()."""
        from google.api_core.exceptions import ResourceExhausted

        from app.providers.errors import RateLimitError

        with patch("app.providers.llm.gemini_adapter.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(
                side_effect=ResourceExhausted("Rate limit exceeded")
            )
            mock_genai.GenerativeModel.return_value = mock_model

            adapter = GeminiAdapter(config)
            messages = [LLMMessage(role="user", content="Hello")]

            with pytest.raises(RateLimitError):
                async for _ in adapter.stream(messages, TaskType.CHAT_RESPONSE):
                    pass
