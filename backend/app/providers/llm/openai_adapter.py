"""OpenAI GPT LLM adapter.

REQ-009 §4.2: Provider-specific adapter for OpenAI.

WHY SUPPORT OPENAI:
- Some users may prefer GPT for specific tasks
- BYOK scenarios where user has OpenAI credits
- Fallback option if Anthropic has outage (future)
"""

import contextlib
import json
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import openai
import structlog
from openai import AsyncOpenAI

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
# - High-volume extraction tasks use gpt-4o-mini (cheaper, faster)
# - Quality-critical tasks use gpt-4o (better reasoning)
DEFAULT_OPENAI_ROUTING: dict[str, str] = {
    # High-volume, simple extraction tasks → gpt-4o-mini (cheaper, faster)
    "skill_extraction": "gpt-4o-mini",
    "extraction": "gpt-4o-mini",
    "ghost_detection": "gpt-4o-mini",
    # Quality-critical tasks → gpt-4o (better reasoning)
    "chat_response": "gpt-4o",
    "onboarding": "gpt-4o",
    "score_rationale": "gpt-4o",
    "cover_letter": "gpt-4o",
    "resume_tailoring": "gpt-4o",
    "story_selection": "gpt-4o",
}

# Fallback if task type not in routing table
DEFAULT_OPENAI_MODEL = "gpt-4o"


def _classify_openai_error(error: Exception) -> ProviderError:
    """Map OpenAI SDK exceptions to internal error taxonomy.

    Returns a ProviderError subclass instance (does not raise).
    The caller is responsible for raising via ``raise _classify_openai_error(e) from e``.

    Handles: RateLimitError (with retry-after header extraction),
    AuthenticationError, BadRequestError (context_length / content_policy),
    and APIConnectionError.
    """
    if isinstance(error, openai.RateLimitError):
        retry_after = None
        if hasattr(error, "response") and error.response is not None:
            retry_header = error.response.headers.get("retry-after")
            if retry_header is not None:
                with contextlib.suppress(ValueError):
                    retry_after = float(retry_header)
        return RateLimitError(str(error), retry_after_seconds=retry_after)

    if isinstance(error, openai.AuthenticationError):
        return AuthenticationError(str(error))

    if isinstance(error, openai.BadRequestError):
        error_msg = str(error).lower()
        if "context_length" in error_msg:
            return ContextLengthError(str(error))
        if "content_policy" in error_msg:
            return ContentFilterError(str(error))
        return ProviderError(str(error))

    if isinstance(error, openai.APIConnectionError):
        return TransientError(str(error))

    return ProviderError(str(error))


def _convert_tool_result_message(msg: LLMMessage) -> dict[str, str]:
    """Convert a tool result LLMMessage to OpenAI tool-role dict.

    WHY: OpenAI uses a dedicated ``tool`` role with ``tool_call_id``.
    """
    return {
        "role": "tool",
        "tool_call_id": msg.tool_result.tool_call_id,
        "content": msg.tool_result.content,
    }


def _convert_tool_call_message(msg: LLMMessage) -> dict:
    """Convert an assistant LLMMessage with tool_calls to OpenAI format.

    WHY: Assistant messages containing tool calls must include the function
    call payload with JSON-encoded arguments.
    """
    return {
        "role": "assistant",
        "content": msg.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in msg.tool_calls
        ],
    }


def _convert_openai_messages(messages: list[LLMMessage]) -> list[dict]:
    """Convert LLMMessages to OpenAI chat-completions message format.

    OpenAI keeps system messages in the messages array (unlike Claude which
    separates them). Returns ``list[dict]`` — the API messages list.
    """
    api_messages: list[dict] = []
    for msg in messages:
        if msg.role == "tool":
            api_messages.append(_convert_tool_result_message(msg))
        elif msg.tool_calls:
            api_messages.append(_convert_tool_call_message(msg))
        else:
            api_messages.append({"role": msg.role, "content": msg.content})
    return api_messages


def _parse_openai_response(
    response: object,
) -> tuple[str | None, list[ToolCall] | None, str]:
    """Parse OpenAI chat-completion response.

    Extracts content, tool_calls, and finish_reason from the first choice.

    Returns:
        Tuple of (content, tool_calls, finish_reason).
    """
    choice = response.choices[0]

    tool_calls: list[ToolCall] | None = None
    if choice.message.tool_calls:
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments),
            )
            for tc in choice.message.tool_calls
        ]

    return choice.message.content, tool_calls, choice.finish_reason


class OpenAIAdapter(LLMProvider):
    """OpenAI GPT adapter using OpenAI SDK.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize OpenAI adapter.

        Args:
            config: Provider configuration with OpenAI API key.
        """
        super().__init__(config)
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        # Merge config routing on top of defaults (config overrides defaults)
        self.model_routing = {**DEFAULT_OPENAI_ROUTING}
        if config.openai_model_routing:
            self.model_routing.update(config.openai_model_routing)

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
        """Generate completion using OpenAI GPT.

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
        api_messages = _convert_openai_messages(messages)

        # Convert tools to OpenAI format
        api_tools = None
        if tools:
            api_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.to_json_schema(),
                    },
                }
                for tool in tools
            ]

        # WHY: OpenAI has native JSON mode via response_format
        response_format = None
        if json_mode:
            response_format = {"type": "json_object"}

        # Log request start
        logger.info(
            "llm_request_start",
            provider="openai",
            model=model,
            task=task.value,
            message_count=len(messages),
        )

        start_time = time.monotonic()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens
                if max_tokens is not None
                else self.config.default_max_tokens,
                temperature=temperature
                if temperature is not None
                else self.config.default_temperature,
                messages=api_messages,
                stop=stop_sequences,
                tools=api_tools,
                response_format=response_format,
            )
        except (
            openai.RateLimitError,
            openai.AuthenticationError,
            openai.BadRequestError,
            openai.APIConnectionError,
        ) as e:
            logger.error(
                "llm_request_failed",
                provider="openai",
                model=model,
                task=task.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise _classify_openai_error(e) from e

        latency_ms = (time.monotonic() - start_time) * 1000
        content, tool_calls, finish_reason = _parse_openai_response(response)

        # Log request complete
        logger.info(
            "llm_request_complete",
            provider="openai",
            model=model,
            task=task.value,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
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
    ) -> AsyncIterator[str]:
        """Stream completion using OpenAI GPT.

        Args:
            messages: Conversation history as list of LLMMessage.
            task: Task type for model routing.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.

        Yields:
            Content chunks as they arrive.
        """
        model = self.get_model_for_task(task)
        api_messages = _convert_openai_messages(messages)

        # Log request start
        logger.info(
            "llm_request_start",
            provider="openai",
            model=model,
            task=task.value,
            message_count=len(messages),
        )

        try:
            response = await self.client.chat.completions.create(
                model=model,
                max_tokens=max_tokens
                if max_tokens is not None
                else self.config.default_max_tokens,
                temperature=temperature
                if temperature is not None
                else self.config.default_temperature,
                messages=api_messages,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except (
            openai.RateLimitError,
            openai.AuthenticationError,
            openai.BadRequestError,
            openai.APIConnectionError,
        ) as e:
            logger.error(
                "llm_request_failed",
                provider="openai",
                model=model,
                task=task.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise _classify_openai_error(e) from e

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "gpt-4o").
        """
        return self.model_routing.get(task.value, DEFAULT_OPENAI_MODEL)
