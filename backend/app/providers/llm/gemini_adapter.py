"""Google Gemini LLM adapter.

REQ-009 §4.2: Provider-specific adapter for Gemini.

WHY SUPPORT GEMINI:
- Alternative for BYOK users with Google Cloud credits
- Competitive pricing for high-volume tasks
- Good multimodal capabilities (future)

Uses the unified google-genai SDK (successor to google-generativeai).
"""

import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import structlog
from google import genai
from google.genai import types

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
# - High-volume extraction tasks use Flash (cheaper, faster)
# - Quality-critical tasks use Pro (better reasoning)
# Fallback if task type not in routing table
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

DEFAULT_GEMINI_ROUTING: dict[str, str] = {
    # High-volume, simple extraction tasks → Flash (cheaper, faster)
    "skill_extraction": DEFAULT_GEMINI_MODEL,
    "extraction": DEFAULT_GEMINI_MODEL,
    "ghost_detection": DEFAULT_GEMINI_MODEL,
    # Quality-critical tasks → Pro (better reasoning)
    "chat_response": DEFAULT_GEMINI_MODEL,  # Flash is now recommended default
    "onboarding": DEFAULT_GEMINI_MODEL,
    "score_rationale": DEFAULT_GEMINI_MODEL,
    "cover_letter": DEFAULT_GEMINI_MODEL,
    "resume_tailoring": DEFAULT_GEMINI_MODEL,
    "story_selection": DEFAULT_GEMINI_MODEL,
    "resume_parsing": "gemini-2.5-flash",
}


def _classify_gemini_error(error: Exception) -> ProviderError:
    """Map Gemini exceptions to internal error taxonomy."""
    error_msg = str(error).lower()
    if "resource" in error_msg and "exhausted" in error_msg:
        return RateLimitError(str(error))
    if "permission" in error_msg or "unauthenticated" in error_msg:
        return AuthenticationError(str(error))
    if "context" in error_msg or "token" in error_msg:
        return ContextLengthError(str(error))
    if "safety" in error_msg or "blocked" in error_msg:
        return ContentFilterError(str(error))
    if "unavailable" in error_msg or "503" in error_msg:
        return TransientError(str(error))
    return ProviderError(str(error))


def _convert_gemini_messages(
    messages: list[LLMMessage],
) -> tuple[str | None, list[types.Content]]:
    """Convert LLMMessages to Gemini format, extracting system instruction."""
    system_instruction = None
    contents: list[types.Content] = []

    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content
        elif msg.role == "tool" and msg.tool_result:
            contents.append(_convert_tool_result(msg))
        elif msg.tool_calls:
            contents.append(_convert_tool_call_message(msg))
        else:
            role = "model" if msg.role == "assistant" else msg.role
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg.content or "")],
                )
            )

    return system_instruction, contents


def _convert_tool_result(msg: LLMMessage) -> types.Content:
    """Convert a tool result message to Gemini function_response format."""
    func_name = (
        msg.tool_result.tool_call_id.split("_")[-1]  # type: ignore[union-attr]
        if "_" in msg.tool_result.tool_call_id  # type: ignore[union-attr]
        else "function"
    )
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name=func_name,
                    response={"result": msg.tool_result.content},  # type: ignore[union-attr]
                )
            )
        ],
    )


def _convert_tool_call_message(msg: LLMMessage) -> types.Content:
    """Convert an assistant message with tool calls to Gemini format."""
    parts: list[types.Part] = []
    if msg.content:
        parts.append(types.Part(text=msg.content))
    for tc in msg.tool_calls:  # type: ignore[union-attr]
        parts.append(
            types.Part(
                function_call=types.FunctionCall(
                    name=tc.name,
                    args=tc.arguments,
                )
            )
        )
    return types.Content(role="model", parts=parts)


def _extract_parts(
    parts: list,
) -> tuple[str | None, list[ToolCall] | None]:
    """Extract content text and tool calls from Gemini response parts."""
    content = None
    tool_calls: list[ToolCall] | None = None
    for part in parts:
        if part.text:
            content = part.text
        elif part.function_call:
            if tool_calls is None:
                tool_calls = []
            fc = part.function_call
            tool_id = f"call_{fc.name}_{len(tool_calls)}"
            tool_calls.append(
                ToolCall(
                    id=tool_id,
                    name=fc.name,
                    arguments=dict(fc.args) if fc.args else {},
                )
            )
    return content, tool_calls


def _parse_gemini_response(
    response: object,
) -> tuple[str | None, list[ToolCall] | None, str]:
    """Parse Gemini response into content, tool_calls, and finish_reason."""
    content = None
    tool_calls: list[ToolCall] | None = None

    if response.candidates:  # type: ignore[attr-defined]
        candidate = response.candidates[0]  # type: ignore[attr-defined]
        if candidate.content and candidate.content.parts:
            content, tool_calls = _extract_parts(candidate.content.parts)
        finish_reason = (
            candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
        )
    else:
        finish_reason = "UNKNOWN"

    return content, tool_calls, finish_reason


class GeminiAdapter(LLMProvider):
    """Google Gemini adapter using unified google-genai SDK.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns
    """

    @property
    def provider_name(self) -> str:
        """Return 'gemini' for pricing lookup and usage tracking."""
        return "gemini"

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize Gemini adapter.

        Args:
            config: Provider configuration with Google API key.
        """
        super().__init__(config)
        self.client = genai.Client(api_key=config.google_api_key)
        self.model_routing = {**DEFAULT_GEMINI_ROUTING}
        if config.gemini_model_routing:
            self.model_routing.update(config.gemini_model_routing)

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
        """Generate completion using Gemini."""
        model_name = self.get_model_for_task(task)
        system_instruction, contents = _convert_gemini_messages(messages)

        # Convert tools to Gemini format
        gemini_tools = None
        if tools:
            function_declarations = [
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.to_json_schema(),  # type: ignore[arg-type]
                )
                for tool in tools
            ]
            gemini_tools = [types.Tool(function_declarations=function_declarations)]

        gen_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens or self.config.default_max_tokens,
            temperature=temperature or self.config.default_temperature,
            stop_sequences=stop_sequences or [],
            system_instruction=system_instruction,
            tools=gemini_tools,  # type: ignore[arg-type]
            response_mime_type="application/json" if json_mode else None,
        )

        logger.info(
            "llm_request_start",
            provider="gemini",
            model=model_name,
            task=task.value,
            message_count=len(messages),
        )

        start_time = time.monotonic()

        try:
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=contents,  # type: ignore[arg-type]
                config=gen_config,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "llm_request_failed",
                provider="gemini",
                model=model_name,
                task=task.value,
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=latency_ms,
            )
            raise _classify_gemini_error(e) from e

        latency_ms = (time.monotonic() - start_time) * 1000
        content, tool_calls, finish_reason = _parse_gemini_response(response)

        input_tokens = (
            response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        )
        output_tokens = (
            response.usage_metadata.candidates_token_count
            if response.usage_metadata
            else 0
        )

        logger.info(
            "llm_request_complete",
            provider="gemini",
            model=model_name,
            task=task.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

        return LLMResponse(
            content=content,
            model=model_name,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )

    async def stream(  # type: ignore[override]
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream completion using Gemini."""
        model_name = self.get_model_for_task(task)
        system_instruction, contents = _convert_gemini_messages(messages)

        gen_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens or self.config.default_max_tokens,
            temperature=temperature or self.config.default_temperature,
            system_instruction=system_instruction,
        )

        logger.info(
            "llm_request_start",
            provider="gemini",
            model=model_name,
            task=task.value,
            message_count=len(messages),
        )

        start_time = time.monotonic()

        try:
            async for chunk in self.client.aio.models.generate_content_stream(  # type: ignore[attr-defined]
                model=model_name,
                contents=contents,  # type: ignore[arg-type]
                config=gen_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "llm_request_failed",
                provider="gemini",
                model=model_name,
                task=task.value,
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=latency_ms,
            )
            raise _classify_gemini_error(e) from e

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "gemini-2.0-flash").
        """
        return self.model_routing.get(task.value, DEFAULT_GEMINI_MODEL)
