"""Claude/Anthropic LLM adapter.

REQ-009 §4.2: Provider-specific adapter for Claude.

WHY ANTHROPIC AS PRIMARY:
- Best instruction-following for agentic tasks
- Superior at maintaining persona (onboarding)
- Strong at structured extraction
- Competitive pricing with Haiku for high-volume tasks
"""

import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic

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
}

# Fallback if task type not in routing table
DEFAULT_CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


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

        # Convert to Anthropic format
        system_msg = None
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "tool":
                # WHY: Anthropic uses tool_result content blocks within user messages
                api_messages.append(
                    {
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
                )
            elif msg.tool_calls:
                # WHY: Assistant message with tool calls needs content blocks format
                content_blocks = []
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
                api_messages.append({"role": "assistant", "content": content_blocks})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

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

        start_time = time.monotonic()

        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens
            if max_tokens is not None
            else self.config.default_max_tokens,
            temperature=temperature
            if temperature is not None
            else self.config.default_temperature,
            system=system_msg,
            messages=api_messages,
            stop_sequences=stop_sequences,
            tools=api_tools,
        )

        latency_ms = (time.monotonic() - start_time) * 1000

        # Parse response content and tool calls
        content = None
        tool_calls = None

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

        return LLMResponse(
            content=content,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            finish_reason=response.stop_reason,
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

        # Convert messages (same as complete, but simpler - no tools in streaming)
        system_msg = None
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens
            if max_tokens is not None
            else self.config.default_max_tokens,
            temperature=temperature
            if temperature is not None
            else self.config.default_temperature,
            system=system_msg,
            messages=api_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def get_model_for_task(self, task: TaskType) -> str:
        """Get model for task using routing table.

        Args:
            task: The task type to get the model for.

        Returns:
            Model identifier string (e.g., "claude-3-5-sonnet-20241022").
        """
        return self.model_routing.get(task.value, DEFAULT_CLAUDE_MODEL)
