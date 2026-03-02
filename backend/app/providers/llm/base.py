"""Abstract base class and types for LLM providers.

REQ-009 §4.1: LLMProvider abstract interface with TaskType enum,
message types, tool calling support, and JSON mode.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


class TaskType(Enum):
    """Task types for model routing.

    WHY ENUM: Explicit task types prevent typos and enable IDE autocomplete.
    The routing table (§4.3) maps these to specific models.
    """

    CHAT_RESPONSE = "chat_response"
    ONBOARDING_INTERVIEW = "onboarding"
    SKILL_EXTRACTION = "skill_extraction"
    EXTRACTION = "extraction"
    GHOST_DETECTION = "ghost_detection"
    SCORE_RATIONALE = "score_rationale"
    COVER_LETTER = "cover_letter"
    RESUME_TAILORING = "resume_tailoring"
    STORY_SELECTION = "story_selection"
    RESUME_PARSING = "resume_parsing"


@dataclass
class ToolParameter:
    """A parameter for a tool definition.

    Attributes:
            name: Parameter name (e.g., "job_id").
            param_type: JSON Schema type ("string", "number", "boolean", "array", "object").
            description: Human-readable description of the parameter.
            required: Whether the parameter is required (default True).
            enum: Optional list of allowed values for constrained strings.
    """

    name: str
    param_type: str
    description: str
    required: bool = True
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    """Definition of a tool the LLM can call.

    WHY EXPLICIT SCHEMA:
    - Enables IDE autocomplete for tool parameters
    - Provider adapters convert this to native format (OpenAI functions, Anthropic tools)
    - Single source of truth for tool capabilities

    Maps to:
    - OpenAI: `tools[].function` schema
    - Anthropic: `tools[]` schema
    - Gemini: `tools[].function_declarations`

    Attributes:
            name: Tool name (e.g., "favorite_job").
            description: What the tool does.
            parameters: List of input parameters.
    """

    name: str
    description: str
    parameters: list[ToolParameter]

    def to_json_schema(self) -> dict:
        """Convert to JSON Schema format (used by OpenAI and Anthropic).

        Returns:
                JSON Schema dict with type, properties, and required fields.
        """
        properties: dict[str, dict] = {}
        required: list[str] = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.param_type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }


@dataclass
class ToolCall:
    """A tool call requested by the LLM.

    WHY SEPARATE FROM TOOL RESULT:
    - Tool calls come FROM the LLM (in response)
    - Tool results go TO the LLM (in next message)
    - Different data flows, different structures

    Attributes:
            id: Unique ID for this call (provider-generated).
            name: Tool name (e.g., "favorite_job").
            arguments: Parsed arguments (already JSON-decoded).
    """

    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """Result of executing a tool, sent back to the LLM.

    Attributes:
            tool_call_id: Must match the ToolCall.id.
            content: Result as string (JSON-encode if structured).
            is_error: True if tool execution failed.
    """

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMMessage:
    """Provider-agnostic message format.

    WHY CUSTOM CLASS: Decouples from provider-specific message formats.
    Anthropic uses {"role": "user", "content": [{"type": "text", ...}]}
    OpenAI uses {"role": "user", "content": "..."}
    This normalizes both.

    Attributes:
            role: Message role ("system", "user", "assistant", "tool").
            content: Text content (None if only tool calls).
            tool_calls: For assistant messages requesting tool use.
            tool_result: For tool role messages with results.
    """

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_result: ToolResult | None = None


@dataclass
class LLMResponse:
    """Provider-agnostic response format.

    Attributes:
            content: Text response (None if only tool calls).
            model: Actual model used (for logging).
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
            finish_reason: Why generation stopped ("stop", "max_tokens", "tool_use").
            latency_ms: Response time in milliseconds.
            tool_calls: Tool calls requested by LLM (if any).
    """

    content: str | None
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    latency_ms: float
    tool_calls: list[ToolCall] | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    WHY ABSTRACT CLASS:
    - Enforces consistent interface across providers
    - Enables type checking and IDE support
    - Makes testing via mock implementations trivial
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize with provider configuration.

        Args:
                config: Provider configuration including API keys and defaults.
        """
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g., 'claude', 'openai', 'gemini').

        REQ-020 §6.2: Used by MeteredLLMProvider to record which provider
        handled a call for pricing lookup and usage tracking.
        """
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        json_mode: bool = False,
        model_override: str | None = None,
    ) -> LLMResponse:
        """Generate a completion (non-streaming).

        Args:
                messages: Conversation history as list of LLMMessage.
                task: Task type for model routing.
                max_tokens: Override default max tokens.
                temperature: Override default temperature.
                stop_sequences: Custom stop sequences.
                tools: Available tools the LLM can call (native function calling).
                json_mode: If True, enforce JSON output format.
                model_override: If provided, use this model instead of routing table.
                        REQ-022 §8.2: Passed by MeteredLLMProvider after DB routing lookup.

        Returns:
                LLMResponse with content and/or tool_calls.

        Raises:
                ProviderError: On API failure after retries.
                RateLimitError: If rate limited and no retry budget.

        Tool Calling Flow:
                1. Pass tools=[...] to enable tool calling
                2. If LLM wants to call a tool, response.tool_calls is populated
                3. Execute the tool(s) and create ToolResult objects
                4. Add assistant message (with tool_calls) and tool messages (with results)
                5. Call complete() again to get final response

        JSON Mode:
                When json_mode=True:
                - OpenAI: Sets response_format={"type": "json_object"}
                - Anthropic: Adds "Respond only with valid JSON" to system prompt
                - Gemini: Sets response_mime_type="application/json"

                WHY NOT ALWAYS JSON: Most tasks need natural language. JSON mode
                adds overhead and can cause issues if the model wants to explain
                something. Only use for structured extraction tasks.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming completion.

        WHY SEPARATE METHOD: Streaming has fundamentally different
        return type (iterator vs single response). Combining them
        into one method with a flag creates awkward typing.

        Args:
                messages: Conversation history as list of LLMMessage.
                task: Task type for model routing.
                max_tokens: Override default max tokens.
                temperature: Override default temperature.

        Yields:
                Content chunks as they arrive.

        Note:
                Token counts not available until stream completes.
                Use complete() if you need token counts immediately.
        """
        # Bare yield makes mypy treat this as an async generator body,
        # which is required for abstract async generator methods.
        yield ""  # pragma: no cover

    @abstractmethod
    def get_model_for_task(self, task: TaskType) -> str:
        """Return the model identifier for a given task.

        WHY EXPOSED: Allows callers to log which model will be used
        before making the call. Useful for debugging and cost tracking.

        Args:
                task: The task type to get the model for.

        Returns:
                Model identifier string (e.g., "claude-3-5-sonnet-20241022").
        """
        ...
