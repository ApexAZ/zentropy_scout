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
DEFAULT_GEMINI_ROUTING: dict[str, str] = {
    # High-volume, simple extraction tasks → Flash (cheaper, faster)
    "skill_extraction": "gemini-2.0-flash",
    "extraction": "gemini-2.0-flash",
    "ghost_detection": "gemini-2.0-flash",
    # Quality-critical tasks → Pro (better reasoning)
    "chat_response": "gemini-2.0-flash",  # Flash is now recommended default
    "onboarding": "gemini-2.0-flash",
    "score_rationale": "gemini-2.0-flash",
    "cover_letter": "gemini-2.0-flash",
    "resume_tailoring": "gemini-2.0-flash",
    "story_selection": "gemini-2.0-flash",
}

# Fallback if task type not in routing table
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


class GeminiAdapter(LLMProvider):
    """Google Gemini adapter using unified google-genai SDK.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize Gemini adapter.

        Args:
            config: Provider configuration with Google API key.
        """
        super().__init__(config)
        # Create client with API key
        self.client = genai.Client(api_key=config.google_api_key)
        # Merge config routing on top of defaults (config overrides defaults)
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
        """Generate completion using Gemini.

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
        model_name = self.get_model_for_task(task)

        # Extract system message and build contents
        system_instruction = None
        contents: list[types.Content] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "tool" and msg.tool_result:
                # WHY: Gemini uses function_response format
                func_name = (
                    msg.tool_result.tool_call_id.split("_")[-1]
                    if "_" in msg.tool_result.tool_call_id
                    else "function"
                )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=func_name,
                                    response={"result": msg.tool_result.content},
                                )
                            )
                        ],
                    )
                )
            elif msg.tool_calls:
                # WHY: Assistant message with function calls
                parts: list[types.Part] = []
                if msg.content:
                    parts.append(types.Part(text=msg.content))
                for tc in msg.tool_calls:
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=tc.name,
                                args=tc.arguments,
                            )
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
            else:
                # WHY: Gemini uses "model" instead of "assistant"
                role = "model" if msg.role == "assistant" else msg.role
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=msg.content or "")],
                    )
                )

        # Convert tools to Gemini format
        gemini_tools = None
        if tools:
            function_declarations = [
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.to_json_schema(),
                )
                for tool in tools
            ]
            gemini_tools = [types.Tool(function_declarations=function_declarations)]

        # Build generation config
        gen_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens or self.config.default_max_tokens,
            temperature=temperature or self.config.default_temperature,
            stop_sequences=stop_sequences or [],
            system_instruction=system_instruction,
            tools=gemini_tools,
            # WHY: Gemini has native JSON mode via response_mime_type
            response_mime_type="application/json" if json_mode else None,
        )

        # Log request start
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
                contents=contents,
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
            # Map errors to our error taxonomy
            error_msg = str(e).lower()
            if "resource" in error_msg and "exhausted" in error_msg:
                raise RateLimitError(str(e)) from e
            if "permission" in error_msg or "unauthenticated" in error_msg:
                raise AuthenticationError(str(e)) from e
            if "context" in error_msg or "token" in error_msg:
                raise ContextLengthError(str(e)) from e
            if "safety" in error_msg or "blocked" in error_msg:
                raise ContentFilterError(str(e)) from e
            if "unavailable" in error_msg or "503" in error_msg:
                raise TransientError(str(e)) from e
            raise ProviderError(str(e)) from e

        latency_ms = (time.monotonic() - start_time) * 1000

        # Parse response content and function calls
        content = None
        tool_calls = None

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        content = part.text
                    elif part.function_call:
                        if tool_calls is None:
                            tool_calls = []
                        fc = part.function_call
                        # Generate a unique ID for the tool call
                        tool_id = f"call_{fc.name}_{len(tool_calls)}"
                        tool_calls.append(
                            ToolCall(
                                id=tool_id,
                                name=fc.name,
                                arguments=dict(fc.args) if fc.args else {},
                            )
                        )

            finish_reason = (
                candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
            )
        else:
            finish_reason = "UNKNOWN"

        # Get token counts for logging
        input_tokens = (
            response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        )
        output_tokens = (
            response.usage_metadata.candidates_token_count
            if response.usage_metadata
            else 0
        )

        # Log request complete
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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
        """Stream completion using Gemini.

        Args:
            messages: Conversation history as list of LLMMessage.
            task: Task type for model routing.
            max_tokens: Override default max tokens.
            temperature: Override default temperature.

        Yields:
            Content chunks as they arrive.
        """
        model_name = self.get_model_for_task(task)

        # Extract system message and convert messages
        system_instruction = None
        contents: list[types.Content] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "model" if msg.role == "assistant" else msg.role
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=msg.content or "")],
                    )
                )

        # Build generation config
        gen_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens or self.config.default_max_tokens,
            temperature=temperature or self.config.default_temperature,
            system_instruction=system_instruction,
        )

        # Log request start
        logger.info(
            "llm_request_start",
            provider="gemini",
            model=model_name,
            task=task.value,
            message_count=len(messages),
        )

        start_time = time.monotonic()

        try:
            async for chunk in self.client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
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
            # Map errors to our error taxonomy
            error_msg = str(e).lower()
            if "resource" in error_msg and "exhausted" in error_msg:
                raise RateLimitError(str(e)) from e
            if "permission" in error_msg or "unauthenticated" in error_msg:
                raise AuthenticationError(str(e)) from e
            if "context" in error_msg or "token" in error_msg:
                raise ContextLengthError(str(e)) from e
            if "safety" in error_msg or "blocked" in error_msg:
                raise ContentFilterError(str(e)) from e
            if "unavailable" in error_msg or "503" in error_msg:
                raise TransientError(str(e)) from e
            raise ProviderError(str(e)) from e

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "gemini-2.0-flash").
        """
        return self.model_routing.get(task.value, DEFAULT_GEMINI_MODEL)
