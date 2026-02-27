"""Tests for Scouter Agent error handling.

REQ-007 §6.7 + §10: Error handling and recovery for job discovery.

Tests cover:
1. Source adapter error handling (API down, rate limits)
2. Extraction failure flagging
3. Scoring failure flagging
4. Fail-forward behavior (continue processing other sources/jobs)
"""

from app.services.scouter_errors import (
    ExtractionStatus,
    ProcessingMetadata,
    RateLimitInfo,
    ScoringStatus,
    SourceError,
    SourceErrorType,
    create_processing_metadata,
    is_retryable_error,
    mark_extraction_failed,
    mark_extraction_success,
    mark_scoring_failed,
    mark_scoring_success,
    needs_extraction_retry,
    needs_scoring_retry,
    parse_rate_limit_response,
)

# =============================================================================
# SourceError Exception Tests
# =============================================================================


class TestSourceError:
    """Tests for SourceError exception class."""

    def test_stores_attributes_when_created(self) -> None:
        """SourceError stores source name and error type when created."""
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.API_DOWN,
            message="Connection refused",
        )

        assert error.source_name == "Adzuna"
        assert error.error_type == SourceErrorType.API_DOWN
        assert "Connection refused" in str(error)

    def test_includes_rate_limit_info_when_rate_limited(self) -> None:
        """SourceError includes retry info when rate limited."""
        error = SourceError(
            source_name="RemoteOK",
            error_type=SourceErrorType.RATE_LIMITED,
            message="Rate limit exceeded",
            rate_limit_info=RateLimitInfo(retry_after_seconds=60),
        )

        assert error.error_type == SourceErrorType.RATE_LIMITED
        assert error.rate_limit_info is not None
        assert error.rate_limit_info.retry_after_seconds == 60

    def test_has_api_error_attributes(self) -> None:
        """SourceError should have code and status_code for API error handling."""
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.API_DOWN,
            message="Connection refused",
        )
        assert error.code == "SOURCE_ERROR"
        assert error.status_code == 502


# =============================================================================
# Error Retry Classification Tests
# =============================================================================


class TestIsRetryableError:
    """Tests for determining if a source error is retryable."""

    def test_rate_limit_is_retryable(self) -> None:
        """Rate limit errors should be retried next poll cycle."""
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.RATE_LIMITED,
            message="Rate limit exceeded",
        )
        assert is_retryable_error(error) is True

    def test_network_error_is_retryable(self) -> None:
        """Network errors are transient and retryable."""
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.NETWORK_ERROR,
            message="Connection reset",
        )
        assert is_retryable_error(error) is True

    def test_timeout_is_retryable(self) -> None:
        """Timeout errors are transient and retryable."""
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.TIMEOUT,
            message="Request timed out",
        )
        assert is_retryable_error(error) is True

    def test_api_down_is_retryable(self) -> None:
        """API down (5xx) errors are transient and retryable."""
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.API_DOWN,
            message="503 Service Unavailable",
        )
        assert is_retryable_error(error) is True

    def test_invalid_response_not_retryable(self) -> None:
        """Invalid response (malformed JSON) is not retryable."""
        # WHY: If the API returns malformed data, retrying won't help.
        # This is a permanent error requiring adapter code fix.
        error = SourceError(
            source_name="Adzuna",
            error_type=SourceErrorType.INVALID_RESPONSE,
            message="JSON decode error",
        )
        assert is_retryable_error(error) is False


# =============================================================================
# Rate Limit Parsing Tests
# =============================================================================


class TestParseRateLimitResponse:
    """Tests for extracting rate limit info from error responses."""

    def test_extracts_seconds_when_retry_after_header_present(self) -> None:
        """Extracts retry-after seconds when header is present."""
        headers = {"retry-after": "120"}
        info = parse_rate_limit_response(headers)

        assert info is not None
        assert info.retry_after_seconds == 120

    def test_returns_none_when_retry_after_header_missing(self) -> None:
        """Returns None when retry-after header is missing."""
        headers = {"content-type": "application/json"}
        info = parse_rate_limit_response(headers)

        assert info is None

    def test_returns_none_when_retry_after_value_invalid(self) -> None:
        """Returns None when retry-after is not a valid number."""
        headers = {"retry-after": "invalid"}
        info = parse_rate_limit_response(headers)

        assert info is None

    def test_extracts_seconds_when_x_ratelimit_reset_present(self) -> None:
        """Extracts seconds when x-ratelimit-reset header is present."""
        headers = {"x-ratelimit-reset": "300"}
        info = parse_rate_limit_response(headers)

        assert info is not None
        assert info.retry_after_seconds == 300


# =============================================================================
# Processing Metadata Tests
# =============================================================================


class TestProcessingMetadata:
    """Tests for job processing status tracking."""

    def test_initializes_with_pending_status_when_created(self) -> None:
        """Initializes with pending status when created."""
        metadata = create_processing_metadata()

        assert metadata.extraction_status == ExtractionStatus.PENDING
        assert metadata.extraction_error is None
        assert metadata.scoring_status == ScoringStatus.PENDING
        assert metadata.scoring_error is None

    def test_serializes_to_dict_when_to_dict_called(self) -> None:
        """Serializes to dict for JSONB storage when to_dict called."""
        metadata = ProcessingMetadata(
            extraction_status=ExtractionStatus.FAILED,
            extraction_error="LLM timeout",
            scoring_status=ScoringStatus.PENDING,
            scoring_error=None,
        )

        data = metadata.to_dict()

        assert data["extraction_status"] == "failed"
        assert data["extraction_error"] == "LLM timeout"
        assert data["scoring_status"] == "pending"
        assert data["scoring_error"] is None

    def test_deserializes_when_from_dict_called(self) -> None:
        """Deserializes from JSONB when from_dict called."""
        data = {
            "extraction_status": "success",
            "extraction_error": None,
            "scoring_status": "failed",
            "scoring_error": "Embedding service down",
        }

        metadata = ProcessingMetadata.from_dict(data)

        assert metadata.extraction_status == ExtractionStatus.SUCCESS
        assert metadata.scoring_status == ScoringStatus.FAILED
        assert metadata.scoring_error == "Embedding service down"

    def test_returns_pending_status_when_from_dict_called_with_none(self) -> None:
        """Returns pending status when from_dict called with None."""
        # WHY: Jobs created before this feature will have null metadata
        metadata = ProcessingMetadata.from_dict(None)

        assert metadata.extraction_status == ExtractionStatus.PENDING
        assert metadata.scoring_status == ScoringStatus.PENDING


# =============================================================================
# Extraction Status Helpers Tests
# =============================================================================


class TestExtractionStatusHelpers:
    """Tests for marking and checking extraction status."""

    def test_sets_success_status_when_extraction_succeeds(self) -> None:
        """Sets success status when extraction succeeds."""
        metadata = create_processing_metadata()
        updated = mark_extraction_success(metadata)

        assert updated.extraction_status == ExtractionStatus.SUCCESS
        assert updated.extraction_error is None

    def test_sets_failed_status_and_error_when_extraction_fails(self) -> None:
        """Sets failed status and stores error when extraction fails."""
        metadata = create_processing_metadata()
        updated = mark_extraction_failed(metadata, "LLM service unavailable")

        assert updated.extraction_status == ExtractionStatus.FAILED
        assert updated.extraction_error == "LLM service unavailable"

    def test_needs_extraction_retry_when_failed(self) -> None:
        """Jobs with failed extraction need retry."""
        metadata = ProcessingMetadata(
            extraction_status=ExtractionStatus.FAILED,
            extraction_error="Timeout",
            scoring_status=ScoringStatus.PENDING,
            scoring_error=None,
        )

        assert needs_extraction_retry(metadata) is True

    def test_needs_extraction_retry_when_success(self) -> None:
        """Jobs with successful extraction don't need retry."""
        metadata = ProcessingMetadata(
            extraction_status=ExtractionStatus.SUCCESS,
            extraction_error=None,
            scoring_status=ScoringStatus.PENDING,
            scoring_error=None,
        )

        assert needs_extraction_retry(metadata) is False

    def test_needs_extraction_retry_when_pending(self) -> None:
        """Jobs with pending extraction don't need retry (haven't tried yet)."""
        metadata = create_processing_metadata()

        assert needs_extraction_retry(metadata) is False


# =============================================================================
# Scoring Status Helpers Tests
# =============================================================================


class TestScoringStatusHelpers:
    """Tests for marking and checking scoring status."""

    def test_sets_success_status_when_scoring_succeeds(self) -> None:
        """Sets success status when scoring succeeds."""
        metadata = create_processing_metadata()
        updated = mark_scoring_success(metadata)

        assert updated.scoring_status == ScoringStatus.SUCCESS
        assert updated.scoring_error is None

    def test_sets_failed_status_and_error_when_scoring_fails(self) -> None:
        """Sets failed status and stores error when scoring fails."""
        metadata = create_processing_metadata()
        updated = mark_scoring_failed(metadata, "Embedding service down")

        assert updated.scoring_status == ScoringStatus.FAILED
        assert updated.scoring_error == "Embedding service down"

    def test_needs_scoring_retry_when_failed(self) -> None:
        """Jobs with failed scoring need retry."""
        metadata = ProcessingMetadata(
            extraction_status=ExtractionStatus.SUCCESS,
            extraction_error=None,
            scoring_status=ScoringStatus.FAILED,
            scoring_error="Rate limit",
        )

        assert needs_scoring_retry(metadata) is True

    def test_needs_scoring_retry_when_success(self) -> None:
        """Jobs with successful scoring don't need retry."""
        metadata = ProcessingMetadata(
            extraction_status=ExtractionStatus.SUCCESS,
            extraction_error=None,
            scoring_status=ScoringStatus.SUCCESS,
            scoring_error=None,
        )

        assert needs_scoring_retry(metadata) is False

    def test_needs_scoring_retry_when_pending(self) -> None:
        """Jobs with pending scoring don't need retry (haven't tried yet)."""
        metadata = create_processing_metadata()

        assert needs_scoring_retry(metadata) is False
