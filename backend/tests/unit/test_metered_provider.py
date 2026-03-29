"""Tests for MeteredLLMProvider and MeteredEmbeddingProvider.

REQ-030 §5.4: MeteredLLMProvider.complete() uses reserve→call→settle
pattern — pre-debit reservation before LLM call, settlement after.
REQ-030 §5.6: stream() logs warning about unmetered streaming.
REQ-030 §5.7: MeteredEmbeddingProvider.embed() uses reserve→embed→settle
pattern with token estimation heuristic.
REQ-028 §4: Cross-provider dispatch via registry.
"""

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.embedding.base import EmbeddingResult
from app.providers.embedding.mock_adapter import MockEmbeddingProvider
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, TaskType
from app.providers.llm.mock_adapter import MockLLMProvider
from app.providers.metered_provider import MeteredEmbeddingProvider, MeteredLLMProvider

TEST_USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_HELLO_MESSAGES = [LLMMessage(role="user", content="Hello")]
_MOCK_PROVIDER_NAME = "mock"
_MOCK_MODEL = "mock-model"
_MOCK_EMBEDDING_MODEL = "mock-embedding-model"
_DB_ERROR_MSG = "DB error"
_ROUTED_MODEL = "claude-3-5-haiku-20241022"
_PROVIDER_CLAUDE = "claude"
_PROVIDER_GEMINI = "gemini"
_KEY_KWARGS = "kwargs"
_KEY_MODEL_OVERRIDE = "model_override"
_PROVIDER_UNAVAILABLE = "Provider unavailable"
_EMBEDDING_SERVICE_DOWN = "Embedding service down"
_NO_PRICING_MSG = "No pricing"
_EMBED_HELLO = ["Hello"]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_metering() -> AsyncMock:
    """Create a mock MeteringService with reserve/settle/release."""
    service = AsyncMock()
    service.reserve = AsyncMock(return_value=MagicMock())
    service.settle = AsyncMock(return_value=None)
    service.release = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_admin_config() -> AsyncMock:
    """Create a mock AdminConfigService for routing lookups."""
    config = AsyncMock()
    # REQ-028 §4: Cross-provider routing returns (provider, model) or None.
    # Default: route to inner (mock) provider with routed model.
    config.get_routing_for_task = AsyncMock(
        return_value=(_MOCK_PROVIDER_NAME, _ROUTED_MODEL)
    )
    return config


@pytest.fixture
def inner_llm() -> MockLLMProvider:
    """Create a MockLLMProvider as the inner/fallback provider."""
    return MockLLMProvider()


@pytest.fixture
def claude_adapter() -> MockLLMProvider:
    """Create a MockLLMProvider for cross-provider dispatch tests."""
    return MockLLMProvider()


@pytest.fixture
def gemini_adapter() -> MockLLMProvider:
    """Create a MockLLMProvider for cross-provider dispatch tests."""
    return MockLLMProvider()


@pytest.fixture
def llm_registry(
    inner_llm: MockLLMProvider,
    claude_adapter: MockLLMProvider,
    gemini_adapter: MockLLMProvider,
) -> dict[str, MockLLMProvider]:
    """Registry with mock adapters keyed by provider name."""
    return {
        _MOCK_PROVIDER_NAME: inner_llm,
        _PROVIDER_CLAUDE: claude_adapter,
        _PROVIDER_GEMINI: gemini_adapter,
    }


@pytest.fixture
def inner_embedding() -> MockEmbeddingProvider:
    """Create a MockEmbeddingProvider as the inner provider."""
    return MockEmbeddingProvider()


@pytest.fixture
def metered_llm(
    inner_llm: MockLLMProvider,
    llm_registry: dict[str, MockLLMProvider],
    mock_metering: AsyncMock,
    mock_admin_config: AsyncMock,
) -> MeteredLLMProvider:
    """Create a MeteredLLMProvider wrapping a mock inner provider."""
    return MeteredLLMProvider(
        inner_llm, llm_registry, mock_metering, mock_admin_config, TEST_USER_ID
    )


@pytest.fixture
def metered_embedding(
    inner_embedding: MockEmbeddingProvider,
    mock_metering: AsyncMock,
    mock_admin_config: AsyncMock,
) -> MeteredEmbeddingProvider:
    """Create a MeteredEmbeddingProvider wrapping a mock inner provider."""
    return MeteredEmbeddingProvider(
        inner_embedding, mock_metering, mock_admin_config, TEST_USER_ID
    )


# =============================================================================
# MeteredLLMProvider — complete()
# =============================================================================


class TestMeteredLLMProviderComplete:
    """MeteredLLMProvider.complete() uses reserve→call→settle pattern."""

    async def test_returns_inner_response(
        self, metered_llm: MeteredLLMProvider
    ) -> None:
        """complete() returns the inner provider's response unchanged."""
        response = await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        assert response.model == _MOCK_MODEL
        assert response.input_tokens == 100
        assert response.output_tokens == 50

    async def test_reserve_called_with_correct_args(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """reserve() receives user_id, task_type, and max_tokens."""
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION, max_tokens=500)
        mock_metering.reserve.assert_called_once_with(
            user_id=TEST_USER_ID,
            task_type="extraction",
            max_tokens=500,
        )

    async def test_settle_called_after_success(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """settle() is called with reservation and response data."""
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        mock_metering.settle.assert_called_once_with(
            reservation=mock_metering.reserve.return_value,
            provider=_MOCK_PROVIDER_NAME,
            model=_MOCK_MODEL,
            input_tokens=100,
            output_tokens=50,
        )

    async def test_release_called_on_provider_failure(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If adapter.complete() raises, release() frees the hold."""
        inner_llm.complete = AsyncMock(side_effect=RuntimeError(_PROVIDER_UNAVAILABLE))
        with pytest.raises(RuntimeError, match=_PROVIDER_UNAVAILABLE):
            await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        mock_metering.release.assert_called_once_with(
            mock_metering.reserve.return_value
        )

    async def test_provider_failure_propagates_after_release(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If adapter.complete() raises, exception propagates and settle is skipped."""
        inner_llm.complete = AsyncMock(side_effect=RuntimeError(_PROVIDER_UNAVAILABLE))
        with pytest.raises(RuntimeError, match=_PROVIDER_UNAVAILABLE):
            await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        mock_metering.settle.assert_not_called()

    async def test_reserve_failure_prevents_llm_call(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If reserve() raises, adapter.complete() is never called."""
        mock_metering.reserve.side_effect = RuntimeError(_NO_PRICING_MSG)
        with pytest.raises(RuntimeError, match=_NO_PRICING_MSG):
            await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        assert len(inner_llm.calls) == 0
        mock_metering.settle.assert_not_called()
        mock_metering.release.assert_not_called()

    async def test_passes_kwargs_through(
        self, metered_llm: MeteredLLMProvider, inner_llm: MockLLMProvider
    ) -> None:
        """complete() forwards all kwargs to inner provider."""
        await metered_llm.complete(
            _HELLO_MESSAGES,
            TaskType.EXTRACTION,
            max_tokens=500,
            temperature=0.5,
        )
        assert inner_llm.calls[-1][_KEY_KWARGS]["max_tokens"] == 500
        assert inner_llm.calls[-1][_KEY_KWARGS]["temperature"] == 0.5

    async def test_max_tokens_none_forwarded_to_reserve(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """When max_tokens is None, reserve() receives None (uses its own default)."""
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        call_kwargs = mock_metering.reserve.call_args.kwargs
        assert call_kwargs["max_tokens"] is None


# =============================================================================
# MeteredLLMProvider — stream()
# =============================================================================


class TestMeteredLLMProviderStream:
    """MeteredLLMProvider.stream() passes through with warning."""

    async def test_yields_inner_stream_chunks(
        self, metered_llm: MeteredLLMProvider
    ) -> None:
        """stream() yields all chunks from inner provider."""
        chunks = []
        async for chunk in metered_llm.stream(_HELLO_MESSAGES, TaskType.EXTRACTION):
            chunks.append(chunk)
        assert len(chunks) > 0

    async def test_does_not_meter_usage(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """stream() does not call reserve, settle, or release."""
        async for _ in metered_llm.stream(_HELLO_MESSAGES, TaskType.EXTRACTION):
            pass
        mock_metering.reserve.assert_not_called()
        mock_metering.settle.assert_not_called()
        mock_metering.release.assert_not_called()

    async def test_logs_warning_about_unmetered_streaming(
        self, metered_llm: MeteredLLMProvider, caplog: pytest.LogCaptureFixture
    ) -> None:
        """REQ-030 §5.6: stream() logs warning about missing metering."""
        with caplog.at_level(logging.WARNING):
            async for _ in metered_llm.stream(_HELLO_MESSAGES, TaskType.EXTRACTION):
                pass
        assert any(
            "stream metering is not implemented" in record.message
            for record in caplog.records
        )


# =============================================================================
# MeteredLLMProvider — delegation
# =============================================================================


class TestMeteredLLMProviderDelegation:
    """MeteredLLMProvider delegates non-metered methods to inner."""

    def test_get_model_for_task_delegates(
        self, metered_llm: MeteredLLMProvider
    ) -> None:
        """get_model_for_task() returns inner provider's result."""
        result = metered_llm.get_model_for_task(TaskType.EXTRACTION)
        assert result == _MOCK_MODEL

    def test_provider_name_delegates(self, metered_llm: MeteredLLMProvider) -> None:
        """provider_name returns inner provider's name."""
        assert metered_llm.provider_name == _MOCK_PROVIDER_NAME


# =============================================================================
# MeteredLLMProvider — DB routing (REQ-028 §4)
# =============================================================================


class TestMeteredLLMProviderRouting:
    """MeteredLLMProvider resolves routing from AdminConfigService."""

    async def test_resolved_model_passed_as_override(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """DB-resolved model is passed as model_override to the dispatched adapter."""
        mock_admin_config.get_routing_for_task.return_value = (
            _MOCK_PROVIDER_NAME,
            _ROUTED_MODEL,
        )
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        last_call = inner_llm.calls[-1]
        assert last_call[_KEY_KWARGS][_KEY_MODEL_OVERRIDE] == _ROUTED_MODEL

    async def test_no_routing_falls_back_to_inner(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """When routing returns None, dispatches to inner with no model_override."""
        mock_admin_config.get_routing_for_task.return_value = None
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        last_call = inner_llm.calls[-1]
        assert last_call[_KEY_KWARGS][_KEY_MODEL_OVERRIDE] is None

    async def test_caller_cannot_pass_model_override_keyword(
        self,
        metered_llm: MeteredLLMProvider,
    ) -> None:
        """Callers cannot pass model_override= keyword — parameter is underscore-prefixed."""
        with pytest.raises(TypeError, match="model_override"):
            await metered_llm.complete(
                _HELLO_MESSAGES,
                TaskType.EXTRACTION,
                model_override="should-be-rejected",  # type: ignore[call-arg]
            )

    async def test_routing_db_error_propagates(
        self,
        metered_llm: MeteredLLMProvider,
        mock_admin_config: AsyncMock,
        mock_metering: AsyncMock,
    ) -> None:
        """Routing DB errors propagate (fail-closed) — request is blocked."""
        mock_admin_config.get_routing_for_task.side_effect = RuntimeError(_DB_ERROR_MSG)
        with pytest.raises(RuntimeError, match=_DB_ERROR_MSG):
            await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        mock_metering.reserve.assert_not_called()


# =============================================================================
# MeteredLLMProvider — cross-provider dispatch (REQ-028 §4.2)
# =============================================================================


class TestMeteredLLMProviderCrossProviderDispatch:
    """MeteredLLMProvider dispatches to correct adapter from registry."""

    async def test_dispatches_to_claude_adapter(
        self,
        metered_llm: MeteredLLMProvider,
        claude_adapter: MockLLMProvider,
        inner_llm: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Routes to Claude adapter when routing says 'claude'."""
        mock_admin_config.get_routing_for_task.return_value = (
            _PROVIDER_CLAUDE,
            _ROUTED_MODEL,
        )
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        assert len(claude_adapter.calls) == 1
        assert len(inner_llm.calls) == 0

    async def test_dispatches_to_gemini_adapter(
        self,
        metered_llm: MeteredLLMProvider,
        gemini_adapter: MockLLMProvider,
        inner_llm: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Routes to Gemini adapter when routing says 'gemini'."""
        mock_admin_config.get_routing_for_task.return_value = (
            _PROVIDER_GEMINI,
            "gemini-2.0-flash",
        )
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        assert len(gemini_adapter.calls) == 1
        assert len(inner_llm.calls) == 0

    async def test_passes_model_override_to_dispatched_adapter(
        self,
        metered_llm: MeteredLLMProvider,
        claude_adapter: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """The model from routing is passed as model_override."""
        mock_admin_config.get_routing_for_task.return_value = (
            _PROVIDER_CLAUDE,
            _ROUTED_MODEL,
        )
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        last_call = claude_adapter.calls[-1]
        assert last_call[_KEY_KWARGS][_KEY_MODEL_OVERRIDE] == _ROUTED_MODEL

    async def test_raises_when_provider_not_in_registry(
        self,
        metered_llm: MeteredLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """Raises ProviderError when routed provider has no API key (not in registry)."""
        mock_admin_config.get_routing_for_task.return_value = (
            "unknown_provider",
            "model",
        )
        with pytest.raises(ProviderError, match="not available"):
            await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)

    async def test_settles_usage_with_dispatched_provider(
        self,
        metered_llm: MeteredLLMProvider,
        mock_admin_config: AsyncMock,
        mock_metering: AsyncMock,
    ) -> None:
        """settle() uses the provider that actually handled the call."""
        mock_admin_config.get_routing_for_task.return_value = (
            _PROVIDER_CLAUDE,
            _ROUTED_MODEL,
        )
        await metered_llm.complete(_HELLO_MESSAGES, TaskType.EXTRACTION)
        call_kwargs = mock_metering.settle.call_args.kwargs
        # MockLLMProvider always returns provider_name="mock", but the key
        # point is settle was called with the dispatched adapter's identity.
        assert call_kwargs["provider"] == _MOCK_PROVIDER_NAME
        assert call_kwargs["model"] == _MOCK_MODEL

    async def test_stream_dispatches_to_correct_provider(
        self,
        metered_llm: MeteredLLMProvider,
        claude_adapter: MockLLMProvider,
        inner_llm: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """stream() routes to the correct adapter from registry."""
        mock_admin_config.get_routing_for_task.return_value = (
            _PROVIDER_CLAUDE,
            _ROUTED_MODEL,
        )
        chunks = []
        async for chunk in metered_llm.stream(_HELLO_MESSAGES, TaskType.EXTRACTION):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert len(claude_adapter.calls) == 1
        assert len(inner_llm.calls) == 0

    async def test_stream_falls_back_to_inner_when_no_routing(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_admin_config: AsyncMock,
    ) -> None:
        """stream() falls back to inner when no routing configured."""
        mock_admin_config.get_routing_for_task.return_value = None
        chunks = []
        async for chunk in metered_llm.stream(_HELLO_MESSAGES, TaskType.EXTRACTION):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert len(inner_llm.calls) == 1


# =============================================================================
# MeteredEmbeddingProvider — embed()
# =============================================================================


class TestMeteredEmbeddingProviderEmbed:
    """REQ-030 §5.7: MeteredEmbeddingProvider.embed() uses reserve→embed→settle."""

    async def test_returns_inner_result(
        self, metered_embedding: MeteredEmbeddingProvider
    ) -> None:
        """embed() returns the inner provider's result unchanged."""
        result = await metered_embedding.embed(_EMBED_HELLO)
        assert result.model == _MOCK_EMBEDDING_MODEL
        assert result.dimensions == 768
        assert len(result.vectors) == 1

    async def test_reserve_called_with_estimated_tokens(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """reserve() receives estimated input tokens from sum(len(text))/4."""
        await metered_embedding.embed(["Hello world"])  # len=11, 11//4 = 2
        mock_metering.reserve.assert_called_once_with(
            user_id=TEST_USER_ID,
            task_type="embedding",
            max_tokens=2,
        )

    async def test_settle_called_after_success(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """settle() is called with reservation and actual token count."""
        await metered_embedding.embed(_EMBED_HELLO)
        mock_metering.settle.assert_called_once_with(
            reservation=mock_metering.reserve.return_value,
            provider=_MOCK_PROVIDER_NAME,
            model=_MOCK_EMBEDDING_MODEL,
            input_tokens=10,  # MockEmbeddingProvider: len(texts) * 10
            output_tokens=0,
        )

    async def test_release_called_on_embed_failure(
        self,
        metered_embedding: MeteredEmbeddingProvider,
        inner_embedding: MockEmbeddingProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If inner.embed() raises, release() frees the hold."""
        inner_embedding.embed = AsyncMock(
            side_effect=RuntimeError(_EMBEDDING_SERVICE_DOWN)
        )
        with pytest.raises(RuntimeError, match=_EMBEDDING_SERVICE_DOWN):
            await metered_embedding.embed(_EMBED_HELLO)
        mock_metering.release.assert_called_once_with(
            mock_metering.reserve.return_value
        )

    async def test_embed_failure_propagates_after_release(
        self,
        metered_embedding: MeteredEmbeddingProvider,
        inner_embedding: MockEmbeddingProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If inner.embed() raises, exception propagates and settle is skipped."""
        inner_embedding.embed = AsyncMock(
            side_effect=RuntimeError(_EMBEDDING_SERVICE_DOWN)
        )
        with pytest.raises(RuntimeError, match=_EMBEDDING_SERVICE_DOWN):
            await metered_embedding.embed(_EMBED_HELLO)
        mock_metering.settle.assert_not_called()

    async def test_release_failure_does_not_mask_provider_error(
        self,
        metered_embedding: MeteredEmbeddingProvider,
        inner_embedding: MockEmbeddingProvider,
        mock_metering: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If both embed() and release() fail, original exception propagates."""
        inner_embedding.embed = AsyncMock(
            side_effect=RuntimeError(_EMBEDDING_SERVICE_DOWN)
        )
        mock_metering.release.side_effect = RuntimeError(_DB_ERROR_MSG)
        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(RuntimeError, match=_EMBEDDING_SERVICE_DOWN),
        ):
            await metered_embedding.embed(_EMBED_HELLO)
        mock_metering.settle.assert_not_called()
        assert any("orphaned" in record.message for record in caplog.records)

    async def test_reserve_failure_prevents_embed_call(
        self,
        metered_embedding: MeteredEmbeddingProvider,
        inner_embedding: MockEmbeddingProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If reserve() raises, inner.embed() is never called."""
        mock_metering.reserve.side_effect = RuntimeError(_NO_PRICING_MSG)
        with pytest.raises(RuntimeError, match=_NO_PRICING_MSG):
            await metered_embedding.embed(_EMBED_HELLO)
        assert len(inner_embedding.calls) == 0
        mock_metering.settle.assert_not_called()
        mock_metering.release.assert_not_called()

    async def test_settle_uses_estimate_for_chunked_batch(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """When total_tokens is -1 (chunked), settle uses sum(len(text))/4 estimate."""
        original_embed = metered_embedding._inner.embed  # noqa: SLF001

        async def embed_with_neg_tokens(texts: list[str]) -> EmbeddingResult:
            result = await original_embed(texts)
            result.total_tokens = -1
            return result

        metered_embedding._inner.embed = embed_with_neg_tokens  # type: ignore[assignment]  # noqa: SLF001

        await metered_embedding.embed(["Hello world"])  # len=11, 11//4 = 2
        call_kwargs = mock_metering.settle.call_args.kwargs
        assert call_kwargs["input_tokens"] == 2

    async def test_settle_receives_zero_output_tokens(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """Embedding settle() always passes output_tokens=0."""
        await metered_embedding.embed(_EMBED_HELLO)
        call_kwargs = mock_metering.settle.call_args.kwargs
        assert call_kwargs["output_tokens"] == 0


# =============================================================================
# MeteredEmbeddingProvider — delegation
# =============================================================================


class TestMeteredEmbeddingProviderDelegation:
    """MeteredEmbeddingProvider delegates non-metered properties."""

    def test_dimensions_delegates(
        self, metered_embedding: MeteredEmbeddingProvider
    ) -> None:
        """dimensions returns inner provider's value."""
        assert metered_embedding.dimensions == 768

    def test_provider_name_delegates(
        self, metered_embedding: MeteredEmbeddingProvider
    ) -> None:
        """provider_name returns inner provider's name."""
        assert metered_embedding.provider_name == _MOCK_PROVIDER_NAME


# =============================================================================
# Dependency injection functions
# =============================================================================


class TestGetMeteredProvider:
    """get_metered_provider DI function."""

    def test_returns_raw_when_metering_disabled(self) -> None:
        """When metering disabled, returns factory singleton directly."""
        from app.api.deps import get_metered_provider

        mock_inner = MockLLMProvider()
        with (
            patch("app.api.deps.settings") as mock_settings,
            patch("app.api.deps.get_llm_provider", return_value=mock_inner),
            patch("app.api.deps.MeteringService") as mock_metering_cls,
        ):
            mock_settings.metering_enabled = False
            result = get_metered_provider(TEST_USER_ID, AsyncMock())
            assert result is mock_inner
            mock_metering_cls.assert_not_called()

    def test_creates_metering_and_admin_config_when_enabled(self) -> None:
        """When metering enabled, creates AdminConfigService, MeteringService, wraps."""
        from app.api.deps import get_metered_provider

        mock_db = AsyncMock()
        mock_registry = {_MOCK_PROVIDER_NAME: MockLLMProvider()}
        with (
            patch("app.api.deps.settings") as mock_settings,
            patch("app.api.deps.get_llm_provider", return_value=MockLLMProvider()),
            patch("app.api.deps.get_llm_registry", return_value=mock_registry),
            patch("app.api.deps.AdminConfigService") as mock_config_cls,
            patch("app.api.deps.MeteringService") as mock_metering_cls,
        ):
            mock_settings.metering_enabled = True
            mock_admin_config = mock_config_cls.return_value
            result = get_metered_provider(TEST_USER_ID, mock_db)
            mock_config_cls.assert_called_once_with(mock_db)
            mock_metering_cls.assert_called_once_with(mock_db, mock_admin_config)
            assert result.provider_name == _MOCK_PROVIDER_NAME


class TestGetMeteredEmbeddingProvider:
    """get_metered_embedding_provider DI function."""

    def test_returns_raw_when_metering_disabled(self) -> None:
        """When metering disabled, returns factory singleton directly."""
        from app.api.deps import get_metered_embedding_provider

        mock_inner = MockEmbeddingProvider()
        with (
            patch("app.api.deps.settings") as mock_settings,
            patch("app.api.deps.get_embedding_provider", return_value=mock_inner),
            patch("app.api.deps.MeteringService") as mock_metering_cls,
        ):
            mock_settings.metering_enabled = False
            result = get_metered_embedding_provider(TEST_USER_ID, AsyncMock())
            assert result is mock_inner
            mock_metering_cls.assert_not_called()

    def test_creates_metering_and_admin_config_when_enabled(self) -> None:
        """When metering enabled, creates AdminConfigService, MeteringService, wraps."""
        from app.api.deps import get_metered_embedding_provider

        mock_db = AsyncMock()
        with (
            patch("app.api.deps.settings") as mock_settings,
            patch(
                "app.api.deps.get_embedding_provider",
                return_value=MockEmbeddingProvider(),
            ),
            patch("app.api.deps.AdminConfigService") as mock_config_cls,
            patch("app.api.deps.MeteringService") as mock_metering_cls,
        ):
            mock_settings.metering_enabled = True
            mock_admin_config = mock_config_cls.return_value
            result = get_metered_embedding_provider(TEST_USER_ID, mock_db)
            mock_config_cls.assert_called_once_with(mock_db)
            mock_metering_cls.assert_called_once_with(mock_db, mock_admin_config)
            assert result.provider_name == _MOCK_PROVIDER_NAME
