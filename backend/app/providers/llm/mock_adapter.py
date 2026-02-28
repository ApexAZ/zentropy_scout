"""Mock LLM provider for testing.

REQ-009 §9.1: MockLLMProvider enables unit testing without hitting real LLM APIs.
"""

from collections.abc import AsyncIterator
from typing import Any

from app.providers.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    TaskType,
    ToolDefinition,
)


class MockLLMProvider(LLMProvider):
    """Mock provider for testing.

    WHY MOCK:
    - Unit tests shouldn't hit real APIs (cost, speed, flakiness)
    - Enables deterministic testing
    - Can simulate error conditions

    Attributes:
        responses: Pre-configured responses keyed by TaskType.
        calls: Record of all method invocations for test assertions.
        last_task: The most recent TaskType used in a call (for quick assertions).
    """

    @property
    def provider_name(self) -> str:
        """Return 'mock' for testing."""
        return "mock"

    def __init__(self, responses: dict[TaskType, str] | None = None) -> None:
        """Initialize mock provider with optional pre-configured responses.

        Args:
            responses: Dict mapping TaskType to response content. If not provided
                for a task, returns a default "Mock response for {task}" string.
        """
        # Don't call super().__init__() - we don't need a config for mock
        self.responses: dict[TaskType, str] = dict(responses) if responses else {}
        self.calls: list[dict[str, Any]] = []
        self.last_task: TaskType | None = None

    def set_response(self, task: TaskType, content: str) -> None:
        """Set or update the response for a specific task type.

        Args:
            task: The TaskType to configure.
            content: The response content to return for this task.
        """
        self.responses[task] = content

    async def complete(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a mock completion.

        Records the call for test assertions and returns a pre-configured
        or default response.

        Args:
            messages: Conversation history as list of LLMMessage.
            task: Task type for response lookup.
            max_tokens: Ignored (recorded in kwargs).
            temperature: Ignored (recorded in kwargs).
            stop_sequences: Ignored (recorded in kwargs).
            tools: Ignored (recorded in kwargs).
            json_mode: Ignored (recorded in kwargs).

        Returns:
            LLMResponse with configured or default content.
        """
        self.calls.append(
            {
                "method": "complete",
                "messages": messages,
                "task": task,
                "kwargs": {
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stop_sequences": stop_sequences,
                    "tools": tools,
                    "json_mode": json_mode,
                },
            }
        )
        self.last_task = task

        content = self.responses.get(task, f"Mock response for {task.value}")

        return LLMResponse(
            content=content,
            model="mock-model",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
            latency_ms=10,
        )

    async def stream(  # type: ignore[override]
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Generate a mock streaming completion.

        Records the call and yields content word-by-word with trailing spaces.

        Args:
            messages: Conversation history as list of LLMMessage.
            task: Task type for response lookup.
            max_tokens: Ignored (recorded in kwargs).
            temperature: Ignored (recorded in kwargs).

        Yields:
            Content chunks (words with trailing spaces).
        """
        self.calls.append(
            {
                "method": "stream",
                "messages": messages,
                "task": task,
                "kwargs": {
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            }
        )
        self.last_task = task

        content = self.responses.get(task, f"Mock response for {task.value}")
        for word in content.split():
            yield word + " "

    def get_model_for_task(self, _task: TaskType) -> str:
        """Return 'mock-model' for any task.

        Args:
            _task: Task type (ignored).

        Returns:
            Always returns 'mock-model'.
        """
        return "mock-model"

    def assert_called_with_task(self, task: TaskType) -> None:
        """Test helper to verify a task was called.

        Args:
            task: The TaskType that should have been called.

        Raises:
            AssertionError: If the task was not called.
        """
        tasks_called = [c["task"] for c in self.calls]
        assert task in tasks_called, f"Expected {task}, got {tasks_called}"
