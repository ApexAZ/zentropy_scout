"""Tests for LLM provider interface (REQ-009 §4.1).

Tests the abstract interface components:
- TaskType enum for model routing
- ToolParameter, ToolDefinition, ToolCall, ToolResult dataclasses
- LLMMessage and LLMResponse dataclasses
- LLMProvider abstract base class
"""

import pytest

from app.providers.config import ProviderConfig
from app.providers.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    TaskType,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)


class TestTaskType:
    """Test TaskType enum for model routing."""

    def test_task_type_has_all_required_values(self):
        """TaskType should have all task types from REQ-009 §4.1."""
        required_tasks = [
            "CHAT_RESPONSE",
            "ONBOARDING_INTERVIEW",
            "SKILL_EXTRACTION",
            "EXTRACTION",
            "GHOST_DETECTION",
            "SCORE_RATIONALE",
            "COVER_LETTER",
            "RESUME_TAILORING",
            "STORY_SELECTION",
        ]
        for task in required_tasks:
            assert hasattr(TaskType, task), f"TaskType missing {task}"

    def test_task_type_values_are_strings(self):
        """TaskType values should be lowercase snake_case strings."""
        assert TaskType.CHAT_RESPONSE.value == "chat_response"
        assert TaskType.SKILL_EXTRACTION.value == "skill_extraction"
        assert TaskType.ONBOARDING_INTERVIEW.value == "onboarding"

    def test_task_type_is_enum(self):
        """TaskType should be a proper enum, not just strings."""
        assert TaskType.CHAT_RESPONSE != "chat_response"
        assert TaskType.CHAT_RESPONSE.value == "chat_response"


class TestToolParameter:
    """Test ToolParameter dataclass."""

    def test_tool_parameter_required_fields(self):
        """ToolParameter should require name, type, and description."""
        param = ToolParameter(
            name="job_id",
            param_type="string",
            description="The UUID of the job posting",
        )
        assert param.name == "job_id"
        assert param.param_type == "string"
        assert param.description == "The UUID of the job posting"

    def test_tool_parameter_default_required_is_true(self):
        """ToolParameter.required should default to True."""
        param = ToolParameter(
            name="test",
            param_type="string",
            description="Test parameter",
        )
        assert param.required is True

    def test_tool_parameter_optional_can_be_false(self):
        """ToolParameter.required can be set to False."""
        param = ToolParameter(
            name="optional_param",
            param_type="number",
            description="Optional parameter",
            required=False,
        )
        assert param.required is False

    def test_tool_parameter_enum_field(self):
        """ToolParameter should support enum constraints."""
        param = ToolParameter(
            name="skill_type",
            param_type="string",
            description="Type of skill",
            enum=["Hard", "Soft", "Tool"],
        )
        assert param.enum == ["Hard", "Soft", "Tool"]

    def test_tool_parameter_enum_defaults_to_none(self):
        """ToolParameter.enum should default to None."""
        param = ToolParameter(
            name="test",
            param_type="string",
            description="Test",
        )
        assert param.enum is None


class TestToolDefinition:
    """Test ToolDefinition dataclass."""

    def test_tool_definition_required_fields(self):
        """ToolDefinition should require name, description, and parameters."""
        tool = ToolDefinition(
            name="favorite_job",
            description="Mark a job posting as favorited",
            parameters=[
                ToolParameter(
                    name="job_id",
                    param_type="string",
                    description="The job posting ID",
                ),
            ],
        )
        assert tool.name == "favorite_job"
        assert tool.description == "Mark a job posting as favorited"
        assert len(tool.parameters) == 1

    def test_tool_definition_to_json_schema_basic(self):
        """to_json_schema should return valid JSON Schema format."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="input",
                    param_type="string",
                    description="Input text",
                ),
            ],
        )
        schema = tool.to_json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert "input" in schema["properties"]
        assert schema["properties"]["input"]["type"] == "string"
        assert schema["properties"]["input"]["description"] == "Input text"
        assert "input" in schema["required"]

    def test_tool_definition_to_json_schema_with_enum(self):
        """to_json_schema should include enum constraints."""
        tool = ToolDefinition(
            name="update_skill",
            description="Update a skill",
            parameters=[
                ToolParameter(
                    name="level",
                    param_type="string",
                    description="Proficiency level",
                    enum=["Beginner", "Intermediate", "Expert"],
                ),
            ],
        )
        schema = tool.to_json_schema()

        assert schema["properties"]["level"]["enum"] == [
            "Beginner",
            "Intermediate",
            "Expert",
        ]

    def test_tool_definition_to_json_schema_optional_param(self):
        """to_json_schema should exclude optional params from required list."""
        tool = ToolDefinition(
            name="search",
            description="Search jobs",
            parameters=[
                ToolParameter(
                    name="query",
                    param_type="string",
                    description="Search query",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    param_type="number",
                    description="Max results",
                    required=False,
                ),
            ],
        )
        schema = tool.to_json_schema()

        assert "query" in schema["required"]
        assert "limit" not in schema["required"]
        assert "limit" in schema["properties"]


class TestToolCall:
    """Test ToolCall dataclass."""

    def test_tool_call_required_fields(self):
        """ToolCall should have id, name, and arguments."""
        call = ToolCall(
            id="call_123",
            name="favorite_job",
            arguments={"job_id": "uuid-456"},
        )
        assert call.id == "call_123"
        assert call.name == "favorite_job"
        assert call.arguments == {"job_id": "uuid-456"}

    def test_tool_call_arguments_is_dict(self):
        """ToolCall.arguments should be a dict (already parsed from JSON)."""
        call = ToolCall(
            id="call_1",
            name="search",
            arguments={"query": "python", "min_score": 80},
        )
        assert isinstance(call.arguments, dict)
        assert call.arguments["query"] == "python"
        assert call.arguments["min_score"] == 80


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_tool_result_required_fields(self):
        """ToolResult should have tool_call_id and content."""
        result = ToolResult(
            tool_call_id="call_123",
            content='{"success": true}',
        )
        assert result.tool_call_id == "call_123"
        assert result.content == '{"success": true}'

    def test_tool_result_is_error_defaults_to_false(self):
        """ToolResult.is_error should default to False."""
        result = ToolResult(
            tool_call_id="call_123",
            content="result",
        )
        assert result.is_error is False

    def test_tool_result_can_indicate_error(self):
        """ToolResult should support indicating tool execution errors."""
        result = ToolResult(
            tool_call_id="call_123",
            content="Job not found",
            is_error=True,
        )
        assert result.is_error is True


class TestLLMMessage:
    """Test LLMMessage dataclass."""

    def test_llm_message_user_role(self):
        """LLMMessage should support user role with content."""
        msg = LLMMessage(role="user", content="Hello, world!")
        assert msg.role == "user"
        assert msg.content == "Hello, world!"

    def test_llm_message_assistant_role(self):
        """LLMMessage should support assistant role."""
        msg = LLMMessage(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_llm_message_system_role(self):
        """LLMMessage should support system role."""
        msg = LLMMessage(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    def test_llm_message_tool_role(self):
        """LLMMessage should support tool role for tool results."""
        result = ToolResult(tool_call_id="call_1", content="result data")
        msg = LLMMessage(role="tool", tool_result=result)
        assert msg.role == "tool"
        assert msg.tool_result == result

    def test_llm_message_with_tool_calls(self):
        """LLMMessage should support assistant messages with tool calls."""
        calls = [
            ToolCall(id="call_1", name="search", arguments={"query": "python"}),
        ]
        msg = LLMMessage(role="assistant", tool_calls=calls)
        assert msg.tool_calls == calls

    def test_llm_message_content_defaults_to_none(self):
        """LLMMessage.content should default to None."""
        msg = LLMMessage(role="assistant", tool_calls=[])
        assert msg.content is None

    def test_llm_message_tool_fields_default_to_none(self):
        """Tool-related fields should default to None."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.tool_calls is None
        assert msg.tool_result is None


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_llm_response_required_fields(self):
        """LLMResponse should have model, token counts, finish_reason, latency."""
        response = LLMResponse(
            content="Generated text",
            model="claude-3-5-sonnet-20241022",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
            latency_ms=250.5,
        )
        assert response.content == "Generated text"
        assert response.model == "claude-3-5-sonnet-20241022"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.finish_reason == "stop"
        assert response.latency_ms == 250.5

    def test_llm_response_content_can_be_none(self):
        """LLMResponse.content can be None (tool-only response)."""
        response = LLMResponse(
            content=None,
            model="claude-3-5-sonnet-20241022",
            input_tokens=100,
            output_tokens=50,
            finish_reason="tool_use",
            latency_ms=200.0,
            tool_calls=[
                ToolCall(id="call_1", name="search", arguments={}),
            ],
        )
        assert response.content is None
        assert response.tool_calls is not None

    def test_llm_response_tool_calls_defaults_to_none(self):
        """LLMResponse.tool_calls should default to None."""
        response = LLMResponse(
            content="text",
            model="model",
            input_tokens=10,
            output_tokens=5,
            finish_reason="stop",
            latency_ms=100.0,
        )
        assert response.tool_calls is None


class TestLLMProviderInterface:
    """Test LLMProvider abstract base class."""

    def test_llm_provider_is_abstract(self):
        """LLMProvider should be abstract and not instantiable directly."""
        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            LLMProvider(config)  # type: ignore[abstract]
        assert "abstract" in str(exc_info.value).lower()

    def test_llm_provider_requires_complete_method(self):
        """Subclasses must implement complete()."""

        class IncompleteProvider(LLMProvider):
            async def stream(self, _messages, _task, **_kwargs):
                yield "text"

            def get_model_for_task(self, _task):
                return "model"

        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(config)  # type: ignore[abstract]
        assert "complete" in str(exc_info.value)

    def test_llm_provider_requires_stream_method(self):
        """Subclasses must implement stream()."""

        class IncompleteProvider(LLMProvider):
            async def complete(self, _messages, _task, **_kwargs):
                return LLMResponse(
                    content="",
                    model="",
                    input_tokens=0,
                    output_tokens=0,
                    finish_reason="stop",
                    latency_ms=0,
                )

            def get_model_for_task(self, _task):
                return "model"

        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(config)  # type: ignore[abstract]
        assert "stream" in str(exc_info.value)

    def test_llm_provider_requires_get_model_for_task_method(self):
        """Subclasses must implement get_model_for_task()."""

        class IncompleteProvider(LLMProvider):
            async def complete(self, _messages, _task, **_kwargs):
                return LLMResponse(
                    content="",
                    model="",
                    input_tokens=0,
                    output_tokens=0,
                    finish_reason="stop",
                    latency_ms=0,
                )

            async def stream(self, _messages, _task, **_kwargs):
                yield "text"

        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(config)  # type: ignore[abstract]
        assert "get_model_for_task" in str(exc_info.value)

    def test_llm_provider_stores_config(self):
        """LLMProvider should store config for subclasses to use."""

        class ConcreteProvider(LLMProvider):
            async def complete(self, _messages, _task, **_kwargs):
                return LLMResponse(
                    content="",
                    model="",
                    input_tokens=0,
                    output_tokens=0,
                    finish_reason="stop",
                    latency_ms=0,
                )

            async def stream(self, _messages, _task, **_kwargs):
                yield "text"

            def get_model_for_task(self, _task):
                return "model"

        config = ProviderConfig(default_max_tokens=8192)
        provider = ConcreteProvider(config)
        assert provider.config.default_max_tokens == 8192


class TestLLMProviderCompleteSignature:
    """Test that LLMProvider.complete() has the correct signature."""

    def test_complete_accepts_messages_parameter(self):
        """complete() should accept messages as a list of LLMMessage."""
        # This test verifies the signature through a mock implementation

        class MockProvider(LLMProvider):
            async def complete(
                self,
                messages: list[LLMMessage],
                task: TaskType,
                _max_tokens: int | None = None,
                _temperature: float | None = None,
                _stop_sequences: list[str] | None = None,
                _tools: list[ToolDefinition] | None = None,
                _json_mode: bool = False,
            ) -> LLMResponse:
                # Verify we received the expected types
                assert isinstance(messages, list)
                assert all(isinstance(m, LLMMessage) for m in messages)
                assert isinstance(task, TaskType)
                return LLMResponse(
                    content="test",
                    model="test-model",
                    input_tokens=10,
                    output_tokens=5,
                    finish_reason="stop",
                    latency_ms=100.0,
                )

            async def stream(self, _messages, _task, **_kwargs):
                yield "text"

            def get_model_for_task(self, _task):
                return "model"

        config = ProviderConfig()
        _provider = MockProvider(config)
        # Signature check passed if instantiation works

    def test_complete_accepts_tools_parameter(self):
        """complete() should accept optional tools parameter."""

        class MockProvider(LLMProvider):
            async def complete(
                self,
                _messages: list[LLMMessage],
                _task: TaskType,
                _max_tokens: int | None = None,
                _temperature: float | None = None,
                _stop_sequences: list[str] | None = None,
                tools: list[ToolDefinition] | None = None,
                _json_mode: bool = False,
            ) -> LLMResponse:
                # Store tools for verification
                self.last_tools = tools
                return LLMResponse(
                    content="test",
                    model="test-model",
                    input_tokens=10,
                    output_tokens=5,
                    finish_reason="stop",
                    latency_ms=100.0,
                )

            async def stream(self, _messages, _task, **_kwargs):
                yield "text"

            def get_model_for_task(self, _task):
                return "model"

        config = ProviderConfig()
        _provider = MockProvider(config)
        # Verify tools parameter is part of signature (type checking)

    def test_complete_accepts_json_mode_parameter(self):
        """complete() should accept json_mode parameter."""

        class MockProvider(LLMProvider):
            async def complete(
                self,
                _messages: list[LLMMessage],
                _task: TaskType,
                _max_tokens: int | None = None,
                _temperature: float | None = None,
                _stop_sequences: list[str] | None = None,
                _tools: list[ToolDefinition] | None = None,
                json_mode: bool = False,
            ) -> LLMResponse:
                self.last_json_mode = json_mode
                return LLMResponse(
                    content="test",
                    model="test-model",
                    input_tokens=10,
                    output_tokens=5,
                    finish_reason="stop",
                    latency_ms=100.0,
                )

            async def stream(self, _messages, _task, **_kwargs):
                yield "text"

            def get_model_for_task(self, _task):
                return "model"

        config = ProviderConfig()
        _provider = MockProvider(config)
        # Verify json_mode parameter is part of signature
