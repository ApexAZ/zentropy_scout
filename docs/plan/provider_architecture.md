# Provider Abstraction — Layer Architecture

**Date:** 2026-01-26
**Reference:** REQ-009 §3 Architecture
**Status:** Phase 1.2 Documentation

---

## Overview

The Provider Abstraction Layer sits between the Application Layer (agents) and the external LLM/embedding APIs. It provides a unified interface that allows agents to work with any supported provider without code changes.

---

## Layer Diagram

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

---

## Layer Responsibilities

### Application Layer

The agents that implement business logic. They call the Provider Abstraction Layer without knowing which underlying provider is being used.

| Agent | Primary LLM Use | Embedding Use |
|-------|----------------|---------------|
| Chat Agent | Conversational responses, intent routing | None |
| Scouter Agent | Job extraction, skill parsing | Job posting embeddings |
| Strategist Agent | Scoring explanations, stretch analysis | Persona/job similarity |
| Ghostwriter Agent | Content generation (resumes, cover letters) | None |

### Provider Abstraction Layer

The unified interface that all agents call. Contains:

| Component | Responsibility |
|-----------|----------------|
| `LLMProvider` | Abstract interface for chat completions |
| `EmbeddingProvider` | Abstract interface for text embeddings |
| `ProviderConfig` | Centralized configuration (keys, models, limits) |
| `ModelRouter` | Maps task types to specific models |

### Provider Adapters

Concrete implementations that wrap provider-specific SDKs:

| Adapter | SDK | Use Case |
|---------|-----|----------|
| `ClaudeAdapter` | Anthropic SDK / Claude Agent SDK | Primary LLM (local mode uses subscription) |
| `OpenAIAdapter` | OpenAI SDK | Embeddings (text-embedding-3-small) |
| `GeminiAdapter` | Google SDK | Future: alternative LLM |

---

## File Structure

```
backend/app/providers/
├── __init__.py              # Re-exports provider factories
├── config.py                # ProviderConfig class
├── factory.py               # Provider factory functions
├── errors.py                # Provider-specific exceptions
├── llm/
│   ├── __init__.py
│   ├── base.py              # LLMProvider ABC
│   ├── claude_adapter.py    # Claude/Anthropic implementation
│   ├── openai_adapter.py    # OpenAI implementation (future)
│   └── gemini_adapter.py    # Gemini implementation (future)
└── embedding/
    ├── __init__.py
    ├── base.py              # EmbeddingProvider ABC
    └── openai_adapter.py    # OpenAI embeddings
```

---

## Data Flow Examples

### LLM Completion Flow

```
Agent
  │
  │ llm.complete(prompt, task_type="extraction")
  ▼
LLMProvider.complete()
  │
  │ model = router.get_model(task_type)
  ▼
ClaudeAdapter._call_api(prompt, model)
  │
  │ Anthropic SDK call
  ▼
Claude API Response
  │
  │ Parse, validate
  ▼
Structured Result → Agent
```

### Embedding Flow

```
Agent
  │
  │ embedding.embed_batch(texts)
  ▼
EmbeddingProvider.embed_batch()
  │
  │ Chunk into batches
  ▼
OpenAIAdapter._embed(chunk)
  │
  │ OpenAI SDK call
  ▼
OpenAI Embedding Response
  │
  │ Collect vectors
  ▼
List[Vector] → Agent → pgvector storage
```

---

## Key Design Decisions

### 1. Local Mode Uses Claude Agent SDK

For MVP, the Claude adapter wraps the Claude Agent SDK which uses the user's Claude subscription rather than direct API calls. This eliminates API costs for the user.

```python
# Local mode (MVP)
from claude_agent_sdk import query, ClaudeAgentOptions

# Hosted mode (future)
from anthropic import Anthropic
```

### 2. Embeddings Always Require API Key

There is no subscription-based embedding option. Even in local mode, embeddings require `OPENAI_API_KEY`. This is acceptable because embedding costs are minimal (~$0.02 per 1M tokens).

### 3. Provider Config is Centralized

All API keys, model routing, and retry policies live in a single `ProviderConfig` class that reads from environment variables. No provider-specific configuration scattered across the codebase.

### 4. Adapters Are Thin Wrappers

Adapters should not contain business logic. They translate between the abstract interface and the provider SDK, handle provider-specific error mapping, and implement retry logic.

---

## Interface Summary

### LLMProvider (ABC)

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        task_type: str = "general",
        output_schema: type[BaseModel] | None = None,
    ) -> CompletionResult: ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]: ...
```

### EmbeddingProvider (ABC)

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]: ...
```

---

## Next Steps

This document establishes the architecture. Implementation proceeds with:

1. **§3.2** - Key Components (detailed interface definitions)
2. **§6.1** - ProviderConfig Class
3. **§6.2** - Environment Variables
4. **§6.3** - Provider Factory
5. **§4.1** - LLM Abstract Interface implementation
6. ... (see implementation_plan.md for full sequence)

---

*Reference: REQ-009 Provider Abstraction Specification*
