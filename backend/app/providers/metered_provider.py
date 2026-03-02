"""Metered provider wrappers.

REQ-020 §6.2, §6.5: Proxy providers that record token usage
after successful LLM/embedding calls and debit user balances.
REQ-022 §8.3: MeteredLLMProvider resolves routing from DB via
AdminConfigService and passes model_override to inner adapter.
"""

import logging
import uuid
from collections.abc import AsyncGenerator

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult
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
    REQ-022 §8.3: Resolves task routing from DB via AdminConfigService,
    passing model_override to the inner adapter.

    Args:
        inner: The actual LLM provider to delegate to.
        metering_service: Service for recording usage and debiting balance.
        admin_config: Service for resolving task-to-model routing from DB.
        user_id: User who made the API call.
    """

    def __init__(
        self,
        inner: LLMProvider,
        metering_service: MeteringService,
        admin_config: AdminConfigService,
        user_id: uuid.UUID,
    ) -> None:
        # Don't call super().__init__() — no ProviderConfig needed.
        # The inner provider already has its config.
        self._inner = inner
        self._metering_service = metering_service
        self._admin_config = admin_config
        self._user_id = user_id

    @property
    def provider_name(self) -> str:
        """Return inner provider's name."""
        return self._inner.provider_name

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
        """Call inner provider, then record usage and debit balance.

        REQ-020 §6.2: Delegates to inner, records usage on success.
        REQ-020 §6.6: If recording fails, logs error but returns response.
        REQ-022 §8.3: Resolves routing from DB via AdminConfigService.
        The caller's model_override is ignored — routing is always resolved
        from the task_routing_config table. If no routing exists, the inner
        adapter falls back to its hardcoded routing table.

        Args:
            messages: Conversation history.
            task: Task type for model routing.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
            stop_sequences: Stop sequences.
            tools: Tool definitions.
            json_mode: JSON output mode.
            _model_override: Ignored — routing is resolved from DB.
                Kept in signature for LLMProvider interface compatibility.

        Returns:
            LLMResponse from the inner provider.

        Raises:
            ProviderError: If the inner provider fails (no usage recorded).
        """
        # REQ-022 §8.3: Resolve routing from DB, ignoring caller's override.
        # Fail-closed: DB errors propagate and block the request.
        resolved_model = await self._admin_config.get_model_for_task(
            self._inner.provider_name, task.value
        )
        response = await self._inner.complete(
            messages,
            task,
            max_tokens=max_tokens,
            temperature=temperature,
            stop_sequences=stop_sequences,
            tools=tools,
            json_mode=json_mode,
            model_override=resolved_model,
        )
        try:
            await self._metering_service.record_and_debit(
                user_id=self._user_id,
                provider=self._inner.provider_name,
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
        """Stream from inner provider without metering.

        REQ-020 §6.2: Streaming metering is deferred — stream() is not
        used in production. Passes through to inner provider unchanged.

        WARNING: stream() does NOT apply DB routing (REQ-022 §8.3).
        If stream() is used in production, routing must be added here.

        Args:
            messages: Conversation history.
            task: Task type for model routing.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.

        Yields:
            Text chunks from the inner provider's stream.
        """
        async for chunk in self._inner.stream(
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
