"""Provider configuration management.

REQ-009 §6.1: Centralized configuration for LLM and embedding providers.
"""

import os
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """Centralized provider configuration.

    WHY DATACLASS:
    - Immutable after creation (frozen=True in production)
    - Clear schema for what's configurable
    - Easy to serialize/deserialize from env vars or JSON

    Attributes:
        llm_provider: Which LLM provider to use ("claude", "openai", "gemini").
        embedding_provider: Which embedding provider to use ("openai", "cohere").
        anthropic_api_key: Anthropic API key (loaded from environment).
        openai_api_key: OpenAI API key (loaded from environment).
        google_api_key: Google AI API key (loaded from environment).
        claude_model_routing: Override model routing for Claude.
        openai_model_routing: Override model routing for OpenAI.
        gemini_model_routing: Override model routing for Gemini.
        embedding_model: Embedding model identifier.
        embedding_dimensions: Vector dimensions (must match pgvector columns).
        default_max_tokens: Default max output tokens.
        default_temperature: Default sampling temperature.
        max_retries: Max retry attempts for transient errors.
        retry_base_delay_ms: Base delay for exponential backoff.
        retry_max_delay_ms: Max delay cap for exponential backoff.
        requests_per_minute: Rate limit (None = no limit).
        tokens_per_minute: Token rate limit (None = no limit).
    """

    # Provider selection
    llm_provider: str = "claude"
    embedding_provider: str = "openai"

    # API keys (loaded from environment)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None

    # Model routing (can override defaults)
    claude_model_routing: dict[str, str] | None = None
    openai_model_routing: dict[str, str] | None = None
    gemini_model_routing: dict[str, str] | None = None

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
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        """Load configuration from environment variables.

        WHY FROM_ENV METHOD:
        - Standard 12-factor app pattern
        - Easy to override in different environments
        - Secrets never in code

        Returns:
            ProviderConfig instance with values from environment.
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
