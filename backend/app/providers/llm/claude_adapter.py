"""Claude/Anthropic LLM adapter.

REQ-009 §4.2: Provider-specific adapter for Claude.

WHY ANTHROPIC AS PRIMARY:
- Best instruction-following for agentic tasks
- Superior at maintaining persona (onboarding)
- Strong at structured extraction
- Competitive pricing with Haiku for high-volume tasks
"""

import contextlib
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import anthropic
import structlog
from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage

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
    LLMProvider,
    LLMResponse,
    TaskType,
    ToolCall,
    ToolDefinition,
)

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig

logger = structlog.get_logger()


# Default model routing table per REQ-009 §4.3
# WHY TASK-BASED ROUTING: Optimizes cost without sacrificing quality
# - High-volume extraction tasks use Haiku (~$0.0002/call)
# - Quality-critical tasks use Sonnet (~$0.01/call for cover letters)
DEFAULT_CLAUDE_ROUTING: dict[str, str] = {
    # High-volume, simple extraction tasks → Claude 3.5 Haiku (cheaper, faster)
    "skill_extraction": "claude-3-5-haiku-20241022",
    "extraction": "claude-3-5-haiku-20241022",
    "ghost_detection": "claude-3-5-haiku-20241022",
    # Quality-critical tasks → Claude 3.5 Sonnet (better reasoning, persona maintenance)
    "chat_response": "claude-3-5-sonnet-20241022",
    "onboarding": "claude-3-5-sonnet-20241022",
    "score_rationale": "claude-3-5-sonnet-20241022",
    "cover_letter": "claude-3-5-sonnet-20241022",
    "resume_tailoring": "claude-3-5-sonnet-20241022",
    "story_selection": "claude-3-5-sonnet-20241022",
    "resume_parsing": "claude-3-5-haiku-20241022",
}

# Fallback if task type not in routing table
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


def _classify_claude_error(error: Exception) -> ProviderError:
    """Map Claude/Anthropic exceptions to internal error taxonomy.

    Returns a ProviderError subclass instance (does not raise).
    The caller is responsible for raising via ``raise _classify_claude_error(e) from e``.
    """
    if isinstance(error, anthropic.RateLimitError):
        retry_after = None
        if hasattr(error, "response") and error.response is not None:
            retry_header = error.response.headers.get("retry-after")
            if retry_header is not None:
                with contextlib.suppress(ValueError):
                    retry_after = float(retry_header)
        return RateLimitError(str(error), retry_after_seconds=retry_after)

    if isinstance(error, anthropic.AuthenticationError):
        return AuthenticationError(str(error))

    if isinstance(error, anthropic.BadRequestError):
        error_msg = str(error).lower()
        if "context_length" in error_msg:
            return ContextLengthError(str(error))
        if "content_policy" in error_msg:
            return ContentFilterError(str(error))
        return ProviderError(str(error))

    if isinstance(error, anthropic.APIConnectionError):
        return TransientError(str(error))

    return ProviderError(str(error))


def _convert_tool_result_message(msg: LLMMessage) -> dict:
    """Convert a tool result message to Anthropic tool_result format.

    WHY: Anthropic uses tool_result content blocks within user messages.
    """
    assert msg.tool_result is not None, "tool-role message must have tool_result"
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": msg.tool_result.tool_call_id,
                "content": msg.tool_result.content,
                "is_error": msg.tool_result.is_error,
            }
        ],
    }


def _convert_tool_call_message(msg: LLMMessage) -> dict:
    """Convert an assistant message with tool calls to Anthropic content blocks format.

    WHY: Assistant messages with tool calls need content blocks format for Anthropic.
    """
    assert msg.tool_calls is not None, "assistant message must have tool_calls"
    content_blocks: list[dict] = []
    if msg.content:
        content_blocks.append({"type": "text", "text": msg.content})
    for tc in msg.tool_calls:
        content_blocks.append(
            {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            }
        )
    return {"role": "assistant", "content": content_blocks}


def _convert_claude_messages(
    messages: list[LLMMessage],
) -> tuple[str | None, list[dict]]:
    """Convert LLMMessages to Anthropic format, extracting system message.

    Returns:
        Tuple of (system_message, api_messages) where system_message is extracted
        from any message with role="system" and api_messages are the converted
        conversation messages.
    """
    system_msg = None
    api_messages: list[dict] = []

    for msg in messages:
        if msg.role == "system":
            system_msg = msg.content
        elif msg.role == "tool":
            api_messages.append(_convert_tool_result_message(msg))
        elif msg.tool_calls:
            api_messages.append(_convert_tool_call_message(msg))
        else:
            api_messages.append({"role": msg.role, "content": msg.content})

    return system_msg, api_messages


def _parse_claude_response(
    response: AnthropicMessage,
) -> tuple[str | None, list[ToolCall] | None, str]:
    """Parse Anthropic response into content, tool_calls, and finish_reason."""
    content = None
    tool_calls: list[ToolCall] | None = None

    for block in response.content:
        if block.type == "text":
            content = block.text
        elif block.type == "tool_use":
            if tool_calls is None:
                tool_calls = []
            tool_calls.append(
                ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                )
            )

    return content, tool_calls, response.stop_reason or "unknown"


class ClaudeAdapter(LLMProvider):
    """Claude adapter using Anthropic SDK.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns
    """

    @property
    def provider_name(self) -> str:
        """Return 'claude' for pricing lookup and usage tracking."""
        return "claude"

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize Claude adapter.

        Args:
            config: Provider configuration with Anthropic API key.
        """
        super().__init__(config)
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
        # Merge config routing on top of defaults (config overrides defaults)
        self.model_routing = {**DEFAULT_CLAUDE_ROUTING}
        if config.claude_model_routing:
            self.model_routing.update(config.claude_model_routing)

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
        """Generate completion using Claude.

        Args:
            messages: Conversation history as list of LLMMessage.
            task: Task type for model routing.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.
            stop_sequences: Custom stop sequences.
            tools: Available tools the LLM can call.
            json_mode: If True, enforce JSON output format.

        Returns:
            LLMResponse with content and/or tool_calls.
        """
        model = self.get_model_for_task(task)
        system_msg, api_messages = _convert_claude_messages(messages)

        # WHY: Anthropic doesn't have native JSON mode, so we modify system prompt
        if json_mode and system_msg:
            system_msg = (
                system_msg + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
                "No explanations, no markdown, just the JSON object."
            )
        elif json_mode:
            system_msg = (
                "Respond ONLY with valid JSON. "
                "No explanations, no markdown, just the JSON object."
            )

        # Convert tools to Anthropic format
        api_tools = None
        if tools:
            api_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.to_json_schema(),
                }
                for tool in tools
            ]

        # Log request start
        logger.info(
            "llm_request_start",
            provider="claude",
            model=model,
            task=task.value,
            message_count=len(messages),
        )

        start_time = time.monotonic()

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens
                if max_tokens is not None
                else self.config.default_max_tokens,
                temperature=temperature
                if temperature is not None
                else self.config.default_temperature,
                system=system_msg,  # type: ignore[arg-type]
                messages=api_messages,  # type: ignore[arg-type]
                stop_sequences=stop_sequences,  # type: ignore[arg-type]
                tools=api_tools,  # type: ignore[arg-type]
            )
        except (
            anthropic.RateLimitError,
            anthropic.AuthenticationError,
            anthropic.BadRequestError,
            anthropic.APIConnectionError,
        ) as e:
            logger.error(
                "llm_request_failed",
                provider="claude",
                model=model,
                task=task.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise _classify_claude_error(e) from e

        latency_ms = (time.monotonic() - start_time) * 1000
        content, tool_calls, finish_reason = _parse_claude_response(response)

        # Log request complete
        logger.info(
            "llm_request_complete",
            provider="claude",
            model=model,
            task=task.value,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream completion using Claude.

        Args:
            messages: Conversation history as list of LLMMessage.
            task: Task type for model routing.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.

        Yields:
            Content chunks as they arrive.
        """
        model = self.get_model_for_task(task)

        # Convert messages (simpler for streaming - no tools)
        system_msg = None
        api_messages: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        # Log request start
        logger.info(
            "llm_request_start",
            provider="claude",
            model=model,
            task=task.value,
            message_count=len(messages),
        )

        try:
            async with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens
                if max_tokens is not None
                else self.config.default_max_tokens,
                temperature=temperature
                if temperature is not None
                else self.config.default_temperature,
                system=system_msg,  # type: ignore[arg-type]
                messages=api_messages,  # type: ignore[arg-type]
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except (
            anthropic.RateLimitError,
            anthropic.AuthenticationError,
            anthropic.BadRequestError,
            anthropic.APIConnectionError,
        ) as e:
            logger.error(
                "llm_request_failed",
                provider="claude",
                model=model,
                task=task.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise _classify_claude_error(e) from e

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "claude-3-5-sonnet-20241022").
        """
        return self.model_routing.get(task.value, DEFAULT_CLAUDE_MODEL)
