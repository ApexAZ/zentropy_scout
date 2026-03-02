"""Tests for MeteredLLMProvider and MeteredEmbeddingProvider.

REQ-020 §6.2, §6.5: Proxy wrappers that record token usage after
successful LLM/embedding calls and debit user balances.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.providers.embedding.base import EmbeddingResult
from app.providers.embedding.mock_adapter import MockEmbeddingProvider
from app.providers.llm.base import LLMMessage, LLMResponse, TaskType
from app.providers.llm.mock_adapter import MockLLMProvider
from app.providers.metered_provider import MeteredEmbeddingProvider, MeteredLLMProvider

TEST_USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_HELLO_MESSAGES = [LLMMessage(role="user", content="Hello")]
_MOCK_MODEL = "mock-model"
_MOCK_EMBEDDING_MODEL = "mock-embedding-model"
_DB_ERROR_MSG = "DB error"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_metering() -> AsyncMock:
    """Create a mock MeteringService with async record_and_debit."""
    service = AsyncMock()
    service.record_and_debit = AsyncMock(return_value=None)
    return service


@pytest.fixture
def inner_llm() -> MockLLMProvider:
    """Create a MockLLMProvider as the inner provider."""
    return MockLLMProvider()


@pytest.fixture
def inner_embedding() -> MockEmbeddingProvider:
    """Create a MockEmbeddingProvider as the inner provider."""
    return MockEmbeddingProvider()


@pytest.fixture
def metered_llm(
    inner_llm: MockLLMProvider, mock_metering: AsyncMock
) -> MeteredLLMProvider:
    """Create a MeteredLLMProvider wrapping a mock inner provider."""
    return MeteredLLMProvider(inner_llm, mock_metering, TEST_USER_ID)


@pytest.fixture
def metered_embedding(
    inner_embedding: MockEmbeddingProvider, mock_metering: AsyncMock
) -> MeteredEmbeddingProvider:
    """Create a MeteredEmbeddingProvider wrapping a mock inner provider."""
    return MeteredEmbeddingProvider(inner_embedding, mock_metering, TEST_USER_ID)


# =============================================================================
# MeteredLLMProvider — complete()
# =============================================================================


class TestMeteredLLMProviderComplete:
    """MeteredLLMProvider.complete() delegates and records usage."""

    async def test_returns_inner_response(
        self, metered_llm: MeteredLLMProvider
    ) -> None:
        """complete() returns the inner provider's response unchanged."""
        messages = _HELLO_MESSAGES
        response = await metered_llm.complete(messages, TaskType.EXTRACTION)
        assert response.model == _MOCK_MODEL
        assert response.input_tokens == 100
        assert response.output_tokens == 50

    async def test_records_usage_after_success(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """complete() calls record_and_debit after successful call."""
        messages = _HELLO_MESSAGES
        await metered_llm.complete(messages, TaskType.EXTRACTION)
        mock_metering.record_and_debit.assert_called_once()

    async def test_records_correct_arguments(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """record_and_debit receives correct provider, model, task, tokens."""
        messages = _HELLO_MESSAGES
        await metered_llm.complete(messages, TaskType.EXTRACTION)
        mock_metering.record_and_debit.assert_called_once_with(
            user_id=TEST_USER_ID,
            provider="mock",
            model=_MOCK_MODEL,
            task_type="extraction",
            input_tokens=100,
            output_tokens=50,
        )

    async def test_does_not_record_on_provider_error(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If inner.complete() raises, no usage is recorded."""

        inner_llm.complete = AsyncMock(side_effect=RuntimeError("Provider unavailable"))

        messages = _HELLO_MESSAGES
        with pytest.raises(RuntimeError, match="Provider unavailable"):
            await metered_llm.complete(messages, TaskType.EXTRACTION)
        mock_metering.record_and_debit.assert_not_called()

    async def test_passes_kwargs_through(
        self, metered_llm: MeteredLLMProvider, inner_llm: MockLLMProvider
    ) -> None:
        """complete() forwards all kwargs to inner provider."""
        messages = _HELLO_MESSAGES
        await metered_llm.complete(
            messages,
            TaskType.EXTRACTION,
            max_tokens=500,
            temperature=0.5,
        )
        assert inner_llm.calls[-1]["kwargs"]["max_tokens"] == 500
        assert inner_llm.calls[-1]["kwargs"]["temperature"] == 0.5

    async def test_returns_response_when_recording_fails(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """If record_and_debit fails, response is still returned."""
        mock_metering.record_and_debit.side_effect = RuntimeError(_DB_ERROR_MSG)
        messages = _HELLO_MESSAGES
        response = await metered_llm.complete(messages, TaskType.EXTRACTION)
        assert response.model == _MOCK_MODEL

    async def test_logs_when_recording_fails(
        self,
        metered_llm: MeteredLLMProvider,
        mock_metering: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Recording failure is logged with user ID."""
        mock_metering.record_and_debit.side_effect = RuntimeError(_DB_ERROR_MSG)
        messages = _HELLO_MESSAGES
        await metered_llm.complete(messages, TaskType.EXTRACTION)
        assert str(TEST_USER_ID) in caplog.text
        assert "Failed to record" in caplog.text


# =============================================================================
# MeteredLLMProvider — stream()
# =============================================================================


class TestMeteredLLMProviderStream:
    """MeteredLLMProvider.stream() passes through without metering."""

    async def test_yields_inner_stream_chunks(
        self, metered_llm: MeteredLLMProvider
    ) -> None:
        """stream() yields all chunks from inner provider."""
        messages = _HELLO_MESSAGES
        chunks = []
        async for chunk in metered_llm.stream(messages, TaskType.EXTRACTION):
            chunks.append(chunk)
        assert len(chunks) > 0

    async def test_does_not_record_usage(
        self, metered_llm: MeteredLLMProvider, mock_metering: AsyncMock
    ) -> None:
        """stream() does NOT call record_and_debit."""
        messages = _HELLO_MESSAGES
        async for _ in metered_llm.stream(messages, TaskType.EXTRACTION):
            pass
        mock_metering.record_and_debit.assert_not_called()


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
        assert metered_llm.provider_name == "mock"


# =============================================================================
# MeteredLLMProvider — model_override passthrough
# =============================================================================


class TestMeteredLLMProviderModelOverride:
    """MeteredLLMProvider passes model_override to inner provider."""

    async def test_model_override_passed_to_inner(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
    ) -> None:
        """model_override is forwarded to inner.complete()."""
        inner_llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="test",
                model="override-model",
                input_tokens=10,
                output_tokens=5,
                finish_reason="stop",
                latency_ms=1.0,
            )
        )
        metered_llm._inner = inner_llm  # noqa: SLF001

        await metered_llm.complete(
            _HELLO_MESSAGES,
            TaskType.EXTRACTION,
            model_override="override-model",
        )

        inner_llm.complete.assert_called_once()
        call_kwargs = inner_llm.complete.call_args
        assert call_kwargs.kwargs.get("model_override") == "override-model"

    async def test_model_override_none_passed_as_none(
        self,
        metered_llm: MeteredLLMProvider,
        inner_llm: MockLLMProvider,
    ) -> None:
        """When model_override is None, None is forwarded to inner."""
        inner_llm.complete = AsyncMock(
            return_value=LLMResponse(
                content="test",
                model=_MOCK_MODEL,
                input_tokens=10,
                output_tokens=5,
                finish_reason="stop",
                latency_ms=1.0,
            )
        )
        metered_llm._inner = inner_llm  # noqa: SLF001

        await metered_llm.complete(
            _HELLO_MESSAGES,
            TaskType.EXTRACTION,
            model_override=None,
        )

        inner_llm.complete.assert_called_once()
        call_kwargs = inner_llm.complete.call_args
        assert call_kwargs.kwargs.get("model_override") is None


# =============================================================================
# MeteredEmbeddingProvider — embed()
# =============================================================================


class TestMeteredEmbeddingProviderEmbed:
    """MeteredEmbeddingProvider.embed() delegates and records usage."""

    async def test_returns_inner_result(
        self, metered_embedding: MeteredEmbeddingProvider
    ) -> None:
        """embed() returns the inner provider's result unchanged."""
        result = await metered_embedding.embed(["Hello"])
        assert result.model == _MOCK_EMBEDDING_MODEL
        assert result.dimensions == 1536
        assert len(result.vectors) == 1

    async def test_records_usage_after_success(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """embed() calls record_and_debit after successful call."""
        await metered_embedding.embed(["Hello"])
        mock_metering.record_and_debit.assert_called_once()

    async def test_records_correct_arguments(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """record_and_debit receives correct args for embedding."""
        await metered_embedding.embed(["Hello world"])
        call_kwargs = mock_metering.record_and_debit.call_args.kwargs
        assert call_kwargs["user_id"] == TEST_USER_ID
        assert call_kwargs["provider"] == "mock"
        assert call_kwargs["model"] == _MOCK_EMBEDDING_MODEL
        assert call_kwargs["task_type"] == "embedding"
        assert call_kwargs["output_tokens"] == 0
        # MockEmbeddingProvider: total_tokens = len(texts) * 10
        assert call_kwargs["input_tokens"] == 10

    async def test_does_not_record_on_error(
        self,
        metered_embedding: MeteredEmbeddingProvider,
        inner_embedding: MockEmbeddingProvider,
        mock_metering: AsyncMock,
    ) -> None:
        """If inner.embed() raises, no usage is recorded."""

        inner_embedding.embed = AsyncMock(
            side_effect=RuntimeError("Embedding service down")
        )

        with pytest.raises(RuntimeError, match="Embedding service down"):
            await metered_embedding.embed(["Hello"])
        mock_metering.record_and_debit.assert_not_called()

    async def test_returns_result_when_recording_fails(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """If record_and_debit fails, result is still returned."""
        mock_metering.record_and_debit.side_effect = RuntimeError(_DB_ERROR_MSG)
        result = await metered_embedding.embed(["Hello"])
        assert result.model == _MOCK_EMBEDDING_MODEL

    async def test_estimates_tokens_for_chunked_batch(
        self, metered_embedding: MeteredEmbeddingProvider, mock_metering: AsyncMock
    ) -> None:
        """When total_tokens is -1 (chunked), estimate as sum(len(text))/4."""
        # Patch inner to return total_tokens=-1 (chunked batch)
        original_embed = metered_embedding._inner.embed  # noqa: SLF001

        async def embed_with_neg_tokens(texts: list[str]) -> EmbeddingResult:
            result = await original_embed(texts)
            result.total_tokens = -1
            return result

        metered_embedding._inner.embed = embed_with_neg_tokens  # type: ignore[assignment]  # noqa: SLF001

        await metered_embedding.embed(["Hello world"])  # len=11, //4 = 2
        call_kwargs = mock_metering.record_and_debit.call_args.kwargs
        assert call_kwargs["input_tokens"] == 2  # 11 // 4 = 2


# =============================================================================
# MeteredEmbeddingProvider — delegation
# =============================================================================


class TestMeteredEmbeddingProviderDelegation:
    """MeteredEmbeddingProvider delegates non-metered properties."""

    def test_dimensions_delegates(
        self, metered_embedding: MeteredEmbeddingProvider
    ) -> None:
        """dimensions returns inner provider's value."""
        assert metered_embedding.dimensions == 1536

    def test_provider_name_delegates(
        self, metered_embedding: MeteredEmbeddingProvider
    ) -> None:
        """provider_name returns inner provider's name."""
        assert metered_embedding.provider_name == "mock"


# =============================================================================
# Dependency injection functions
# =============================================================================


class TestGetMeteredProvider:
    """get_metered_provider DI function."""

    async def test_returns_raw_when_metering_disabled(self) -> None:
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

    async def test_creates_metering_when_enabled(self) -> None:
        """When metering enabled, creates MeteringService and wraps provider."""
        from app.api.deps import get_metered_provider

        mock_db = AsyncMock()
        with (
            patch("app.api.deps.settings") as mock_settings,
            patch("app.api.deps.get_llm_provider", return_value=MockLLMProvider()),
            patch("app.api.deps.MeteringService") as mock_metering_cls,
        ):
            mock_settings.metering_enabled = True
            result = get_metered_provider(TEST_USER_ID, mock_db)
            mock_metering_cls.assert_called_once_with(mock_db)
            # Verify wrapper delegates to inner provider
            assert result.provider_name == "mock"


class TestGetMeteredEmbeddingProvider:
    """get_metered_embedding_provider DI function."""

    async def test_returns_raw_when_metering_disabled(self) -> None:
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

    async def test_creates_metering_when_enabled(self) -> None:
        """When metering enabled, creates MeteringService and wraps provider."""
        from app.api.deps import get_metered_embedding_provider

        mock_db = AsyncMock()
        with (
            patch("app.api.deps.settings") as mock_settings,
            patch(
                "app.api.deps.get_embedding_provider",
                return_value=MockEmbeddingProvider(),
            ),
            patch("app.api.deps.MeteringService") as mock_metering_cls,
        ):
            mock_settings.metering_enabled = True
            result = get_metered_embedding_provider(TEST_USER_ID, mock_db)
            mock_metering_cls.assert_called_once_with(mock_db)
            # Verify wrapper delegates to inner provider
            assert result.provider_name == "mock"
