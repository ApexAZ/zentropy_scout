"""Tests for IngestTokenStore — in-memory token store for job posting ingest.

REQ-006 §5.6: Manages confirmation tokens with TTL for preview sessions.

Covers:
- create: token generation, TTL, capacity limits, per-user cap, auto-cleanup
- get: retrieval, tenant isolation, expiration check
- consume: one-time use semantics
- cleanup_expired: batch removal of expired tokens
- clear: full store wipe
- Singleton lifecycle: get_token_store, reset_token_store
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.ingest import ExtractedJobData
from app.services.ingest_token_store import (
    IngestTokenStore,
    get_token_store,
    reset_token_store,
)

# =============================================================================
# Constants
# =============================================================================

_USER_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
_USER_B = uuid.UUID("20000000-0000-0000-0000-000000000002")
_TTL_MINUTES = 15


# =============================================================================
# Helpers
# =============================================================================


def _extracted_data(**overrides: object) -> ExtractedJobData:
    """Build minimal ExtractedJobData for testing."""
    base: ExtractedJobData = {
        "job_title": "Engineer",
        "company_name": "TestCorp",
    }
    return {**base, **overrides}  # type: ignore[typeddict-item]


def _create_token(
    store: IngestTokenStore,
    user_id: uuid.UUID = _USER_A,
    raw_text: str = "text",
    source_url: str = "",
    source_name: str = "Test",
) -> tuple[str, datetime]:
    """Create a token with sensible defaults for testing."""
    return store.create(
        user_id=user_id,
        raw_text=raw_text,
        source_url=source_url,
        source_name=source_name,
        extracted_data=_extracted_data(),
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def store() -> IngestTokenStore:
    """Fresh token store for each test."""
    return IngestTokenStore(ttl_minutes=_TTL_MINUTES)


# =============================================================================
# Tests — create
# =============================================================================


class TestCreate:
    """Token creation with TTL and capacity limits."""

    def test_create_returns_token_and_expiry(self, store: IngestTokenStore) -> None:
        """create() returns a UUID4 token and a future expiration datetime."""
        token, expires_at = store.create(
            user_id=_USER_A,
            raw_text="Job posting text",
            source_url="https://example.com/job/1",
            source_name="Example",
            extracted_data=_extracted_data(),
        )
        assert len(token) == 36  # UUID4 format
        assert expires_at > datetime.now(UTC)

    def test_create_stores_all_fields(self, store: IngestTokenStore) -> None:
        """Stored preview data contains all provided fields."""
        data = _extracted_data(job_title="Senior Engineer")
        token, _ = store.create(
            user_id=_USER_A,
            raw_text="Full posting text",
            source_url="https://example.com/job/2",
            source_name="LinkedIn",
            extracted_data=data,
        )
        preview = store.get(token, _USER_A)
        assert preview is not None
        assert preview.user_id == _USER_A
        assert preview.raw_text == "Full posting text"
        assert preview.source_url == "https://example.com/job/2"
        assert preview.source_name == "LinkedIn"
        assert preview.extracted_data["job_title"] == "Senior Engineer"

    def test_create_unique_tokens(self, store: IngestTokenStore) -> None:
        """Each create() call generates a unique token."""
        tokens = {_create_token(store)[0] for _ in range(10)}
        assert len(tokens) == 10

    def test_create_calls_cleanup_before_capacity_check(self) -> None:
        """create() removes expired tokens before checking capacity.

        Fills store to max, expires all tokens, then verifies a new
        create() succeeds (cleanup frees capacity before rejection).
        """
        store = IngestTokenStore(ttl_minutes=1, max_store_size=3)

        # Fill to capacity
        for _ in range(3):
            _create_token(store)

        # Expire all tokens
        past = datetime.now(UTC) - timedelta(minutes=5)
        for data in store._store.values():
            data.expires_at = past

        # Should succeed: cleanup frees capacity
        token, _ = _create_token(store, raw_text="new")
        assert store.get(token, _USER_A) is not None

    def test_create_rejects_when_global_capacity_exceeded(self) -> None:
        """create() raises ValidationError when global capacity is exceeded."""
        from app.core.errors import ValidationError

        store = IngestTokenStore(ttl_minutes=_TTL_MINUTES, max_store_size=2)

        # Fill to capacity
        for _ in range(2):
            _create_token(store)

        # Third token should be rejected
        with pytest.raises(ValidationError, match="capacity"):
            _create_token(store, user_id=_USER_B)

    def test_create_rejects_when_per_user_cap_exceeded(self) -> None:
        """create() raises ValidationError when per-user cap is exceeded."""
        from app.core.errors import ValidationError

        store = IngestTokenStore(ttl_minutes=_TTL_MINUTES, max_per_user=2)

        # Fill user A's cap
        for _ in range(2):
            _create_token(store)

        # User A's third token should be rejected
        with pytest.raises(ValidationError, match="Per-user"):
            _create_token(store)

    def test_create_cleanup_frees_per_user_cap(self) -> None:
        """create() cleanup frees per-user slots from expired tokens."""
        store = IngestTokenStore(ttl_minutes=1, max_per_user=2)

        # Fill user A's cap
        for _ in range(2):
            _create_token(store)

        # Expire all tokens
        past = datetime.now(UTC) - timedelta(minutes=5)
        for data in store._store.values():
            data.expires_at = past

        # Should succeed: cleanup frees per-user slots
        token, _ = _create_token(store)
        assert store.get(token, _USER_A) is not None

    def test_per_user_cap_does_not_affect_other_users(self) -> None:
        """User B can still create tokens when User A hits per-user cap."""
        store = IngestTokenStore(
            ttl_minutes=_TTL_MINUTES, max_store_size=100, max_per_user=2
        )

        # Fill user A's cap
        for _ in range(2):
            _create_token(store)

        # User B should still be able to create
        token, _ = _create_token(store, user_id=_USER_B)
        assert store.get(token, _USER_B) is not None


# =============================================================================
# Tests — get
# =============================================================================


class TestGet:
    """Token retrieval with ownership and expiration checks."""

    def test_get_returns_data_for_valid_token(self, store: IngestTokenStore) -> None:
        """get() returns stored preview data for a valid token."""
        token, _ = _create_token(store)
        result = store.get(token, _USER_A)
        assert result is not None
        assert result.raw_text == "text"

    def test_get_returns_none_for_nonexistent_token(
        self, store: IngestTokenStore
    ) -> None:
        """get() returns None for a token that doesn't exist."""
        assert store.get("nonexistent-token", _USER_A) is None

    def test_get_returns_none_for_wrong_user(self, store: IngestTokenStore) -> None:
        """get() returns None when user_id doesn't match (tenant isolation)."""
        token, _ = _create_token(store)
        # User B cannot access User A's token
        assert store.get(token, _USER_B) is None

    def test_get_returns_none_for_expired_token(self, store: IngestTokenStore) -> None:
        """get() returns None and removes expired token."""
        token, _ = _create_token(store)
        # Expire the token
        store._store[token].expires_at = datetime.now(UTC) - timedelta(minutes=1)

        assert store.get(token, _USER_A) is None
        # Token should be cleaned up
        assert token not in store._store

    def test_get_does_not_consume_token(self, store: IngestTokenStore) -> None:
        """get() is non-destructive — token remains accessible after get()."""
        token, _ = _create_token(store)
        # Multiple get() calls should all succeed
        assert store.get(token, _USER_A) is not None
        assert store.get(token, _USER_A) is not None


# =============================================================================
# Tests — consume
# =============================================================================


class TestConsume:
    """One-time token consumption."""

    def test_consume_returns_data_and_removes_token(
        self, store: IngestTokenStore
    ) -> None:
        """consume() returns data and removes the token from store."""
        token, _ = _create_token(store)
        result = store.consume(token, _USER_A)
        assert result is not None
        assert result.raw_text == "text"

        # Token is gone after consume
        assert store.get(token, _USER_A) is None
        assert store.consume(token, _USER_A) is None

    def test_consume_returns_none_for_wrong_user(self, store: IngestTokenStore) -> None:
        """consume() returns None for wrong user (tenant isolation)."""
        token, _ = _create_token(store)
        # User B cannot consume User A's token
        assert store.consume(token, _USER_B) is None
        # Token should still exist for User A
        assert store.get(token, _USER_A) is not None

    def test_cross_tenant_consume_preserves_legitimate_consume(
        self, store: IngestTokenStore
    ) -> None:
        """After wrong-user consume fails, correct user can still consume."""
        token, _ = _create_token(store)
        # User B's failed consume should not destroy User A's token
        assert store.consume(token, _USER_B) is None
        # User A can still consume successfully
        result = store.consume(token, _USER_A)
        assert result is not None
        assert result.raw_text == "text"

    def test_consume_returns_none_for_expired_token(
        self, store: IngestTokenStore
    ) -> None:
        """consume() returns None for expired token."""
        token, _ = _create_token(store)
        store._store[token].expires_at = datetime.now(UTC) - timedelta(minutes=1)

        assert store.consume(token, _USER_A) is None

    def test_consume_returns_none_for_nonexistent_token(
        self, store: IngestTokenStore
    ) -> None:
        """consume() returns None for nonexistent token."""
        assert store.consume("nonexistent-token", _USER_A) is None


# =============================================================================
# Tests — cleanup_expired
# =============================================================================


class TestCleanupExpired:
    """Batch removal of expired tokens."""

    def test_cleanup_removes_expired_tokens(self, store: IngestTokenStore) -> None:
        """cleanup_expired() removes only expired tokens."""
        tokens = [_create_token(store)[0] for _ in range(3)]

        # Expire the first two
        past = datetime.now(UTC) - timedelta(minutes=1)
        store._store[tokens[0]].expires_at = past
        store._store[tokens[1]].expires_at = past

        removed = store.cleanup_expired()
        assert removed == 2
        assert store.get(tokens[0], _USER_A) is None
        assert store.get(tokens[1], _USER_A) is None
        assert store.get(tokens[2], _USER_A) is not None

    def test_cleanup_preserves_other_users_valid_tokens(
        self, store: IngestTokenStore
    ) -> None:
        """cleanup_expired() only removes expired tokens across users."""
        token_a, _ = _create_token(store)
        token_b, _ = _create_token(store, user_id=_USER_B)

        # Expire only User A's token
        store._store[token_a].expires_at = datetime.now(UTC) - timedelta(minutes=1)

        removed = store.cleanup_expired()
        assert removed == 1
        assert store.get(token_a, _USER_A) is None
        assert store.get(token_b, _USER_B) is not None

    def test_cleanup_returns_zero_when_none_expired(
        self, store: IngestTokenStore
    ) -> None:
        """cleanup_expired() returns 0 when no tokens are expired."""
        _create_token(store)
        assert store.cleanup_expired() == 0

    def test_cleanup_on_empty_store(self, store: IngestTokenStore) -> None:
        """cleanup_expired() on empty store returns 0."""
        assert store.cleanup_expired() == 0


# =============================================================================
# Tests — clear
# =============================================================================


class TestClear:
    """Full store wipe."""

    def test_clear_removes_all_tokens(self, store: IngestTokenStore) -> None:
        """clear() removes all tokens regardless of expiration."""
        tokens = [_create_token(store)[0] for _ in range(3)]

        store.clear()
        for token in tokens:
            assert store.get(token, _USER_A) is None

    def test_clear_on_empty_store(self, store: IngestTokenStore) -> None:
        """clear() on empty store is a no-op."""
        store.clear()  # Should not raise


# =============================================================================
# Tests — singleton lifecycle
# =============================================================================


class TestSingletonLifecycle:
    """get_token_store() and reset_token_store() singleton management."""

    def test_get_token_store_returns_singleton(self) -> None:
        """get_token_store() returns the same instance on repeated calls."""
        reset_token_store()
        store1 = get_token_store()
        store2 = get_token_store()
        assert store1 is store2

    def test_reset_clears_store_and_creates_new_instance(self) -> None:
        """reset_token_store() clears data and returns new instance."""
        reset_token_store()
        store1 = get_token_store()
        _create_token(store1)
        reset_token_store()
        store2 = get_token_store()
        assert store2 is not store1
        # New store should have no tokens
        assert store2.get("any-token", _USER_A) is None

    def test_reset_is_safe_when_no_store_exists(self) -> None:
        """reset_token_store() is a no-op when singleton is None."""
        reset_token_store()
        reset_token_store()  # Should not raise
