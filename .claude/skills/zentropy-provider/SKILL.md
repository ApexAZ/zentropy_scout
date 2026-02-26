---
name: zentropy-provider
description: |
  LLM provider patterns for Zentropy Scout. Load this skill when:
  - Calling Claude, making LLM API calls, or getting completions
  - Using Claude Agent SDK or structured outputs
  - Extracting data from text using AI
  - Generating content (resumes, cover letters, summaries)
  - Working with embeddings or the provider abstraction layer
  - Someone asks about "LLM", "Claude", "API", "extract", "generate", or "completion"
---

# Zentropy Scout Provider Patterns

## Critical: Local Mode Uses Claude Agent SDK

**MVP uses Claude Agent SDK, NOT direct API calls.**

```bash
pip install claude-agent-sdk
```

## Basic Completion with Structured Output

```python
from claude_agent_sdk import query, ClaudeAgentOptions
from pydantic import BaseModel

class ExtractedSkills(BaseModel):
    required_skills: list[dict]
    preferred_skills: list[dict]
    culture_text: str

async def extract_skills(job_description: str) -> ExtractedSkills:
    """Extract skills from job posting using Claude Agent SDK."""
    options = ClaudeAgentOptions(
        system_prompt="You are a job posting analyzer. Extract skills accurately.",
        max_turns=1,
        output_format={
            "type": "json_schema",
            "schema": ExtractedSkills.model_json_schema()
        }
    )

    async for message in query(
        prompt=f"Extract skills from this job posting:\n\n{job_description}",
        options=options
    ):
        if message.type == "result" and message.structured_output:
            return ExtractedSkills.model_validate(message.structured_output)

    raise ExtractionError("Failed to extract skills")
```

## Key SDK Differences from API

| Aspect | Claude Agent SDK | Anthropic API |
|--------|------------------|---------------|
| Auth | User's Claude subscription | API key required |
| Response | Always streaming (`async for`) | Can be sync or stream |
| Structured output | `output_format` option | `response_format` parameter |
| Result location | `message.structured_output` | `response.content[0].text` |
| Tools | MCP-based | API tool schema |

## Provider Abstraction Interface

```python
from abc import ABC, abstractmethod
from typing import Optional, Type
from pydantic import BaseModel

class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        task: TaskType,
        output_schema: Optional[Type[BaseModel]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Unified completion interface."""
        pass

class ClaudeAgentSDKProvider(LLMProvider):
    """Local mode: uses Claude subscription via SDK."""

    async def complete(
        self,
        messages: list[dict],
        task: TaskType,
        output_schema: Optional[Type[BaseModel]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            max_turns=1,
        )

        if output_schema:
            options.output_format = {
                "type": "json_schema",
                "schema": output_schema.model_json_schema()
            }

        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)

        async for message in query(prompt=prompt, options=options):
            if message.type == "result":
                if output_schema and message.structured_output:
                    return LLMResponse(
                        content=output_schema.model_validate(message.structured_output)
                    )
                return LLMResponse(content=message.result)

        raise ProviderError("No result from SDK")
```

## Task-Based Model Routing

```python
from enum import Enum

class TaskType(Enum):
    EXTRACTION = "extraction"      # Quick extraction → Haiku
    SKILL_EXTRACTION = "skill_extraction"
    GENERATION = "generation"      # Creative writing → Sonnet
    ANALYSIS = "analysis"          # Complex reasoning → Sonnet
    SCORING = "scoring"            # Numerical analysis → Sonnet

# Model selection per task (local mode uses subscription default)
TASK_MODEL_MAP = {
    TaskType.EXTRACTION: "haiku",
    TaskType.SKILL_EXTRACTION: "haiku",
    TaskType.GENERATION: "sonnet",
    TaskType.ANALYSIS: "sonnet",
    TaskType.SCORING: "sonnet",
}
```

## Embeddings (Requires OpenAI Key)

Embeddings always require an API key, even in local mode:

```python
from openai import AsyncOpenAI

class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]
```

## Error Handling

```python
class ProviderError(Exception):
    """Base exception for provider errors."""
    pass

class ExtractionError(ProviderError):
    """Failed to extract structured data."""
    pass

class RateLimitError(ProviderError):
    """Hit rate limits."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
```

## SDK Documentation Links

- Overview: https://platform.claude.com/docs/en/agent-sdk/overview
- Python SDK: https://platform.claude.com/docs/en/agent-sdk/python
- Structured outputs: https://platform.claude.com/docs/en/agent-sdk/structured-outputs
- Custom tools (MCP): https://platform.claude.com/docs/en/agent-sdk/custom-tools
