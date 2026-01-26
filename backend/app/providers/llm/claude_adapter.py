"""Claude/Anthropic LLM adapter.

REQ-009 §4.2: Provider-specific adapter for Claude.
"""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.providers.llm.base import CompletionResult, LLMProvider

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


class ClaudeAdapter(LLMProvider):
    """Claude adapter using Anthropic SDK.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns
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
        prompt: str,
        system_prompt: str | None = None,
        task_type: str = "general",
        output_schema: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> CompletionResult:
        """Generate completion using Claude.

        Implementation will be added in §4.2.
        """
        raise NotImplementedError("ClaudeAdapter.complete() not yet implemented")

    async def stream(
        self,
        prompt: str,  # noqa: ARG002
        system_prompt: str | None = None,  # noqa: ARG002
        max_tokens: int | None = None,  # noqa: ARG002
        temperature: float | None = None,  # noqa: ARG002
    ) -> AsyncIterator[str]:
        """Stream completion using Claude.

        Implementation will be added in §4.2.
        """
        raise NotImplementedError("ClaudeAdapter.stream() not yet implemented")
        yield  # Makes this a generator
