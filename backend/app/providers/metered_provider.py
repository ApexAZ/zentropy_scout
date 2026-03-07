"""Metered provider wrappers.

REQ-020 §6.2, §6.5: Proxy providers that record token usage
after successful LLM/embedding calls and debit user balances.
REQ-028 §4: Cross-provider dispatch via registry — routes each
task to the correct provider+model based on DB routing table.
"""

import logging
import uuid
from collections.abc import AsyncGenerator

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult
from app.providers.errors import ProviderError
from app.providers.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    TaskType,
    ToolDefinition,
)
from app.services.admin_config_service import AdminConfigService
from app.services.metering_service import MeteringService

logger = logging.getLogger(__name__)


class MeteredLLMProvider(LLMProvider):
    """Proxy that records token usage and debits the user's balance.

    REQ-020 §6.2: Wraps a real LLMProvider, delegates all calls,
    and records usage after successful complete() calls.
    REQ-028 §4: Accepts a registry of providers and dispatches each
    task to the correct provider+model based on DB routing.

    Args:
        inner: The fallback LLM provider (used when no routing exists).
        registry: Dict mapping provider name to LLMProvider instance.
            Used for cross-provider dispatch. If None, only inner is used.
        metering_service: Service for recording usage and debiting balance.
        admin_config: Service for resolving task-to-model routing from DB.
        user_id: User who made the API call.
    """

    def __init__(
        self,
        inner: LLMProvider,
        registry: dict[str, LLMProvider] | None,
        metering_service: MeteringService,
        admin_config: AdminConfigService,
        user_id: uuid.UUID,
    ) -> None:
        # Don't call super().__init__() — no ProviderConfig needed.
        # The inner provider already has its config.
        self._inner = inner
        self._registry = registry or {}
        self._metering_service = metering_service
        self._admin_config = admin_config
        self._user_id = user_id

    @property
    def provider_name(self) -> str:
        """Return inner (fallback) provider's name."""
        return self._inner.provider_name

    def _resolve_adapter(
        self, routing: tuple[str, str] | None
    ) -> tuple[LLMProvider, str | None]:
        """Resolve which adapter to use and the model override.

        Args:
            routing: (provider, model) from DB, or None.

        Returns:
            (adapter, model_override) tuple.

        Raises:
            ProviderError: If routed provider is not in registry.
        """
        if routing is None:
            logger.warning(
                "No routing configured for task, falling back to %s",
                self._inner.provider_name,
            )
            return self._inner, None

        provider_name, model = routing
        adapter = self._registry.get(provider_name)
        if adapter is None:
            logger.error(
                "Provider '%s' not in registry — API key may be missing",
                provider_name,
            )
            raise ProviderError(
                "The requested service is not available. "
                "Please contact your administrator."
            )
        return adapter, model

    async def complete(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        json_mode: bool = False,
        _model_override: str | None = None,
    ) -> LLMResponse:
        """Dispatch to the correct provider, then record usage.

        REQ-028 §4.2: Resolves (provider, model) from DB routing table.
        Dispatches to the correct adapter from the registry.
        Falls back to inner provider when no routing is configured.

        Args:
            messages: Conversation history.
            task: Task type for model routing.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
            stop_sequences: Stop sequences.
            tools: Tool definitions.
            json_mode: JSON output mode.
            _model_override: Ignored — routing is resolved from DB.

        Returns:
            LLMResponse from the dispatched provider.

        Raises:
            ProviderError: If routed provider is not in registry.
        """
        # REQ-028 §4: Resolve cross-provider routing from DB.
        routing = await self._admin_config.get_routing_for_task(task.value)
        adapter, model_override = self._resolve_adapter(routing)

        response = await adapter.complete(
            messages,
            task,
            max_tokens=max_tokens,
            temperature=temperature,
            stop_sequences=stop_sequences,
            tools=tools,
            json_mode=json_mode,
            model_override=model_override,
        )
        try:
            await self._metering_service.record_and_debit(
                user_id=self._user_id,
                provider=adapter.provider_name,
                model=response.model,
                task_type=task.value,
                input_tokens=max(0, response.input_tokens),
                output_tokens=max(0, response.output_tokens),
            )
        except Exception:
            logger.exception(
                "Failed to record metered usage for user %s", self._user_id
            )
        return response

    async def stream(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream from the correct provider based on DB routing.

        REQ-028 §4.2: Applies cross-provider dispatch to streaming.
        Note: model_override is not supported for streaming — the adapter
        uses its default model for the task. The correct provider is
        selected, but DB-configured model is not applied.

        Args:
            messages: Conversation history.
            task: Task type for model routing.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.

        Yields:
            Text chunks from the dispatched provider's stream.
        """
        routing = await self._admin_config.get_routing_for_task(task.value)
        adapter, _model_override = self._resolve_adapter(routing)

        async for chunk in adapter.stream(
            messages, task, max_tokens=max_tokens, temperature=temperature
        ):
            yield chunk

    def get_model_for_task(self, task: TaskType) -> str:
        """Return inner provider's model for the given task."""
        return self._inner.get_model_for_task(task)


class MeteredEmbeddingProvider(EmbeddingProvider):
    """Proxy that records embedding usage and debits the user's balance.

    REQ-020 §6.5: Wraps a real EmbeddingProvider, delegates all calls,
    and records usage after successful embed() calls.
    REQ-022 §8.5: No routing change for embeddings — only pricing
    lookup migrated to DB via AdminConfigService in MeteringService.

    Args:
        inner: The actual embedding provider to delegate to.
        metering_service: Service for recording usage and debiting balance.
        _admin_config: Accepted for DI symmetry with MeteredLLMProvider.
            Pricing lookups happen via MeteringService internally.
        user_id: User who made the API call.
    """

    def __init__(
        self,
        inner: EmbeddingProvider,
        metering_service: MeteringService,
        _admin_config: AdminConfigService,
        user_id: uuid.UUID,
    ) -> None:
        # Don't call super().__init__() — no ProviderConfig needed.
        # _admin_config accepted for DI symmetry with MeteredLLMProvider
        # but not stored — pricing lookups happen via MeteringService.
        self._inner = inner
        self._metering_service = metering_service
        self._user_id = user_id

    @property
    def provider_name(self) -> str:
        """Return inner provider's name."""
        return self._inner.provider_name

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Call inner provider, then record usage and debit balance.

        REQ-020 §6.5: Records with task_type="embedding" and output_tokens=0.
        If total_tokens is -1 (chunked batch), estimates as sum(len(text))/4.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult from the inner provider.

        Raises:
            ProviderError: If the inner provider fails (no usage recorded).
        """
        result = await self._inner.embed(texts)
        try:
            input_tokens = result.total_tokens
            if input_tokens < 0:
                # Chunked batch — estimate tokens (REQ-020 §6.5)
                input_tokens = sum(len(text) for text in texts) // 4
                logger.warning(
                    "Estimated %d embedding tokens for chunked batch "
                    "(provider returned %d)",
                    input_tokens,
                    result.total_tokens,
                )
            await self._metering_service.record_and_debit(
                user_id=self._user_id,
                provider=self._inner.provider_name,
                model=result.model,
                task_type="embedding",
                input_tokens=input_tokens,
                output_tokens=0,
            )
        except Exception:
            logger.exception(
                "Failed to record metered embedding usage for user %s",
                self._user_id,
            )
        return result

    @property
    def dimensions(self) -> int:
        """Return inner provider's embedding dimensions."""
        return self._inner.dimensions
