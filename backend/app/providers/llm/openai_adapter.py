"""OpenAI GPT LLM adapter.

REQ-009 §4.2: Provider-specific adapter for OpenAI.

WHY SUPPORT OPENAI:
- Some users may prefer GPT for specific tasks
- BYOK scenarios where user has OpenAI credits
- Fallback option if Anthropic has outage (future)
"""

import json
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

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


# Default model routing - used when no routing provided in config
DEFAULT_OPENAI_MODEL = "gpt-4o"


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
        self.model_routing = config.openai_model_routing or {}

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

        # Convert to OpenAI format
        api_messages = []

        for msg in messages:
            if msg.role == "tool":
                # WHY: OpenAI uses dedicated tool role with tool_call_id
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.tool_call_id,
                    "content": msg.tool_result.content,
                })
            elif msg.tool_calls:
                # WHY: Assistant message with tool calls needs function format
                api_messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                })
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

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
                    }
                }
                for tool in tools
            ]

        # WHY: OpenAI has native JSON mode via response_format
        response_format = None
        if json_mode:
            response_format = {"type": "json_object"}

        start_time = time.monotonic()

        response = await self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens if max_tokens is not None else self.config.default_max_tokens,
            temperature=temperature if temperature is not None else self.config.default_temperature,
            messages=api_messages,
            stop=stop_sequences,
            tools=api_tools,
            response_format=response_format,
        )

        latency_ms = (time.monotonic() - start_time) * 1000

        # Parse tool calls from response
        tool_calls = None
        choice = response.choices[0]

        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            content=choice.message.content,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            finish_reason=choice.finish_reason,
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

        # Convert messages (same as complete but simpler)
        api_messages = []
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        response = await self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens if max_tokens is not None else self.config.default_max_tokens,
            temperature=temperature if temperature is not None else self.config.default_temperature,
            messages=api_messages,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "gpt-4o").
        """
        return self.model_routing.get(task.value, DEFAULT_OPENAI_MODEL)
