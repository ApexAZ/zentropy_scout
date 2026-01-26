"""Abstract base class for LLM providers.

REQ-009 §4.1: LLMProvider abstract interface.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


class CompletionResult(BaseModel):
    """Result from an LLM completion.

    Attributes:
        content: The generated text content.
        model: The model that generated the response.
        usage: Token usage statistics.
        structured_output: Parsed output if output_schema was provided.
    """

    content: str
    model: str
    usage: dict | None = None
    structured_output: dict | None = None


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    WHY ABC:
    - Enforces consistent interface across providers
    - Enables dependency injection for testing
    - Allows swapping providers without code changes
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize with provider configuration.

        Args:
            config: Provider configuration including API keys and defaults.
        """
        self.config = config

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        task_type: str = "general",
        output_schema: type[BaseModel] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> CompletionResult:
        """Generate a completion for the given prompt.

        Args:
            prompt: The user prompt to complete.
            system_prompt: Optional system prompt for context.
            task_type: Task type for model routing.
            output_schema: Optional Pydantic model for structured output.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.

        Returns:
            CompletionResult with generated content.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream a completion for the given prompt.

        Args:
            prompt: The user prompt to complete.
            system_prompt: Optional system prompt for context.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.

        Yields:
            Text chunks as they are generated.
        """
        ...
