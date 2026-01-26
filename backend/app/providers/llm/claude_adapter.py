"""Claude/Anthropic LLM adapter.

REQ-009 §4.2: Provider-specific adapter for Claude.
Note: This is a stub implementation. Full implementation will be added in §4.2.
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.providers.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    TaskType,
    ToolDefinition,
)

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


class ClaudeAdapter(LLMProvider):
    """Claude adapter using Anthropic SDK.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns

    Note: This is a stub. Full implementation will be added in §4.2.
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize Claude adapter.

        Args:
            config: Provider configuration with Anthropic API key.
        """
        super().__init__(config)
        # Actual client initialization will be added in §4.2

    async def complete(
        self,
        _messages: list[LLMMessage],
        _task: TaskType,
        _max_tokens: int | None = None,
        _temperature: float | None = None,
        _stop_sequences: list[str] | None = None,
        _tools: list[ToolDefinition] | None = None,
        _json_mode: bool = False,
    ) -> LLMResponse:
        """Generate completion using Claude.

        Implementation will be added in §4.2.
        """
        raise NotImplementedError("ClaudeAdapter.complete() not yet implemented")

    async def stream(
        self,
        _messages: list[LLMMessage],
        _task: TaskType,
        _max_tokens: int | None = None,
        _temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream completion using Claude.

        Implementation will be added in §4.2.
        """
        raise NotImplementedError("ClaudeAdapter.stream() not yet implemented")
        yield  # Makes this a generator

    def get_model_for_task(self, _task: TaskType) -> str:
        """Get model for task using routing table.

        Implementation will be added in §4.2.
        """
        raise NotImplementedError(
            "ClaudeAdapter.get_model_for_task() not yet implemented"
        )
