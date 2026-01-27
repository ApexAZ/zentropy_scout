"""Tests for MockLLMProvider (REQ-009 §9.1).

Tests the mock provider for unit testing without hitting real LLM APIs:
- Configurable responses by TaskType
- Call recording for test assertions
- assert_called_with_task() helper method
"""

import pytest

from app.providers.llm.base import LLMMessage, LLMResponse, TaskType
from app.providers.llm.mock_adapter import MockLLMProvider


class TestMockLLMProviderInstantiation:
    """Test MockLLMProvider creation."""

    def test_create_without_responses(self):
        """MockLLMProvider should be creatable with no pre-configured responses."""
        mock = MockLLMProvider()
        assert mock.responses == {}
        assert mock.calls == []

    def test_create_with_responses(self):
        """MockLLMProvider should accept pre-configured responses dict."""
        responses = {
            TaskType.SKILL_EXTRACTION: '{"skills": ["Python", "SQL"]}',
            TaskType.COVER_LETTER: "Dear Hiring Manager...",
        }
        mock = MockLLMProvider(responses=responses)
        assert mock.responses == responses

    def test_responses_are_copied(self):
        """MockLLMProvider should not mutate the input responses dict."""
        responses = {TaskType.CHAT_RESPONSE: "Hello"}
        mock = MockLLMProvider(responses=responses)
        mock.responses[TaskType.EXTRACTION] = "New"
        assert TaskType.EXTRACTION not in responses


class TestMockLLMProviderComplete:
    """Test MockLLMProvider.complete() method."""

    @pytest.mark.anyio
    async def test_complete_returns_llm_response(self):
        """complete() should return an LLMResponse object."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        response = await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert isinstance(response, LLMResponse)

    @pytest.mark.anyio
    async def test_complete_returns_configured_content(self):
        """complete() should return configured response for the task type."""
        mock = MockLLMProvider(
            responses={
                TaskType.SKILL_EXTRACTION: '{"skills": ["Python"]}',
            }
        )
        messages = [LLMMessage(role="user", content="Extract skills")]

        response = await mock.complete(messages, TaskType.SKILL_EXTRACTION)

        assert response.content == '{"skills": ["Python"]}'

    @pytest.mark.anyio
    async def test_complete_returns_default_for_unconfigured_task(self):
        """complete() should return default response for unconfigured task types."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        response = await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert response.content == "Mock response for chat_response"

    @pytest.mark.anyio
    async def test_complete_returns_mock_model(self):
        """complete() should always return 'mock-model' as the model."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        response = await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert response.model == "mock-model"

    @pytest.mark.anyio
    async def test_complete_returns_fixed_token_counts(self):
        """complete() should return fixed token counts for deterministic testing."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        response = await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert response.input_tokens == 100
        assert response.output_tokens == 50

    @pytest.mark.anyio
    async def test_complete_returns_stop_finish_reason(self):
        """complete() should return 'stop' as finish_reason."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        response = await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert response.finish_reason == "stop"

    @pytest.mark.anyio
    async def test_complete_returns_low_latency(self):
        """complete() should return low latency for fast tests."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        response = await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert response.latency_ms == 10


class TestMockLLMProviderCallRecording:
    """Test MockLLMProvider call recording for assertions."""

    @pytest.mark.anyio
    async def test_complete_records_call(self):
        """complete() should record the call for later assertions."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        await mock.complete(messages, TaskType.CHAT_RESPONSE)

        assert len(mock.calls) == 1
        assert mock.calls[0]["method"] == "complete"
        assert mock.calls[0]["messages"] == messages
        assert mock.calls[0]["task"] == TaskType.CHAT_RESPONSE

    @pytest.mark.anyio
    async def test_complete_records_kwargs(self):
        """complete() should record additional kwargs."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        await mock.complete(
            messages,
            TaskType.CHAT_RESPONSE,
            max_tokens=1000,
            temperature=0.7,
        )

        assert mock.calls[0]["kwargs"]["max_tokens"] == 1000
        assert mock.calls[0]["kwargs"]["temperature"] == 0.7

    @pytest.mark.anyio
    async def test_multiple_calls_are_recorded(self):
        """MockLLMProvider should record multiple calls."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]

        await mock.complete(messages, TaskType.CHAT_RESPONSE)
        await mock.complete(messages, TaskType.SKILL_EXTRACTION)
        await mock.complete(messages, TaskType.COVER_LETTER)

        assert len(mock.calls) == 3
        assert mock.calls[0]["task"] == TaskType.CHAT_RESPONSE
        assert mock.calls[1]["task"] == TaskType.SKILL_EXTRACTION
        assert mock.calls[2]["task"] == TaskType.COVER_LETTER


class TestMockLLMProviderStream:
    """Test MockLLMProvider.stream() method."""

    @pytest.mark.anyio
    async def test_stream_yields_words(self):
        """stream() should yield content word-by-word with trailing spaces."""
        mock = MockLLMProvider(
            responses={
                TaskType.CHAT_RESPONSE: "Hello world",
            }
        )
        messages = [LLMMessage(role="user", content="Hi")]

        chunks = []
        async for chunk in mock.stream(messages, TaskType.CHAT_RESPONSE):
            chunks.append(chunk)

        assert chunks == ["Hello ", "world "]

    @pytest.mark.anyio
    async def test_stream_records_call(self):
        """stream() should record the call for later assertions."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hi")]

        # Consume the iterator
        async for _ in mock.stream(messages, TaskType.CHAT_RESPONSE):
            pass

        assert len(mock.calls) == 1
        assert mock.calls[0]["method"] == "stream"
        assert mock.calls[0]["messages"] == messages
        assert mock.calls[0]["task"] == TaskType.CHAT_RESPONSE

    @pytest.mark.anyio
    async def test_stream_default_response(self):
        """stream() should use default response for unconfigured task types."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hi")]

        chunks = []
        async for chunk in mock.stream(messages, TaskType.EXTRACTION):
            chunks.append(chunk)

        # Default is "Mock response for {task.value}"
        assert "Mock " in chunks[0]


class TestMockLLMProviderGetModelForTask:
    """Test MockLLMProvider.get_model_for_task() method."""

    def test_get_model_for_task_returns_mock_model(self):
        """get_model_for_task() should always return 'mock-model'."""
        mock = MockLLMProvider()

        assert mock.get_model_for_task(TaskType.CHAT_RESPONSE) == "mock-model"
        assert mock.get_model_for_task(TaskType.SKILL_EXTRACTION) == "mock-model"
        assert mock.get_model_for_task(TaskType.COVER_LETTER) == "mock-model"


class TestMockLLMProviderAssertHelpers:
    """Test MockLLMProvider assertion helper methods."""

    @pytest.mark.anyio
    async def test_assert_called_with_task_passes(self):
        """assert_called_with_task() should pass when task was called."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]
        await mock.complete(messages, TaskType.SKILL_EXTRACTION)

        # Should not raise
        mock.assert_called_with_task(TaskType.SKILL_EXTRACTION)

    @pytest.mark.anyio
    async def test_assert_called_with_task_fails(self):
        """assert_called_with_task() should fail when task was not called."""
        mock = MockLLMProvider()
        messages = [LLMMessage(role="user", content="Hello")]
        await mock.complete(messages, TaskType.CHAT_RESPONSE)

        with pytest.raises(AssertionError) as exc_info:
            mock.assert_called_with_task(TaskType.SKILL_EXTRACTION)

        assert "SKILL_EXTRACTION" in str(exc_info.value)
        assert "CHAT_RESPONSE" in str(exc_info.value)

    def test_assert_called_with_task_fails_when_no_calls(self):
        """assert_called_with_task() should fail when no calls were made."""
        mock = MockLLMProvider()

        with pytest.raises(AssertionError):
            mock.assert_called_with_task(TaskType.CHAT_RESPONSE)


class TestMockLLMProviderIsLLMProvider:
    """Test that MockLLMProvider is a valid LLMProvider."""

    def test_mock_is_instance_of_llm_provider(self):
        """MockLLMProvider should be an instance of LLMProvider."""
        from app.providers.llm.base import LLMProvider

        mock = MockLLMProvider()
        assert isinstance(mock, LLMProvider)
