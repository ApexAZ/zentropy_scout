"""In-memory token store for job posting ingest previews.

REQ-006 §5.6: Manages confirmation tokens with TTL for preview sessions.

WHY IN-MEMORY:
- Simple for local-first MVP
- Token TTL is short (15 min)
- Preview data is ephemeral, doesn't need persistence
- Can be replaced with Redis for multi-instance deployments later
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.schemas.ingest import ExtractedJobData

# Default TTL for preview tokens (15 minutes)
DEFAULT_TOKEN_TTL_MINUTES = 15


@dataclass
class IngestPreviewData:
    """Stored preview data associated with a confirmation token.

    Attributes:
        user_id: Owner of this preview session.
        raw_text: Original raw text from request.
        source_url: Source URL from request.
        source_name: Source name from request.
        extracted_data: Extracted fields from LLM.
        expires_at: When this token expires.
    """

    user_id: uuid.UUID
    raw_text: str
    source_url: str
    source_name: str
    extracted_data: ExtractedJobData
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class IngestTokenStore:
    """In-memory store for ingest preview tokens.

    Note: This implementation is safe for async/await usage (single-threaded
    event loop) but not for multi-threaded access. For multi-instance
    deployments, replace with Redis-backed implementation.

    WHY CLASS:
    - Encapsulates token management logic
    - Easy to replace with Redis adapter later
    - Testable with clear interface
    """

    def __init__(self, ttl_minutes: int = DEFAULT_TOKEN_TTL_MINUTES) -> None:
        """Initialize the token store.

        Args:
            ttl_minutes: Token time-to-live in minutes.
        """
        self._store: dict[str, IngestPreviewData] = {}
        self._ttl_minutes = ttl_minutes

    def create(
        self,
        user_id: uuid.UUID,
        raw_text: str,
        source_url: str,
        source_name: str,
        extracted_data: ExtractedJobData,
    ) -> tuple[str, datetime]:
        """Create a new preview token.

        Args:
            user_id: The user creating this preview.
            raw_text: Original job posting text.
            source_url: Where the job was found.
            source_name: Name of the source.
            extracted_data: Extracted job fields from LLM.

        Returns:
            Tuple of (token, expires_at).
        """
        token = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=self._ttl_minutes)

        self._store[token] = IngestPreviewData(
            user_id=user_id,
            raw_text=raw_text,
            source_url=source_url,
            source_name=source_name,
            extracted_data=extracted_data,
            expires_at=expires_at,
        )

        return token, expires_at

    def get(self, token: str, user_id: uuid.UUID) -> IngestPreviewData | None:
        """Get preview data if token exists, is valid, and belongs to user.

        Args:
            token: The confirmation token.
            user_id: The requesting user's ID.

        Returns:
            Preview data if valid, None if not found/expired/wrong user.
        """
        data = self._store.get(token)
        if data is None:
            return None

        # Check ownership
        if data.user_id != user_id:
            return None

        # Check expiration
        if datetime.now(UTC) > data.expires_at:
            # Clean up expired token
            del self._store[token]
            return None

        return data

    def consume(self, token: str, user_id: uuid.UUID) -> IngestPreviewData | None:
        """Get and remove preview data (one-time use).

        Args:
            token: The confirmation token.
            user_id: The requesting user's ID.

        Returns:
            Preview data if valid, None if not found/expired/wrong user.
        """
        data = self.get(token, user_id)
        if data is not None:
            del self._store[token]
        return data

    def cleanup_expired(self) -> int:
        """Remove all expired tokens.

        Returns:
            Number of tokens removed.
        """
        now = datetime.now(UTC)
        expired = [
            token for token, data in self._store.items() if now > data.expires_at
        ]
        for token in expired:
            del self._store[token]
        return len(expired)

    def clear(self) -> None:
        """Clear all tokens (for testing)."""
        self._store.clear()


# Singleton instance for the application
_token_store: IngestTokenStore | None = None


def get_token_store() -> IngestTokenStore:
    """Get the singleton token store instance.

    Returns:
        The IngestTokenStore singleton.
    """
    global _token_store
    if _token_store is None:
        _token_store = IngestTokenStore()
    return _token_store


def reset_token_store() -> None:
    """Reset the token store singleton (for testing)."""
    global _token_store
    if _token_store is not None:
        _token_store.clear()
    _token_store = None
