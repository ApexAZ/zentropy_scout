"""Metered provider wrappers.

REQ-030 §5.4: MeteredLLMProvider.complete() uses reserve→call→settle
pattern — pre-debit reservation before LLM call, settlement after.
REQ-030 §5.6: stream() logs warning about unmetered streaming.
REQ-030 §5.7: MeteredEmbeddingProvider.embed() uses reserve→embed→settle
pattern with token estimation heuristic.
REQ-030 §5.8: Both providers call persist_response_metadata() after
successful LLM/embed call but before settle() — outbox pattern for
settlement retry by background sweep.
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
from app.services.billing.metering_service import MeteringService

logger = logging.getLogger(__name__)

_RELEASE_FAILED_LOG = "Release also failed for user %s — hold orphaned until sweep"
_SETTLE_FAILED_LOG = (
    "Unexpected settlement error for user %s — %s returned, hold orphaned until sweep"
)
_PERSIST_FAILED_LOG = (
    "persist_response_metadata failed for user %s — "
    "settlement will proceed without outbox data"
)


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
        credits_enabled: If True, stream() is fail-closed (AF-09).
    """

    def __init__(
        self,
        inner: LLMProvider,
        registry: dict[str, LLMProvider] | None,
        metering_service: MeteringService,
        admin_config: AdminConfigService,
        user_id: uuid.UUID,
        *,
        credits_enabled: bool = True,
    ) -> None:
        # Don't call super().__init__() — no ProviderConfig needed.
        # The inner provider already has its config.
        self._inner = inner
        self._registry = registry or {}
        self._metering_service = metering_service
        self._admin_config = admin_config
        self._user_id = user_id
        self._credits_enabled = credits_enabled

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
        """Dispatch to the correct provider using reserve→call→settle.

        REQ-030 §5.4: Reserves estimated cost before the LLM call,
        settles with actual cost after success, or releases the hold
        on failure. Eliminates the post-debit fire-and-forget pattern.

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
            NoPricingConfigError: If no routing/pricing exists.
            UnregisteredModelError: If routed model not in registry.
        """
        # 1. Resolve cross-provider routing from DB
        routing = await self._admin_config.get_routing_for_task(task.value)
        adapter, model_override = self._resolve_adapter(routing)

        # 2. Reserve estimated cost (fail-closed: no reservation = no LLM call)
        reservation = await self._metering_service.reserve(
            user_id=self._user_id,
            task_type=task.value,
            max_tokens=max_tokens,
        )

        # 3. Make the LLM call (release hold on any adapter failure)
        try:
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
        except Exception:
            try:
                await self._metering_service.release(reservation)
            except Exception:
                logger.exception(_RELEASE_FAILED_LOG, self._user_id)
            raise

        # 4. Persist response metadata (outbox pattern — REQ-030 §5.8).
        # Best-effort: failure must not block settle() or response return.
        try:
            await self._metering_service.persist_response_metadata(
                reservation=reservation,
                model=response.model,
                input_tokens=max(0, response.input_tokens),
                output_tokens=max(0, response.output_tokens),
            )
        except Exception:
            logger.exception(_PERSIST_FAILED_LOG, self._user_id)

        # 5. Settle with actual cost. settle() catches expected errors
        # (SQLAlchemyError, pricing errors) internally. Unexpected errors
        # (AF-07: programming bugs) propagate — catch them here so the
        # LLM response is still returned to the user.
        try:
            await self._metering_service.settle(
                reservation=reservation,
                provider=adapter.provider_name,
                model=response.model,
                input_tokens=max(0, response.input_tokens),
                output_tokens=max(0, response.output_tokens),
            )
        except Exception:
            logger.exception(_SETTLE_FAILED_LOG, self._user_id, "response")

        return response

    async def stream(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream from the correct provider based on DB routing.

        AF-09: Fail-closed when credits are enabled — stream metering is
        not implemented, so allowing streaming would bypass billing.
        REQ-030 §5.6: When credits are disabled, logs a warning and
        passes through to the inner provider.

        Args:
            messages: Conversation history.
            task: Task type for model routing.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.

        Yields:
            Text chunks from the dispatched provider's stream.

        Raises:
            ProviderError: If credits_enabled is True (unmetered streaming
                would bypass billing).
        """
        if self._credits_enabled:
            raise ProviderError(
                "Streaming is not supported while credits are enabled. "
                "Use complete() instead."
            )

        logger.warning(
            "stream() called with metering enabled but stream metering is not "
            "implemented — usage will not be recorded for user %s",
            self._user_id,
        )
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

    REQ-030 §5.7: Wraps a real EmbeddingProvider, delegates all calls,
    and uses reserve→embed→settle pattern for usage recording.
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
        """Reserve estimated cost, call inner provider, settle with actuals.

        REQ-030 §5.7: Uses reserve→embed→settle pattern. Estimates input
        tokens as sum(len(text))/4 for the reservation. After the call,
        settles with actual total_tokens (or the estimate for chunked batches
        where total_tokens is -1).

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult from the inner provider.

        Raises:
            ProviderError: If the inner provider fails (hold released).
            NoPricingConfigError: If no pricing exists for embedding model.
            UnregisteredModelError: If embedding model not in registry.
        """
        # 1. Estimate input tokens for reservation (REQ-020 §6.5 heuristic)
        estimated_tokens = sum(len(text) for text in texts) // 4

        # 2. Reserve estimated cost (fail-closed: no reservation = no embed call)
        # AF-13: Input tokens go to max_input_tokens; embeddings produce zero
        # output tokens so max_tokens=0 (avoids inflated output cost component).
        reservation = await self._metering_service.reserve(
            user_id=self._user_id,
            task_type="embedding",
            max_input_tokens=estimated_tokens,
            max_tokens=0,
        )

        # 3. Execute embedding call (release hold on any failure)
        try:
            result = await self._inner.embed(texts)
        except Exception:
            try:
                await self._metering_service.release(reservation)
            except Exception:
                logger.exception(_RELEASE_FAILED_LOG, self._user_id)
            raise

        # 4. Resolve actual token count (use estimate for chunked batches)
        input_tokens = result.total_tokens
        if input_tokens < 0:
            input_tokens = estimated_tokens
            logger.warning(
                "Estimated %d embedding tokens for chunked batch "
                "(provider returned %d)",
                input_tokens,
                result.total_tokens,
            )

        # 5. Persist response metadata (outbox pattern — REQ-030 §5.8).
        # Best-effort: failure must not block settle() or result return.
        try:
            await self._metering_service.persist_response_metadata(
                reservation=reservation,
                model=result.model,
                input_tokens=max(0, input_tokens),
                output_tokens=0,
            )
        except Exception:
            logger.exception(_PERSIST_FAILED_LOG, self._user_id)

        # 6. Settle with actual cost. settle() catches expected errors
        # internally. Unexpected errors (AF-07) propagate — catch here
        # so the embedding result is still returned.
        try:
            await self._metering_service.settle(
                reservation=reservation,
                provider=self._inner.provider_name,
                model=result.model,
                input_tokens=max(0, input_tokens),
                output_tokens=0,
            )
        except Exception:
            logger.exception(_SETTLE_FAILED_LOG, self._user_id, "result")

        return result

    @property
    def dimensions(self) -> int:
        """Return inner provider's embedding dimensions."""
        return self._inner.dimensions
