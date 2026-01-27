"""Google Gemini LLM adapter.

REQ-009 §4.2: Provider-specific adapter for Gemini.

WHY SUPPORT GEMINI:
- Alternative for BYOK users with Google Cloud credits
- Competitive pricing for high-volume tasks
- Good multimodal capabilities (future)
"""

import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

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


# Default model routing table per REQ-009 §4.3
# WHY TASK-BASED ROUTING: Optimizes cost without sacrificing quality
# - High-volume extraction tasks use Flash (cheaper, faster)
# - Quality-critical tasks use Pro (better reasoning)
DEFAULT_GEMINI_ROUTING: dict[str, str] = {
    # High-volume, simple extraction tasks → Flash (cheaper, faster)
    "skill_extraction": "gemini-1.5-flash",
    "extraction": "gemini-1.5-flash",
    "ghost_detection": "gemini-1.5-flash",
    # Quality-critical tasks → Pro (better reasoning)
    "chat_response": "gemini-1.5-pro",
    "onboarding": "gemini-1.5-pro",
    "score_rationale": "gemini-1.5-pro",
    "cover_letter": "gemini-1.5-pro",
    "resume_tailoring": "gemini-1.5-pro",
    "story_selection": "gemini-1.5-pro",
}

# Fallback if task type not in routing table
DEFAULT_GEMINI_MODEL = "gemini-1.5-pro"


class GeminiAdapter(LLMProvider):
    """Google Gemini adapter using Google AI SDK.

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
        genai.configure(api_key=config.google_api_key)
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

        # Extract system message for system_instruction
        system_msg = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "tool":
                # WHY: Gemini uses function_response format
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "function_response": {
                                    "name": msg.tool_result.tool_call_id.split("_")[-1]
                                    if "_" in msg.tool_result.tool_call_id
                                    else "function",
                                    "response": {"result": msg.tool_result.content},
                                }
                            }
                        ],
                    }
                )
            elif msg.tool_calls:
                # WHY: Assistant message with function calls
                parts = []
                if msg.content:
                    parts.append({"text": msg.content})
                for tc in msg.tool_calls:
                    parts.append(
                        {
                            "function_call": {
                                "name": tc.name,
                                "args": tc.arguments,
                            }
                        }
                    )
                contents.append({"role": "model", "parts": parts})
            else:
                # WHY: Gemini uses "model" instead of "assistant"
                role = "model" if msg.role == "assistant" else msg.role
                contents.append(
                    {
                        "role": role,
                        "parts": [{"text": msg.content}],
                    }
                )

        # Convert tools to Gemini format
        gemini_tools = None
        if tools:
            function_declarations = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.to_json_schema(),
                }
                for tool in tools
            ]
            gemini_tools = [{"function_declarations": function_declarations}]

        # Build generation config
        generation_config = {
            "max_output_tokens": max_tokens
            if max_tokens is not None
            else self.config.default_max_tokens,
            "temperature": temperature
            if temperature is not None
            else self.config.default_temperature,
        }

        if stop_sequences:
            generation_config["stop_sequences"] = stop_sequences

        # WHY: Gemini has native JSON mode via response_mime_type
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        # Create model with system instruction and tools
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system_msg,
            tools=gemini_tools,
        )

        start_time = time.monotonic()

        try:
            response = await model.generate_content_async(
                contents,
                generation_config=generation_config,
            )
        except google_exceptions.ResourceExhausted as e:
            raise RateLimitError(str(e)) from e
        except google_exceptions.PermissionDenied as e:
            raise AuthenticationError(str(e)) from e
        except google_exceptions.Unauthenticated as e:
            raise AuthenticationError(str(e)) from e
        except google_exceptions.InvalidArgument as e:
            error_msg = str(e).lower()
            if "context" in error_msg:
                raise ContextLengthError(str(e)) from e
            if "safety" in error_msg:
                raise ContentFilterError(str(e)) from e
            raise ProviderError(str(e)) from e
        except google_exceptions.ServiceUnavailable as e:
            raise TransientError(str(e)) from e

        latency_ms = (time.monotonic() - start_time) * 1000

        # Parse response content and function calls
        content = None
        tool_calls = None

        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content = part.text
                elif hasattr(part, "function_call") and part.function_call:
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

        return LLMResponse(
            content=content,
            model=model_name,
            input_tokens=response.usage_metadata.prompt_token_count
            if response.usage_metadata
            else 0,
            output_tokens=response.usage_metadata.candidates_token_count
            if response.usage_metadata
            else 0,
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
        system_msg = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                role = "model" if msg.role == "assistant" else msg.role
                contents.append(
                    {
                        "role": role,
                        "parts": [{"text": msg.content}],
                    }
                )

        # Build generation config
        generation_config = {
            "max_output_tokens": max_tokens
            if max_tokens is not None
            else self.config.default_max_tokens,
            "temperature": temperature
            if temperature is not None
            else self.config.default_temperature,
        }

        # Create model with system instruction
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system_msg,
        )

        try:
            response = await model.generate_content_async(
                contents,
                generation_config=generation_config,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except google_exceptions.ResourceExhausted as e:
            raise RateLimitError(str(e)) from e
        except google_exceptions.PermissionDenied as e:
            raise AuthenticationError(str(e)) from e
        except google_exceptions.Unauthenticated as e:
            raise AuthenticationError(str(e)) from e
        except google_exceptions.InvalidArgument as e:
            error_msg = str(e).lower()
            if "context" in error_msg:
                raise ContextLengthError(str(e)) from e
            if "safety" in error_msg:
                raise ContentFilterError(str(e)) from e
            raise ProviderError(str(e)) from e
        except google_exceptions.ServiceUnavailable as e:
            raise TransientError(str(e)) from e

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "gemini-1.5-pro").
        """
        return self.model_routing.get(task.value, DEFAULT_GEMINI_MODEL)
