"""Scouter Agent error handling service.

REQ-007 §6.7 + §10: Error handling and recovery for job discovery.

Error Handling Strategy:
    - Source API down: Log, skip source, continue with others
    - Rate limit hit: Back off, retry next poll cycle
    - Extraction fails: Store job without extracted skills, flag for retry
    - Scoring fails: Store job with null scores, flag for retry

Key Principle: Fail-forward - continue processing other sources/jobs even
when individual operations fail, flagging failures for later retry.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class SourceErrorType(Enum):
    """Types of errors that can occur when fetching from job sources.

    REQ-007 §6.7: Categorizes source errors for handling decisions.
    """

    API_DOWN = "api_down"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"


class ExtractionStatus(Enum):
    """Status of skill/culture extraction for a job posting.

    REQ-007 §6.7: Tracks extraction state for retry logic.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class ScoringStatus(Enum):
    """Status of fit/stretch scoring for a job posting.

    REQ-007 §6.7: Tracks scoring state for retry logic.
    """

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class RateLimitInfo:
    """Rate limit information extracted from error response.

    REQ-007 §6.7: Used for backoff decisions.

    Attributes:
        retry_after_seconds: Seconds to wait before retrying.
    """

    retry_after_seconds: int


@dataclass
class ProcessingMetadata:
    """Tracks extraction and scoring status for a job posting.

    REQ-007 §6.7: Stored in processing_metadata JSONB column.

    Attributes:
        extraction_status: Current extraction state.
        extraction_error: Error message if extraction failed.
        scoring_status: Current scoring state.
        scoring_error: Error message if scoring failed.
    """

    extraction_status: ExtractionStatus
    extraction_error: str | None
    scoring_status: ScoringStatus
    scoring_error: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONB storage.

        Returns:
            Dict suitable for storing in processing_metadata JSONB column.

        Note:
            Uses Any for values because JSONB dict contains mixed types
            (str, None).
        """
        return {
            "extraction_status": self.extraction_status.value,
            "extraction_error": self.extraction_error,
            "scoring_status": self.scoring_status.value,
            "scoring_error": self.scoring_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProcessingMetadata":
        """Deserialize from JSONB storage.

        Args:
            data: JSONB dict or None for missing/new jobs.

        Returns:
            ProcessingMetadata instance with default PENDING status for missing.

        Raises:
            ValueError: If extraction_status or scoring_status values in data
                are not valid enum values ("pending", "success", "failed").

        Note:
            Uses Any for parameter because JSONB dict contains mixed types.
        """
        if data is None:
            return create_processing_metadata()

        return cls(
            extraction_status=ExtractionStatus(
                data.get("extraction_status", "pending")
            ),
            extraction_error=data.get("extraction_error"),
            scoring_status=ScoringStatus(data.get("scoring_status", "pending")),
            scoring_error=data.get("scoring_error"),
        )


# =============================================================================
# Exceptions
# =============================================================================


class SourceError(Exception):
    """Exception for job source adapter failures.

    REQ-007 §6.7: Raised when a source API fails.

    Attributes:
        source_name: Name of the source that failed.
        error_type: Category of error for handling decisions.
        rate_limit_info: Optional retry info for rate limit errors.
    """

    def __init__(
        self,
        source_name: str,
        error_type: SourceErrorType,
        message: str,
        rate_limit_info: RateLimitInfo | None = None,
    ) -> None:
        """Initialize SourceError.

        Args:
            source_name: Name of the source that failed.
            error_type: Category of error.
            message: Human-readable error description.
            rate_limit_info: Optional retry information.
        """
        super().__init__(message)
        self.source_name = source_name
        self.error_type = error_type
        self.rate_limit_info = rate_limit_info


# =============================================================================
# Error Classification Functions
# =============================================================================


# WHY: These error types represent transient failures that may succeed on retry.
# INVALID_RESPONSE is NOT retryable because the API returned malformed data,
# which indicates a bug in the adapter or a breaking API change.
_RETRYABLE_ERROR_TYPES = frozenset(
    [
        SourceErrorType.API_DOWN,
        SourceErrorType.RATE_LIMITED,
        SourceErrorType.NETWORK_ERROR,
        SourceErrorType.TIMEOUT,
    ]
)


def is_retryable_error(error: SourceError) -> bool:
    """Check if a source error is worth retrying.

    REQ-007 §6.7: Determines if error is transient (retry later) vs
    permanent (needs code fix).

    Args:
        error: The source error to check.

    Returns:
        True if the error type is transient and retryable.
    """
    return error.error_type in _RETRYABLE_ERROR_TYPES


# =============================================================================
# Rate Limit Parsing
# =============================================================================


def parse_rate_limit_response(
    headers: dict[str, str],
) -> RateLimitInfo | None:
    """Extract rate limit retry info from response headers.

    REQ-007 §6.7: Parse standard rate limit headers.

    Supports:
    - retry-after: Standard HTTP header (seconds)
    - x-ratelimit-reset: Common alternative (seconds)

    Args:
        headers: Response headers dict (case-insensitive keys recommended).

    Returns:
        RateLimitInfo if parseable, None otherwise.
    """
    # Try standard retry-after header first
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return RateLimitInfo(retry_after_seconds=int(retry_after))
        except ValueError:
            pass

    # Try x-ratelimit-reset as fallback
    reset = headers.get("x-ratelimit-reset")
    if reset is not None:
        try:
            return RateLimitInfo(retry_after_seconds=int(reset))
        except ValueError:
            pass

    return None


# =============================================================================
# Processing Metadata Helpers
# =============================================================================


def create_processing_metadata() -> ProcessingMetadata:
    """Create fresh processing metadata with pending status.

    REQ-007 §6.7: Initialize metadata for new jobs.

    Returns:
        ProcessingMetadata with all statuses set to PENDING.
    """
    return ProcessingMetadata(
        extraction_status=ExtractionStatus.PENDING,
        extraction_error=None,
        scoring_status=ScoringStatus.PENDING,
        scoring_error=None,
    )


# =============================================================================
# Extraction Status Helpers
# =============================================================================


def mark_extraction_success(metadata: ProcessingMetadata) -> ProcessingMetadata:
    """Mark extraction as successful.

    REQ-007 §6.7: Update status after successful skill/culture extraction.

    Args:
        metadata: Current processing metadata.

    Returns:
        New metadata with extraction marked as SUCCESS.
    """
    return ProcessingMetadata(
        extraction_status=ExtractionStatus.SUCCESS,
        extraction_error=None,
        scoring_status=metadata.scoring_status,
        scoring_error=metadata.scoring_error,
    )


def mark_extraction_failed(
    metadata: ProcessingMetadata,
    error_message: str,
) -> ProcessingMetadata:
    """Mark extraction as failed for retry.

    REQ-007 §6.7: Flag job for extraction retry.

    Args:
        metadata: Current processing metadata.
        error_message: Description of what failed.

    Returns:
        New metadata with extraction marked as FAILED.
    """
    return ProcessingMetadata(
        extraction_status=ExtractionStatus.FAILED,
        extraction_error=error_message,
        scoring_status=metadata.scoring_status,
        scoring_error=metadata.scoring_error,
    )


def needs_extraction_retry(metadata: ProcessingMetadata) -> bool:
    """Check if job needs extraction retry.

    REQ-007 §6.7: Identify jobs with failed extraction.

    Args:
        metadata: Processing metadata to check.

    Returns:
        True if extraction previously failed and needs retry.
    """
    return metadata.extraction_status == ExtractionStatus.FAILED


# =============================================================================
# Scoring Status Helpers
# =============================================================================


def mark_scoring_success(metadata: ProcessingMetadata) -> ProcessingMetadata:
    """Mark scoring as successful.

    REQ-007 §6.7: Update status after successful fit/stretch scoring.

    Args:
        metadata: Current processing metadata.

    Returns:
        New metadata with scoring marked as SUCCESS.
    """
    return ProcessingMetadata(
        extraction_status=metadata.extraction_status,
        extraction_error=metadata.extraction_error,
        scoring_status=ScoringStatus.SUCCESS,
        scoring_error=None,
    )


def mark_scoring_failed(
    metadata: ProcessingMetadata,
    error_message: str,
) -> ProcessingMetadata:
    """Mark scoring as failed for retry.

    REQ-007 §6.7: Flag job for scoring retry.

    Args:
        metadata: Current processing metadata.
        error_message: Description of what failed.

    Returns:
        New metadata with scoring marked as FAILED.
    """
    return ProcessingMetadata(
        extraction_status=metadata.extraction_status,
        extraction_error=metadata.extraction_error,
        scoring_status=ScoringStatus.FAILED,
        scoring_error=error_message,
    )


def needs_scoring_retry(metadata: ProcessingMetadata) -> bool:
    """Check if job needs scoring retry.

    REQ-007 §6.7: Identify jobs with failed scoring.

    Args:
        metadata: Processing metadata to check.

    Returns:
        True if scoring previously failed and needs retry.
    """
    return metadata.scoring_status == ScoringStatus.FAILED
