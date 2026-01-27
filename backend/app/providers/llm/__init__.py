"""LLM provider module.

REQ-009 §4: LLM provider interface and adapters.
"""

from app.providers.llm.base import (
    CompletionResult,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    TaskType,
    ToolCall,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from app.providers.llm.claude_adapter import ClaudeAdapter
from app.providers.llm.gemini_adapter import GeminiAdapter
from app.providers.llm.mock_adapter import MockLLMProvider
from app.providers.llm.openai_adapter import OpenAIAdapter

__all__ = [
    # Base types
    "CompletionResult",
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "TaskType",
    "ToolCall",
    "ToolDefinition",
    "ToolParameter",
    "ToolResult",
    # Adapters
    "ClaudeAdapter",
    "GeminiAdapter",
    "MockLLMProvider",
    "OpenAIAdapter",
]
