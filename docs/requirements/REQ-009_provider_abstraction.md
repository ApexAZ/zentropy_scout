# REQ-009: Provider Abstraction Layer

**Status:** Implemented
**Version:** 0.2
**PRD Reference:** §6 Technical Architecture
**Last Updated:** 2026-02-27

---

## 1. Overview

This document specifies the abstraction layer that decouples Zentropy Scout's business logic from specific LLM and embedding provider implementations.

### 1.1 Problem Statement

Without abstraction, the codebase becomes tightly coupled to specific providers:

```python
# BAD: Provider-specific code scattered throughout
from anthropic import Anthropic
client = Anthropic()
response = client.messages.create(model="claude-3-sonnet-20240229", ...)

# Later, in another file...
from openai import OpenAI
client = OpenAI()
embedding = client.embeddings.create(model="text-embedding-3-small", ...)
```

**Problems this creates:**
1. **Vendor lock-in** — Switching providers requires touching dozens of files
2. **Testing difficulty** — Can't easily mock LLM calls
3. **Inconsistent error handling** — Each call site handles errors differently
4. **No centralized configuration** — Model names, API keys scattered
5. **BYOK complexity** — Supporting user-provided API keys becomes a nightmare

### 1.2 Solution: Provider Abstraction

A unified interface that all agents and services use:

```python
# GOOD: Business logic uses abstraction
from zentropy.providers import get_llm_provider, get_embedding_provider

llm = get_llm_provider()  # Returns configured provider
response = await llm.complete(
    task="cover_letter",  # Routing hint
    messages=[...],
    stream=True
)

embedder = get_embedding_provider()
vectors = await embedder.embed(["text1", "text2"])
```

### 1.3 Goals

| Goal | Description | Priority |
|------|-------------|----------|
| **Provider agnostic** | Switch Claude ↔ OpenAI ↔ Gemini without code changes | P0 |
| **Task-based routing** | Different models for different tasks (Haiku for extraction, Sonnet for writing) | P0 |
| **BYOK ready** | Users can provide their own API keys (future hosted version) | P1 |
| **Testable** | Easy to mock for unit tests | P0 |
| **Observable** | Centralized logging, cost tracking, latency metrics | P1 |
| **Resilient** | Automatic retries, fallbacks on failure | P1 |

### 1.4 Non-Goals (Explicit Exclusions)

| Non-Goal | Rationale |
|----------|-----------|
| **Multi-provider per request** | No "try Claude, fall back to OpenAI" — adds complexity, inconsistent outputs |
| **Fine-tuned model support** | MVP uses base models only |
| **Self-hosted models** | Ollama/vLLM support deferred to v2 |
| **Prompt caching** | Provider-specific feature; add later if needed |

### 1.5 Dual-Mode Architecture: Local vs Hosted

Zentropy Scout supports two operating modes with different LLM access patterns:

| Mode | Auth | LLM Interface | Embeddings | Use Case |
|------|------|---------------|------------|----------|
| **Local (MVP)** | User's Claude subscription | Claude Agent SDK | OpenAI API (key required) | Personal use on user's machine |
| **Hosted (Future)** | BYOK — user provides API keys | Anthropic/OpenAI APIs | OpenAI API (user's key) | Multi-tenant hosted service |

**WHY TWO MODES:**
- Local mode leverages the user's existing Claude Pro/Max subscription — no separate API key for LLM
- Hosted mode requires API keys because Anthropic does not permit third-party apps to use Claude.ai subscriptions

#### 1.5.1 Local Mode: Claude Agent SDK

The Claude Agent SDK (`claude-agent-sdk` package) wraps Claude Code and provides:
- Streaming completions via `query()`
- Built-in tools (Read, Write, Bash, Glob)
- Structured output via `output_format` option
- Custom tools via MCP integration

```python
# Local mode uses Claude Agent SDK
from claude_agent_sdk import query, ClaudeAgentOptions
from pydantic import BaseModel

class ExtractedSkills(BaseModel):
    skills: list[dict]
    culture_text: str

async def extract_skills_local(job_description: str) -> ExtractedSkills:
    """Extract skills using Claude Agent SDK (local mode)."""
    options = ClaudeAgentOptions(
        system_prompt="You are a job posting analyzer.",
        max_turns=1,
        output_format={
            "type": "json_schema",
            "schema": ExtractedSkills.model_json_schema()
        }
    )

    async for message in query(
        prompt=f"Extract skills and culture text from:\n\n{job_description}",
        options=options
    ):
        if message.type == "result" and message.structured_output:
            return ExtractedSkills.model_validate(message.structured_output)
```

**Key differences from API:**
- No API key needed (uses Claude subscription)
- Always streaming (`async for message in query()`)
- Structured output via `output_format` option, returned in `message.structured_output`
- Tools defined via MCP, not API tool schema

**Documentation:** https://platform.claude.com/docs/en/agent-sdk/overview

#### 1.5.2 Hosted Mode: Direct API

For hosted/multi-tenant deployment, use the standard Anthropic Python SDK:

```python
# Hosted mode uses Anthropic API
from anthropic import AsyncAnthropic

async def extract_skills_hosted(job_description: str, api_key: str) -> ExtractedSkills:
    """Extract skills using Anthropic API (hosted mode with BYOK)."""
    client = AsyncAnthropic(api_key=api_key)

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system="You are a job posting analyzer.",
        messages=[{
            "role": "user",
            "content": f"Extract skills and culture text from:\n\n{job_description}"
        }]
    )
    # Parse JSON from response.content[0].text
```

#### 1.5.3 Provider Abstraction Must Handle Both

The `LLMProvider` interface (§4.1) must abstract over both modes:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        task: TaskType,
        output_schema: Optional[Type[BaseModel]] = None,  # For structured output
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
    ) -> LLMResponse:
        """
        Unified interface for both modes.

        Local mode: Translates to claude_agent_sdk.query()
        Hosted mode: Translates to anthropic.messages.create()
        """
        pass

# Factory returns appropriate implementation
def get_llm_provider() -> LLMProvider:
    if settings.PROVIDER_MODE == "local":
        return ClaudeAgentSDKProvider()  # Uses claude-agent-sdk
    else:
        return AnthropicAPIProvider(api_key=settings.ANTHROPIC_API_KEY)
```

**Implementation priority:**
1. **MVP:** Implement `ClaudeAgentSDKProvider` only
2. **Future:** Add `AnthropicAPIProvider` and `OpenAIAPIProvider` for BYOK

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-007 Agent Behavior v0.3 | Consumer | Agents use this abstraction |
| REQ-008 Scoring Algorithm v0.1 | Consumer | Embedding generation |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| REQ-007 | Model routing | §11.2 references this for model selection |
| (Future) Billing | Cost tracking | Per-user token usage |

---

## 3. Architecture

### 3.1 Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐   │
│  │   Chat   │  │ Scouter  │  │ Strategist│  │  Ghostwriter │   │
│  │  Agent   │  │  Agent   │  │   Agent   │  │    Agent     │   │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └──────┬───────┘   │
│       │             │              │               │            │
└───────┼─────────────┼──────────────┼───────────────┼────────────┘
        │             │              │               │
        ▼             ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Provider Abstraction Layer                    │
│  ┌────────────────────────────┐  ┌────────────────────────────┐ │
│  │       LLMProvider          │  │    EmbeddingProvider       │ │
│  │  • complete()              │  │  • embed()                 │ │
│  │  • stream()                │  │  • embed_batch()           │ │
│  │  • route_model()           │  │                            │ │
│  └─────────────┬──────────────┘  └─────────────┬──────────────┘ │
│                │                               │                 │
│  ┌─────────────┴───────────────────────────────┴──────────────┐ │
│  │                    ProviderConfig                          │ │
│  │  • api_keys, model_routing, retry_policy, rate_limits      │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
        │                               │
        ▼                               ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│  Claude Adapter   │  │  OpenAI Adapter   │  │  Gemini Adapter   │
│  (Anthropic SDK)  │  │   (OpenAI SDK)    │  │  (Google SDK)     │
└───────────────────┘  └───────────────────┘  └───────────────────┘
```

### 3.2 Key Components

| Component | Responsibility |
|-----------|----------------|
| `LLMProvider` | Abstract interface for chat completions |
| `EmbeddingProvider` | Abstract interface for text embeddings |
| `ProviderConfig` | Centralized configuration (keys, models, limits) |
| `*Adapter` | Provider-specific SDK wrappers |
| `ModelRouter` | Maps task types to specific models |

---

## 4. LLM Provider Interface

### 4.1 Abstract Interface

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional
from dataclasses import dataclass
from enum import Enum

class TaskType(Enum):
    """
    Task types for model routing.

    WHY ENUM: Explicit task types prevent typos and enable IDE autocomplete.
    The routing table (§4.3) maps these to specific models.
    """
    CHAT_RESPONSE = "chat_response"           # Conversational replies
    ONBOARDING_INTERVIEW = "onboarding"       # Persona gathering
    SKILL_EXTRACTION = "skill_extraction"     # Extract skills from job postings
    EXTRACTION = "extraction"                 # Generic extraction (keywords, metrics) — REQ-010 utility functions
    GHOST_DETECTION = "ghost_detection"       # Classify posting legitimacy
    SCORE_RATIONALE = "score_rationale"       # Explain job match scores
    COVER_LETTER = "cover_letter"             # Generate cover letters
    RESUME_TAILORING = "resume_tailoring"     # Tailor resume bullets
    STORY_SELECTION = "story_selection"       # Pick achievement stories


@dataclass
class ToolParameter:
    """
    A parameter for a tool definition.
    """
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None  # For constrained string values


@dataclass
class ToolDefinition:
    """
    Definition of a tool the LLM can call.

    WHY EXPLICIT SCHEMA:
    - Enables IDE autocomplete for tool parameters
    - Provider adapters convert this to native format (OpenAI functions, Anthropic tools)
    - Single source of truth for tool capabilities

    Maps to:
    - OpenAI: `tools[].function` schema
    - Anthropic: `tools[]` schema
    - Gemini: `tools[].function_declarations`
    """
    name: str                           # e.g., "favorite_job"
    description: str                    # What the tool does
    parameters: List[ToolParameter]     # Input parameters

    def to_json_schema(self) -> dict:
        """Convert to JSON Schema format (used by OpenAI and Anthropic)."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
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
    """
    A tool call requested by the LLM.

    WHY SEPARATE FROM TOOL RESULT:
    - Tool calls come FROM the LLM (in response)
    - Tool results go TO the LLM (in next message)
    - Different data flows, different structures
    """
    id: str                  # Unique ID for this call (provider-generated)
    name: str                # Tool name (e.g., "favorite_job")
    arguments: dict          # Parsed arguments (already JSON-decoded)


@dataclass
class ToolResult:
    """
    Result of executing a tool, sent back to the LLM.
    """
    tool_call_id: str        # Must match the ToolCall.id
    content: str             # Result as string (JSON-encode if structured)
    is_error: bool = False   # True if tool execution failed


@dataclass
class LLMMessage:
    """
    Provider-agnostic message format.

    WHY CUSTOM CLASS: Decouples from provider-specific message formats.
    Anthropic uses {"role": "user", "content": [{"type": "text", ...}]}
    OpenAI uses {"role": "user", "content": "..."}
    This normalizes both.
    """
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None

    # Tool-related fields
    tool_calls: Optional[List[ToolCall]] = None    # For assistant messages requesting tool use
    tool_result: Optional[ToolResult] = None       # For tool role messages with results

    # Future: images (for multimodal support)


@dataclass
class LLMResponse:
    """
    Provider-agnostic response format.
    """
    content: Optional[str]            # Text response (None if only tool calls)
    model: str                        # Actual model used (for logging)
    input_tokens: int
    output_tokens: int
    finish_reason: str                # "stop", "max_tokens", "tool_use"
    latency_ms: float
    tool_calls: Optional[List[ToolCall]] = None  # Tool calls requested by LLM


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    WHY ABSTRACT CLASS:
    - Enforces consistent interface across providers
    - Enables type checking and IDE support
    - Makes testing via mock implementations trivial
    """

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        task: TaskType,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[ToolDefinition]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Generate a completion (non-streaming).

        Args:
            messages: Conversation history
            task: Task type for model routing
            max_tokens: Override default max tokens
            temperature: Override default temperature
            stop_sequences: Custom stop sequences
            tools: Available tools the LLM can call (native function calling)
            json_mode: If True, enforce JSON output format

        Returns:
            LLMResponse with content and/or tool_calls

        Raises:
            ProviderError: On API failure after retries
            RateLimitError: If rate limited and no retry budget

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
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[LLMMessage],
        task: TaskType,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """
        Generate a streaming completion.

        WHY SEPARATE METHOD: Streaming has fundamentally different
        return type (iterator vs single response). Combining them
        into one method with a flag creates awkward typing.

        Yields:
            Content chunks as they arrive

        Note:
            Token counts not available until stream completes.
            Use complete() if you need token counts immediately.
        """
        pass

    @abstractmethod
    def get_model_for_task(self, task: TaskType) -> str:
        """
        Return the model identifier for a given task.

        WHY EXPOSED: Allows callers to log which model will be used
        before making the call. Useful for debugging and cost tracking.
        """
        pass
```

### 4.2 Provider-Specific Adapters

#### 4.2.1 Claude Adapter

```python
from anthropic import AsyncAnthropic

class ClaudeAdapter(LLMProvider):
    """
    Anthropic Claude implementation.

    WHY ANTHROPIC AS PRIMARY:
    - Best instruction-following for agentic tasks
    - Superior at maintaining persona (onboarding)
    - Strong at structured extraction
    - Competitive pricing with Haiku for high-volume tasks
    """

    def __init__(self, config: ProviderConfig):
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
        self.config = config
        self.model_routing = config.claude_model_routing

    async def complete(
        self,
        messages: List[LLMMessage],
        task: TaskType,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[ToolDefinition]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        model = self.get_model_for_task(task)

        # Convert to Anthropic format
        system_msg = None
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "tool":
                # Anthropic uses tool_result content blocks
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_result.tool_call_id,
                        "content": msg.tool_result.content,
                        "is_error": msg.tool_result.is_error,
                    }]
                })
            elif msg.tool_calls:
                # Assistant message with tool calls
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                api_messages.append({"role": "assistant", "content": content_blocks})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        # JSON mode: Anthropic doesn't have native JSON mode, so we modify system prompt
        if json_mode and system_msg:
            system_msg = system_msg + "\n\nIMPORTANT: Respond ONLY with valid JSON. No explanations, no markdown, just the JSON object."
        elif json_mode:
            system_msg = "Respond ONLY with valid JSON. No explanations, no markdown, just the JSON object."

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
            max_tokens=max_tokens or self.config.default_max_tokens,
            temperature=temperature if temperature is not None else self.config.default_temperature,
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
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

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
        messages: List[LLMMessage],
        task: TaskType,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        model = self.get_model_for_task(task)

        # Convert messages (same as above)
        system_msg = None
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens or self.config.default_max_tokens,
            temperature=temperature if temperature is not None else self.config.default_temperature,
            system=system_msg,
            messages=api_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def get_model_for_task(self, task: TaskType) -> str:
        return self.model_routing.get(task, self.config.default_claude_model)
```

#### 4.2.2 OpenAI Adapter

```python
from openai import AsyncOpenAI

class OpenAIAdapter(LLMProvider):
    """
    OpenAI GPT implementation.

    WHY SUPPORT OPENAI:
    - Some users may prefer GPT for specific tasks
    - BYOK scenarios where user has OpenAI credits
    - Fallback option if Anthropic has outage (future)
    """

    def __init__(self, config: ProviderConfig):
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self.config = config
        self.model_routing = config.openai_model_routing

    async def complete(
        self,
        messages: List[LLMMessage],
        task: TaskType,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        tools: Optional[List[ToolDefinition]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        model = self.get_model_for_task(task)

        # Convert to OpenAI format
        api_messages = []
        for msg in messages:
            if msg.role == "tool":
                # OpenAI uses tool role with tool_call_id
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_result.tool_call_id,
                    "content": msg.tool_result.content,
                })
            elif msg.tool_calls:
                # Assistant message with tool calls
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

        # JSON mode: OpenAI has native support
        response_format = None
        if json_mode:
            response_format = {"type": "json_object"}

        start_time = time.monotonic()

        response = await self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens or self.config.default_max_tokens,
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

    # stream() implementation similar...

    def get_model_for_task(self, task: TaskType) -> str:
        return self.model_routing.get(task, self.config.default_openai_model)
```

### 4.3 Model Routing Table

**WHY TASK-BASED ROUTING:**
Different tasks have different requirements:
- **Skill extraction**: High volume, simple task → Use cheap/fast model (Haiku)
- **Cover letter**: Quality critical, low volume → Use best model (Sonnet)
- **Chat**: Conversational nuance needed → Use good model (Sonnet)

This optimizes cost without sacrificing quality where it matters.

```python
# Default routing for Claude
CLAUDE_MODEL_ROUTING: Dict[TaskType, str] = {
    # High volume, simple tasks → Haiku (fast, cheap)
    TaskType.SKILL_EXTRACTION: "claude-3-haiku-20240307",
    TaskType.EXTRACTION: "claude-3-haiku-20240307",  # Generic extraction (keywords, metrics)
    TaskType.GHOST_DETECTION: "claude-3-haiku-20240307",

    # Quality-critical tasks → Sonnet (balanced)
    TaskType.CHAT_RESPONSE: "claude-3-5-sonnet-20241022",
    TaskType.ONBOARDING_INTERVIEW: "claude-3-5-sonnet-20241022",
    TaskType.SCORE_RATIONALE: "claude-3-5-sonnet-20241022",
    TaskType.COVER_LETTER: "claude-3-5-sonnet-20241022",
    TaskType.RESUME_TAILORING: "claude-3-5-sonnet-20241022",
    TaskType.STORY_SELECTION: "claude-3-5-sonnet-20241022",
}

# Default routing for OpenAI
OPENAI_MODEL_ROUTING: Dict[TaskType, str] = {
    # High volume → GPT-4o-mini
    TaskType.SKILL_EXTRACTION: "gpt-4o-mini",
    TaskType.EXTRACTION: "gpt-4o-mini",  # Generic extraction (keywords, metrics)
    TaskType.GHOST_DETECTION: "gpt-4o-mini",

    # Quality-critical → GPT-4o
    TaskType.CHAT_RESPONSE: "gpt-4o",
    TaskType.ONBOARDING_INTERVIEW: "gpt-4o",
    TaskType.SCORE_RATIONALE: "gpt-4o",
    TaskType.COVER_LETTER: "gpt-4o",
    TaskType.RESUME_TAILORING: "gpt-4o",
    TaskType.STORY_SELECTION: "gpt-4o",
}

# Default routing for Gemini
GEMINI_MODEL_ROUTING: Dict[TaskType, str] = {
    # High volume → Flash
    TaskType.SKILL_EXTRACTION: "gemini-1.5-flash",
    TaskType.EXTRACTION: "gemini-1.5-flash",  # Generic extraction (keywords, metrics)
    TaskType.GHOST_DETECTION: "gemini-1.5-flash",

    # Quality-critical → Pro
    TaskType.CHAT_RESPONSE: "gemini-1.5-pro",
    TaskType.ONBOARDING_INTERVIEW: "gemini-1.5-pro",
    TaskType.SCORE_RATIONALE: "gemini-1.5-pro",
    TaskType.COVER_LETTER: "gemini-1.5-pro",
    TaskType.RESUME_TAILORING: "gemini-1.5-pro",
    TaskType.STORY_SELECTION: "gemini-1.5-pro",
}
```

### 4.4 Cost Estimates by Task

| Task | Frequency | Model (Claude) | Est. Tokens | Cost/Call | Monthly (500 jobs) |
|------|-----------|----------------|-------------|-----------|-------------------|
| Skill Extraction | Per job | Haiku | ~800 | $0.0002 | $0.10 |
| Ghost Detection | Per job | Haiku | ~500 | $0.0001 | $0.05 |
| Score Rationale | Per job | Sonnet | ~400 | $0.003 | $1.50 |
| Cover Letter | Per application | Sonnet | ~1500 | $0.01 | $5.00* |
| Resume Tailoring | Per application | Sonnet | ~1200 | $0.008 | $4.00* |
| Chat Response | Per message | Sonnet | ~600 | $0.004 | $20.00** |

*Assuming 50 applications/month
**Assuming 100 messages/month

**Total estimated: ~$30/month for moderate usage**

### 4.5 Tool Calling Patterns

**WHY NATIVE TOOL CALLING:**
Native tool/function calling (vs. ReAct-style text parsing) provides:
- **Schema validation**: Provider enforces parameter types
- **Reliable parsing**: No regex to break on edge cases
- **Parallel calls**: LLM can request multiple tools at once
- **Better reasoning**: Models trained specifically for tool selection

#### 4.5.1 Defining Tools

```python
# Define tools available to the Chat Agent
CHAT_AGENT_TOOLS = [
    ToolDefinition(
        name="favorite_job",
        description="Mark a job posting as favorited by the user",
        parameters=[
            ToolParameter(name="job_posting_id", type="string", description="The UUID of the job posting"),
        ]
    ),
    ToolDefinition(
        name="update_persona_skill",
        description="Add or update a skill in the user's persona",
        parameters=[
            ToolParameter(name="skill_name", type="string", description="Name of the skill"),
            ToolParameter(name="skill_type", type="string", description="Type of skill", enum=["Hard", "Soft", "Tool"]),
            ToolParameter(name="proficiency_level", type="string", description="Proficiency level",
                         enum=["Learning", "Familiar", "Proficient", "Expert"]),
        ]
    ),
    ToolDefinition(
        name="search_jobs",
        description="Search for job postings matching criteria",
        parameters=[
            ToolParameter(name="query", type="string", description="Search query"),
            ToolParameter(name="min_fit_score", type="number", description="Minimum fit score (0-100)", required=False),
        ]
    ),
]
```

#### 4.5.2 Tool Calling Flow

```python
async def chat_with_tools(user_message: str, llm: LLMProvider):
    """
    Complete chat flow with tool calling.

    WHY LOOP: The LLM may request multiple rounds of tool calls
    before generating a final response. We loop until it stops
    requesting tools.
    """
    messages = [
        LLMMessage(role="system", content=CHAT_AGENT_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_message),
    ]

    max_tool_rounds = 5  # Prevent infinite loops

    for _ in range(max_tool_rounds):
        response = await llm.complete(
            messages=messages,
            task=TaskType.CHAT_RESPONSE,
            tools=CHAT_AGENT_TOOLS,
        )

        if not response.tool_calls:
            # No tool calls = final response
            return response.content

        # Add assistant message with tool calls to history
        messages.append(LLMMessage(
            role="assistant",
            content=response.content,
            tool_calls=response.tool_calls,
        ))

        # Execute each tool and add results
        for tool_call in response.tool_calls:
            result = await execute_tool(tool_call.name, tool_call.arguments)
            messages.append(LLMMessage(
                role="tool",
                tool_result=ToolResult(
                    tool_call_id=tool_call.id,
                    content=json.dumps(result),
                    is_error=False,
                ),
            ))

    raise MaxToolRoundsExceeded("LLM kept requesting tools")
```

#### 4.5.3 Tool Execution

```python
async def execute_tool(name: str, arguments: dict) -> dict:
    """
    Execute a tool by name and return the result.

    WHY SEPARATE FUNCTION: Keeps tool execution logic separate from
    LLM interaction. Tools are just API calls (see REQ-007 §4).
    """
    if name == "favorite_job":
        job_id = arguments["job_posting_id"]
        await api_client.post(f"/job-postings/{job_id}/favorite")
        return {"success": True, "message": f"Favorited job {job_id}"}

    elif name == "update_persona_skill":
        await api_client.post("/personas/{persona_id}/skills", json=arguments)
        return {"success": True, "message": f"Added skill {arguments['skill_name']}"}

    elif name == "search_jobs":
        results = await api_client.get("/job-postings", params=arguments)
        return {"jobs": results, "count": len(results)}

    else:
        return {"error": f"Unknown tool: {name}"}
```

### 4.6 JSON Mode Patterns

**WHY JSON MODE:**
Structured extraction tasks (skill parsing, score calculation) need reliable JSON output.
Without JSON mode, the LLM might add:
- Preamble: "Here's the JSON you requested:"
- Markdown: ` ```json ... ``` `
- Explanations after the JSON

JSON mode forces clean output that parses without preprocessing.

#### 4.6.1 When to Use JSON Mode

| Task | Use JSON Mode? | Rationale |
|------|----------------|-----------|
| Skill Extraction | ✅ Yes | Need structured array of skills |
| Ghost Detection | ✅ Yes | Need `{"ghost_score": 75, "reasons": [...]}` |
| Score Rationale | ❌ No | Natural language explanation |
| Cover Letter | ❌ No | Free-form text |
| Chat Response | ❌ No | Conversational, may include tool calls |

#### 4.6.2 JSON Mode Usage

```python
async def extract_skills(job_description: str, llm: LLMProvider) -> List[dict]:
    """
    Extract skills from a job description using JSON mode.
    """
    messages = [
        LLMMessage(role="system", content="""
            Extract skills from the job description.
            Return a JSON object with this schema:
            {
                "skills": [
                    {"name": "Python", "type": "Hard", "is_required": true},
                    {"name": "Communication", "type": "Soft", "is_required": false}
                ]
            }
        """),
        LLMMessage(role="user", content=job_description),
    ]

    response = await llm.complete(
        messages=messages,
        task=TaskType.SKILL_EXTRACTION,
        json_mode=True,  # Enforce JSON output
    )

    # Safe to parse - provider guaranteed valid JSON
    data = json.loads(response.content)
    return data["skills"]
```

#### 4.6.3 Provider-Specific Behavior

| Provider | JSON Mode Implementation | Notes |
|----------|-------------------------|-------|
| OpenAI | `response_format={"type": "json_object"}` | Native support, very reliable |
| Anthropic | System prompt modification | No native support; we append JSON instruction |
| Gemini | `response_mime_type="application/json"` | Native support |

**Anthropic Workaround:**
Since Anthropic doesn't have native JSON mode, we append to the system prompt:
```
IMPORTANT: Respond ONLY with valid JSON. No explanations, no markdown, just the JSON object.
```

This is ~95% reliable with Sonnet. For critical paths, add validation + retry.

---

## 5. Embedding Provider Interface

### 5.1 Abstract Interface

```python
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class EmbeddingResult:
    """
    Result of embedding operation.
    """
    vectors: List[List[float]]  # One vector per input text
    model: str
    dimensions: int
    total_tokens: int


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    WHY SEPARATE FROM LLM PROVIDER:
    - Different API patterns (batch-oriented vs conversational)
    - Different providers may be optimal (OpenAI embeddings are excellent)
    - Embeddings are stateless; LLM may need conversation context
    """

    @abstractmethod
    async def embed(self, texts: List[str]) -> EmbeddingResult:
        """
        Generate embeddings for a list of texts.

        WHY BATCH BY DEFAULT:
        - Embedding APIs are optimized for batch calls
        - Reduces round trips and latency
        - Single-text embedding is just batch of 1

        Args:
            texts: List of strings to embed

        Returns:
            EmbeddingResult with vectors in same order as input

        Raises:
            ProviderError: On API failure after retries
        """
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """
        Return the embedding dimensions.

        WHY PROPERTY: Database schema needs to know vector size
        at table creation time. This makes it queryable.
        """
        pass
```

### 5.2 OpenAI Embedding Adapter

```python
class OpenAIEmbeddingAdapter(EmbeddingProvider):
    """
    OpenAI embedding implementation.

    WHY OPENAI FOR EMBEDDINGS (even when using Claude for LLM):
    - text-embedding-3-small has excellent quality/cost ratio
    - Well-documented, stable API
    - Good batch support (up to 2048 texts)
    - Anthropic doesn't offer embeddings (as of early 2025)
    """

    def __init__(self, config: ProviderConfig):
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self.model = config.embedding_model  # e.g., "text-embedding-3-small"
        self._dimensions = config.embedding_dimensions  # e.g., 1536

    async def embed(self, texts: List[str]) -> EmbeddingResult:
        # OpenAI has a limit of 8191 tokens per text
        # and 2048 texts per batch

        if len(texts) > 2048:
            # Chunk into batches
            results = []
            for i in range(0, len(texts), 2048):
                batch = texts[i:i+2048]
                batch_result = await self._embed_batch(batch)
                results.extend(batch_result.vectors)
            return EmbeddingResult(
                vectors=results,
                model=self.model,
                dimensions=self._dimensions,
                total_tokens=-1  # Unknown for chunked
            )

        return await self._embed_batch(texts)

    async def _embed_batch(self, texts: List[str]) -> EmbeddingResult:
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        vectors = [item.embedding for item in response.data]

        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            dimensions=self._dimensions,
            total_tokens=response.usage.total_tokens,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions
```

### 5.3 Embedding Model Comparison

| Model | Dimensions | Cost/1M tokens | Quality | Recommendation |
|-------|------------|----------------|---------|----------------|
| text-embedding-3-small | 1536 | $0.02 | Good | **MVP choice** |
| text-embedding-3-large | 3072 | $0.13 | Better | Future upgrade |
| text-embedding-ada-002 | 1536 | $0.10 | Good | Legacy, avoid |
| Cohere embed-english-v3 | 1024 | $0.10 | Good | Alternative |

**Decision: text-embedding-3-small**

Rationale:
- 6.5x cheaper than ada-002 with similar quality
- 1536 dimensions is sufficient for skill/job matching
- Widely used, well-tested

---

## 6. Configuration Management

### 6.1 ProviderConfig Class

```python
@dataclass
class ProviderConfig:
    """
    Centralized provider configuration.

    WHY DATACLASS:
    - Immutable after creation (frozen=True in production)
    - Clear schema for what's configurable
    - Easy to serialize/deserialize from env vars or JSON
    """

    # Provider selection
    llm_provider: str = "claude"  # "claude", "openai", "gemini"
    embedding_provider: str = "openai"  # "openai", "cohere"

    # API keys (loaded from environment)
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Model routing (can override defaults)
    claude_model_routing: Optional[Dict[TaskType, str]] = None
    openai_model_routing: Optional[Dict[TaskType, str]] = None
    gemini_model_routing: Optional[Dict[TaskType, str]] = None

    # Embedding config
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Defaults
    default_max_tokens: int = 4096
    default_temperature: float = 0.7

    # Retry policy
    max_retries: int = 3
    retry_base_delay_ms: int = 1000
    retry_max_delay_ms: int = 30000

    # Rate limiting
    requests_per_minute: Optional[int] = None  # None = no limit
    tokens_per_minute: Optional[int] = None

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        """
        Load configuration from environment variables.

        WHY FROM_ENV METHOD:
        - Standard 12-factor app pattern
        - Easy to override in different environments
        - Secrets never in code
        """
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "claude"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
            default_max_tokens=int(os.getenv("DEFAULT_MAX_TOKENS", "4096")),
            default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.7")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        )
```

### 6.2 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `claude` | Which LLM provider to use |
| `EMBEDDING_PROVIDER` | No | `openai` | Which embedding provider to use |
| `ANTHROPIC_API_KEY` | If Claude | — | Anthropic API key |
| `OPENAI_API_KEY` | If OpenAI/embeddings | — | OpenAI API key |
| `GOOGLE_API_KEY` | If Gemini | — | Google AI API key |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | Embedding model identifier |
| `EMBEDDING_DIMENSIONS` | No | `1536` | Vector dimensions |
| `DEFAULT_MAX_TOKENS` | No | `4096` | Default max output tokens |
| `DEFAULT_TEMPERATURE` | No | `0.7` | Default sampling temperature |
| `LLM_MAX_RETRIES` | No | `3` | Max retry attempts |

### 6.3 Provider Factory

```python
_llm_provider: Optional[LLMProvider] = None
_embedding_provider: Optional[EmbeddingProvider] = None


def get_llm_provider(config: Optional[ProviderConfig] = None) -> LLMProvider:
    """
    Get or create the LLM provider singleton.

    WHY SINGLETON:
    - Reuses HTTP connections (performance)
    - Centralized rate limiting
    - Consistent configuration across app

    WHY OPTIONAL CONFIG:
    - First call sets the config (app startup)
    - Subsequent calls reuse (business logic)
    """
    global _llm_provider

    if _llm_provider is None:
        if config is None:
            config = ProviderConfig.from_env()

        if config.llm_provider == "claude":
            _llm_provider = ClaudeAdapter(config)
        elif config.llm_provider == "openai":
            _llm_provider = OpenAIAdapter(config)
        elif config.llm_provider == "gemini":
            _llm_provider = GeminiAdapter(config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")

    return _llm_provider


def get_embedding_provider(config: Optional[ProviderConfig] = None) -> EmbeddingProvider:
    """
    Get or create the embedding provider singleton.
    """
    global _embedding_provider

    if _embedding_provider is None:
        if config is None:
            config = ProviderConfig.from_env()

        if config.embedding_provider == "openai":
            _embedding_provider = OpenAIEmbeddingAdapter(config)
        elif config.embedding_provider == "cohere":
            _embedding_provider = CohereEmbeddingAdapter(config)
        else:
            raise ValueError(f"Unknown embedding provider: {config.embedding_provider}")

    return _embedding_provider


def reset_providers():
    """
    Reset provider singletons. Used in tests.
    """
    global _llm_provider, _embedding_provider
    _llm_provider = None
    _embedding_provider = None
```

---

## 7. Error Handling & Resilience

### 7.1 Error Taxonomy

```python
class ProviderError(Exception):
    """Base class for provider errors."""
    pass


class RateLimitError(ProviderError):
    """
    Rate limit exceeded.

    WHY SEPARATE CLASS:
    - Callers may want to handle differently (back off, queue)
    - Contains retry-after information
    """
    def __init__(self, message: str, retry_after_seconds: Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(ProviderError):
    """
    Invalid or expired API key.

    WHY SEPARATE: No point retrying — need user intervention.
    """
    pass


class ModelNotFoundError(ProviderError):
    """
    Requested model doesn't exist or isn't accessible.
    """
    pass


class ContentFilterError(ProviderError):
    """
    Content blocked by provider's safety filter.

    WHY SEPARATE: May need to modify prompt, not just retry.
    """
    pass


class ContextLengthError(ProviderError):
    """
    Input exceeded model's context window.

    WHY SEPARATE: Need to truncate/summarize, not retry.
    """
    pass


class TransientError(ProviderError):
    """
    Temporary failure (network, server overload).
    Safe to retry.
    """
    pass
```

### 7.2 Retry Strategy

```python
async def with_retries(
    func: Callable[[], Awaitable[T]],
    config: ProviderConfig,
    retryable_errors: tuple = (TransientError, RateLimitError),
) -> T:
    """
    Execute function with exponential backoff retry.

    WHY EXPONENTIAL BACKOFF:
    - Prevents thundering herd on recovery
    - Respects provider rate limits
    - Industry standard pattern

    WHY JITTER:
    - Prevents synchronized retries from multiple clients
    - Spreads load more evenly
    """
    last_error = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except retryable_errors as e:
            last_error = e

            if attempt == config.max_retries:
                break  # No more retries

            # Calculate delay with exponential backoff + jitter
            if isinstance(e, RateLimitError) and e.retry_after_seconds:
                delay = e.retry_after_seconds
            else:
                base_delay = config.retry_base_delay_ms * (2 ** attempt)
                jitter = random.uniform(0, base_delay * 0.1)
                delay = min(base_delay + jitter, config.retry_max_delay_ms) / 1000

            logger.warning(
                f"Provider error (attempt {attempt + 1}/{config.max_retries + 1}): {e}. "
                f"Retrying in {delay:.2f}s"
            )

            await asyncio.sleep(delay)

    raise last_error
```

### 7.3 Error Mapping

Each adapter must map provider-specific errors to our taxonomy:

```python
# In ClaudeAdapter
async def complete(self, ...):
    try:
        response = await self.client.messages.create(...)
        return self._to_response(response)
    except anthropic.RateLimitError as e:
        raise RateLimitError(str(e), retry_after_seconds=e.retry_after)
    except anthropic.AuthenticationError as e:
        raise AuthenticationError(str(e))
    except anthropic.BadRequestError as e:
        if "context_length" in str(e).lower():
            raise ContextLengthError(str(e))
        if "content_policy" in str(e).lower():
            raise ContentFilterError(str(e))
        raise ProviderError(str(e))
    except anthropic.APIError as e:
        raise TransientError(str(e))
```

---

## 8. Observability

### 8.1 Logging

```python
import structlog

logger = structlog.get_logger()

# In adapter methods
async def complete(self, messages, task, ...):
    model = self.get_model_for_task(task)

    logger.info(
        "llm_request_start",
        provider="claude",
        model=model,
        task=task.value,
        message_count=len(messages),
    )

    try:
        response = await self._call_api(...)

        logger.info(
            "llm_request_complete",
            provider="claude",
            model=model,
            task=task.value,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )

        return response

    except Exception as e:
        logger.error(
            "llm_request_failed",
            provider="claude",
            model=model,
            task=task.value,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
```

### 8.2 Metrics (Future)

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `llm_request_duration_seconds` | Histogram | provider, model, task | Latency tracking |
| `llm_request_total` | Counter | provider, model, task, status | Request volume |
| `llm_tokens_total` | Counter | provider, model, task, direction | Token usage |
| `llm_errors_total` | Counter | provider, model, task, error_type | Error rates |

### 8.3 Cost Tracking (Future)

```python
@dataclass
class UsageRecord:
    """
    Record of LLM/embedding usage for cost tracking.

    WHY TRACK:
    - Per-user billing in hosted version
    - Cost optimization insights
    - Anomaly detection (runaway agent)
    """
    user_id: str
    provider: str
    model: str
    task: str
    input_tokens: int
    output_tokens: int
    cost_usd: float  # Calculated from token prices
    timestamp: datetime
```

---

## 9. Testing Support

### 9.1 Mock Provider

```python
class MockLLMProvider(LLMProvider):
    """
    Mock provider for testing.

    WHY MOCK:
    - Unit tests shouldn't hit real APIs (cost, speed, flakiness)
    - Enables deterministic testing
    - Can simulate error conditions
    """

    def __init__(self, responses: Optional[Dict[TaskType, str]] = None):
        self.responses = responses or {}
        self.calls: List[Dict] = []  # Record calls for assertions

    async def complete(self, messages, task, **kwargs) -> LLMResponse:
        self.calls.append({
            "method": "complete",
            "messages": messages,
            "task": task,
            "kwargs": kwargs,
        })

        content = self.responses.get(task, f"Mock response for {task.value}")

        return LLMResponse(
            content=content,
            model="mock-model",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
            latency_ms=10,
        )

    async def stream(self, messages, task, **kwargs) -> AsyncIterator[str]:
        self.calls.append({
            "method": "stream",
            "messages": messages,
            "task": task,
            "kwargs": kwargs,
        })

        content = self.responses.get(task, f"Mock response for {task.value}")
        for word in content.split():
            yield word + " "

    def get_model_for_task(self, task: TaskType) -> str:
        return "mock-model"

    def assert_called_with_task(self, task: TaskType):
        """Test helper to verify task was called."""
        tasks_called = [c["task"] for c in self.calls]
        assert task in tasks_called, f"Expected {task}, got {tasks_called}"
```

### 9.2 Test Fixtures

```python
import pytest

@pytest.fixture
def mock_llm():
    """Fixture that provides mock LLM and resets after test."""
    mock = MockLLMProvider({
        TaskType.SKILL_EXTRACTION: '{"skills": ["Python", "SQL"]}',
        TaskType.COVER_LETTER: "Dear Hiring Manager...",
    })

    # Inject mock
    import zentropy.providers as providers
    providers._llm_provider = mock

    yield mock

    # Reset
    providers.reset_providers()


# Usage in tests
async def test_skill_extraction(mock_llm):
    from zentropy.agents.scouter import extract_skills

    skills = await extract_skills("Job description...")

    mock_llm.assert_called_with_task(TaskType.SKILL_EXTRACTION)
    assert "Python" in skills
```

---

## 10. BYOK Support (Future)

### 10.1 Design Overview

**WHY BYOK:**
- Reduces hosting costs (user pays their own API bills)
- Privacy-conscious users keep data with their preferred provider
- Enables power users to use their own fine-tuned models

### 10.2 Implementation Sketch

```python
class BYOKConfig:
    """
    User-provided API key configuration.
    Stored encrypted in database, decrypted at runtime.
    """
    user_id: str
    provider: str  # "claude", "openai", "gemini"
    encrypted_api_key: bytes
    model_overrides: Optional[Dict[str, str]]  # Task -> model
    created_at: datetime
    last_used_at: datetime


def get_llm_provider_for_user(user_id: str) -> LLMProvider:
    """
    Get LLM provider using user's API key if configured.

    WHY PER-USER:
    - Different users may have different providers
    - API keys must be isolated
    - Usage tracking per user
    """
    byok_config = get_byok_config(user_id)

    if byok_config:
        api_key = decrypt(byok_config.encrypted_api_key)
        config = ProviderConfig(
            llm_provider=byok_config.provider,
            anthropic_api_key=api_key if byok_config.provider == "claude" else None,
            openai_api_key=api_key if byok_config.provider == "openai" else None,
            # ... etc
        )
        return create_provider(config)

    # Fall back to system default
    return get_llm_provider()
```

### 10.3 Security Considerations

| Concern | Mitigation |
|---------|------------|
| Key storage | Encrypt at rest (AES-256-GCM) |
| Key in memory | Clear after use, don't log |
| Key validation | Verify key works before saving |
| Key rotation | Support updating without downtime |
| Abuse prevention | Rate limit even with BYOK |

---

## 11. Open Questions

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Support local models (Ollama)? | Deferred | Add in v2 if demand |
| 2 | Cross-provider fallback? | Deferred | Complexity vs. benefit |
| 3 | Prompt caching (Claude)? | TBD | Could reduce costs significantly |
| 4 | How to handle model deprecations? | TBD | Need migration strategy |

---

## 12. Design Decisions & Rationale

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Abstraction approach | Interface + adapters / Plugin system / Direct SDK | Interface + adapters | Simple, testable, sufficient for 3 providers |
| Primary LLM | Claude / OpenAI / Gemini | Claude | Best instruction-following, persona maintenance |
| Embedding provider | Same as LLM / Separate | Separate (OpenAI) | Anthropic doesn't offer embeddings; OpenAI's are excellent |
| Task routing | Single model / Per-task routing | Per-task routing | Optimizes cost without sacrificing quality |
| Singleton pattern | Per-request / Singleton / Scoped | Singleton | Connection reuse, simpler config |
| Error taxonomy | Provider errors / Generic / Custom hierarchy | Custom hierarchy | Enables smart handling at call sites |

---

## 13. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-25 | 0.1 | Initial draft. LLM and Embedding provider interfaces, Claude/OpenAI adapters, model routing tables, configuration management, error handling, testing support, BYOK design. |
| 2026-01-25 | 0.2 | **Critical additions for REQ-007 agent support:** (1) Added native tool calling support — `ToolDefinition`, `ToolCall`, `ToolResult` dataclasses, `tools` parameter in `complete()`, full tool call flow documentation (§4.5). (2) Added JSON mode — `json_mode` parameter for structured extraction tasks, provider-specific implementations (§4.6). (3) Updated `LLMMessage` to support `tool_calls` and `tool_result` fields. (4) Updated `LLMResponse` to include `tool_calls`. (5) Updated Claude and OpenAI adapter implementations to handle tools and JSON mode. |
