"""Tests for persona embedding cache service.

REQ-008 §10.2: Caching for scoring performance.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.services.embedding_cache import (
    CachedPersonaEmbeddings,
    PersonaEmbeddingCache,
)
from app.services.persona_embedding_generator import (
    PersonaEmbeddingData,
    PersonaEmbeddingsResult,
)

# =============================================================================
# Constants
# =============================================================================

_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# =============================================================================
# Test Fixtures
# =============================================================================


def make_persona_embeddings(
    persona_id: uuid.UUID | None = None,
    version: datetime | None = None,
) -> PersonaEmbeddingsResult:
    """Create test persona embeddings."""
    return PersonaEmbeddingsResult(
        persona_id=persona_id or uuid.uuid4(),
        hard_skills=PersonaEmbeddingData(
            vector=[0.1] * 1536,
            source_text="Python (Expert) | AWS (Proficient)",
        ),
        soft_skills=PersonaEmbeddingData(
            vector=[0.2] * 1536,
            source_text="Leadership | Communication",
        ),
        logistics=PersonaEmbeddingData(
            vector=[0.3] * 1536,
            source_text="Remote preference: hybrid\nLocation: Seattle, WA, USA",
        ),
        version=version or datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
        model_name="text-embedding-3-small",
    )


# =============================================================================
# Test: Cache Operations
# =============================================================================


class TestPersonaEmbeddingCacheBasics:
    """Test basic cache operations."""

    def test_cache_miss_returns_none(self):
        """Cache miss returns None."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()

        result = cache.get(_USER_ID, persona_id)

        assert result is None

    def test_cache_hit_returns_embeddings(self):
        """Cache hit returns stored embeddings."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)
        result = cache.get(_USER_ID, persona_id)

        assert result is not None
        assert result.embeddings == embeddings

    def test_invalidate_removes_entry(self):
        """Invalidate removes cached entry."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)
        cache.invalidate(_USER_ID, persona_id)
        result = cache.get(_USER_ID, persona_id)

        assert result is None

    def test_invalidate_nonexistent_is_noop(self):
        """Invalidating non-existent key is a no-op."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()

        # Should not raise
        cache.invalidate(_USER_ID, persona_id)

    def test_clear_all_removes_all_entries(self):
        """clear_all removes all cached entries."""
        cache = PersonaEmbeddingCache()
        persona_id_1 = uuid.uuid4()
        persona_id_2 = uuid.uuid4()
        embeddings_1 = make_persona_embeddings(persona_id=persona_id_1)
        embeddings_2 = make_persona_embeddings(persona_id=persona_id_2)

        cache.put(_USER_ID, persona_id_1, embeddings_1)
        cache.put(_USER_ID, persona_id_2, embeddings_2)
        cache.clear_all()

        assert cache.get(_USER_ID, persona_id_1) is None
        assert cache.get(_USER_ID, persona_id_2) is None


# =============================================================================
# Test: Freshness Validation
# =============================================================================


class TestPersonaEmbeddingCacheFreshness:
    """Test freshness validation using source hashes."""

    def test_get_with_matching_hash_returns_embeddings(self):
        """Cache returns embeddings when source hash matches."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)
        source_text = embeddings.hard_skills.source_text

        cache.put(_USER_ID, persona_id, embeddings)
        result = cache.get_if_fresh(_USER_ID, persona_id, hard_skills_text=source_text)

        assert result is not None
        assert result.embeddings == embeddings

    def test_get_with_changed_source_returns_none(self):
        """Cache returns None when source text has changed."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)
        changed_source = "JavaScript (Expert) | React (Proficient)"

        cache.put(_USER_ID, persona_id, embeddings)
        result = cache.get_if_fresh(
            _USER_ID, persona_id, hard_skills_text=changed_source
        )

        assert result is None
        # Verify it was invalidated (can still get without freshness check)
        assert cache.get(_USER_ID, persona_id) is None

    def test_get_if_fresh_with_all_three_sources(self):
        """Freshness check validates all three embedding source texts."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)

        # All sources match
        result = cache.get_if_fresh(
            _USER_ID,
            persona_id,
            hard_skills_text=embeddings.hard_skills.source_text,
            soft_skills_text=embeddings.soft_skills.source_text,
            logistics_text=embeddings.logistics.source_text,
        )
        assert result is not None

    def test_stale_soft_skills_invalidates_cache(self):
        """Stale soft skills source invalidates the cache."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)

        result = cache.get_if_fresh(
            _USER_ID,
            persona_id,
            hard_skills_text=embeddings.hard_skills.source_text,
            soft_skills_text="Changed Soft Skills",
            logistics_text=embeddings.logistics.source_text,
        )
        assert result is None

    def test_stale_logistics_invalidates_cache(self):
        """Stale logistics source invalidates the cache."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)

        result = cache.get_if_fresh(
            _USER_ID,
            persona_id,
            hard_skills_text=embeddings.hard_skills.source_text,
            soft_skills_text=embeddings.soft_skills.source_text,
            logistics_text="Different location data",
        )
        assert result is None


# =============================================================================
# Test: Cache Statistics
# =============================================================================


class TestPersonaEmbeddingCacheStats:
    """Test cache statistics for monitoring."""

    def test_stats_shows_size(self):
        """Stats includes current cache size."""
        cache = PersonaEmbeddingCache()
        embeddings = make_persona_embeddings()

        assert cache.stats().size == 0

        cache.put(_USER_ID, embeddings.persona_id, embeddings)
        assert cache.stats().size == 1

    def test_stats_tracks_hits_and_misses(self):
        """Stats tracks hit and miss counts."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        # Miss
        cache.get(_USER_ID, uuid.uuid4())
        assert cache.stats().misses == 1
        assert cache.stats().hits == 0

        # Hit
        cache.put(_USER_ID, persona_id, embeddings)
        cache.get(_USER_ID, persona_id)
        assert cache.stats().hits == 1
        assert cache.stats().misses == 1

    def test_stats_tracks_invalidations(self):
        """Stats tracks invalidation count."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)
        cache.invalidate(_USER_ID, persona_id)

        assert cache.stats().invalidations == 1


# =============================================================================
# Test: CachedPersonaEmbeddings
# =============================================================================


class TestCachedPersonaEmbeddings:
    """Test the CachedPersonaEmbeddings dataclass."""

    def test_stores_embeddings_with_source_hashes(self):
        """CachedPersonaEmbeddings stores embeddings and source hashes."""
        embeddings = make_persona_embeddings()
        cached = CachedPersonaEmbeddings(
            embeddings=embeddings,
            hard_skills_hash="abc123",
            soft_skills_hash="def456",
            logistics_hash="ghi789",
        )

        assert cached.embeddings == embeddings
        assert cached.hard_skills_hash == "abc123"
        assert cached.soft_skills_hash == "def456"
        assert cached.logistics_hash == "ghi789"


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestPersonaEmbeddingCacheEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_overwrite_existing_entry(self):
        """Putting new embeddings for same persona overwrites."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()

        embeddings_v1 = make_persona_embeddings(
            persona_id=persona_id,
            version=datetime(2026, 1, 1, tzinfo=UTC),
        )
        embeddings_v2 = make_persona_embeddings(
            persona_id=persona_id,
            version=datetime(2026, 2, 1, tzinfo=UTC),
        )

        cache.put(_USER_ID, persona_id, embeddings_v1)
        cache.put(_USER_ID, persona_id, embeddings_v2)

        result = cache.get(_USER_ID, persona_id)
        assert result is not None
        assert result.embeddings.version == embeddings_v2.version

    def test_get_if_fresh_with_partial_sources(self):
        """Freshness check works with only some source texts provided."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(_USER_ID, persona_id, embeddings)

        # Only check hard_skills freshness
        result = cache.get_if_fresh(
            _USER_ID,
            persona_id,
            hard_skills_text=embeddings.hard_skills.source_text,
        )
        assert result is not None

    def test_empty_source_text_handling(self):
        """Cache handles empty source text correctly."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        embeddings = PersonaEmbeddingsResult(
            persona_id=persona_id,
            hard_skills=PersonaEmbeddingData(vector=[0.1] * 1536, source_text=""),
            soft_skills=PersonaEmbeddingData(vector=[0.2] * 1536, source_text=""),
            logistics=PersonaEmbeddingData(vector=[0.3] * 1536, source_text="data"),
            version=datetime(2026, 1, 15, tzinfo=UTC),
            model_name="text-embedding-3-small",
        )

        cache.put(_USER_ID, persona_id, embeddings)

        # Empty source still matches empty source
        result = cache.get_if_fresh(_USER_ID, persona_id, hard_skills_text="")
        assert result is not None

        # Non-empty vs empty is stale
        result = cache.get_if_fresh(
            _USER_ID, persona_id, hard_skills_text="Python (Expert)"
        )
        assert result is None


# =============================================================================
# Test: Tenant Isolation (Security — defense-in-depth)
# =============================================================================


class TestPersonaEmbeddingCacheTenantIsolation:
    """Same persona_id with different user_id must not share cache entries."""

    def test_different_user_same_persona_is_cache_miss(self):
        """Embeddings cached under user A are invisible to user B."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(user_a, persona_id, embeddings)

        # User B should get a miss for the same persona_id
        assert cache.get(user_b, persona_id) is None
        # User A should still get a hit
        assert cache.get(user_a, persona_id) is not None

    def test_invalidate_only_affects_own_user(self):
        """Invalidating user A's entry does not affect user B's."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(user_a, persona_id, embeddings)
        cache.put(user_b, persona_id, embeddings)

        cache.invalidate(user_a, persona_id)

        assert cache.get(user_a, persona_id) is None
        assert cache.get(user_b, persona_id) is not None

    def test_get_if_fresh_different_user_is_cache_miss(self):
        """get_if_fresh with different user_id returns None."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        embeddings = make_persona_embeddings(persona_id=persona_id)

        cache.put(user_a, persona_id, embeddings)

        result = cache.get_if_fresh(
            user_b,
            persona_id,
            hard_skills_text=embeddings.hard_skills.source_text,
        )
        assert result is None

    def test_put_different_user_creates_separate_entry(self):
        """put() with different user_id creates a new entry, not overwrite."""
        cache = PersonaEmbeddingCache()
        persona_id = uuid.uuid4()
        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        embeddings_a = make_persona_embeddings(
            persona_id=persona_id,
            version=datetime(2026, 1, 1, tzinfo=UTC),
        )
        embeddings_b = make_persona_embeddings(
            persona_id=persona_id,
            version=datetime(2026, 6, 1, tzinfo=UTC),
        )

        cache.put(user_a, persona_id, embeddings_a)
        cache.put(user_b, persona_id, embeddings_b)

        result_a = cache.get(user_a, persona_id)
        result_b = cache.get(user_b, persona_id)
        assert result_a is not None
        assert result_b is not None
        assert result_a.embeddings.version != result_b.embeddings.version
        assert cache.stats().size == 2


# =============================================================================
# Test: LRU Eviction (REQ-008 §10.2 - Prevent Resource Exhaustion)
# =============================================================================


class TestPersonaEmbeddingCacheLRU:
    """Test LRU eviction when cache is full."""

    def test_max_size_default(self):
        """Default max_size is 1000."""
        cache = PersonaEmbeddingCache()
        assert cache.stats().max_size == 1000

    def test_max_size_custom(self):
        """Custom max_size is respected."""
        cache = PersonaEmbeddingCache(max_size=5)
        assert cache.stats().max_size == 5

    def test_max_size_invalid_zero(self):
        """max_size of 0 raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            PersonaEmbeddingCache(max_size=0)

    def test_max_size_invalid_negative(self):
        """Negative max_size raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            PersonaEmbeddingCache(max_size=-1)

    def test_evicts_lru_when_full(self):
        """Oldest entry is evicted when cache is full."""
        cache = PersonaEmbeddingCache(max_size=2)

        # Add two entries
        persona_id_1 = uuid.uuid4()
        persona_id_2 = uuid.uuid4()
        embeddings_1 = make_persona_embeddings(persona_id=persona_id_1)
        embeddings_2 = make_persona_embeddings(persona_id=persona_id_2)

        cache.put(_USER_ID, persona_id_1, embeddings_1)  # First (LRU)
        cache.put(_USER_ID, persona_id_2, embeddings_2)  # Second

        # Cache is full
        assert cache.stats().size == 2

        # Add third entry - should evict first (LRU)
        persona_id_3 = uuid.uuid4()
        embeddings_3 = make_persona_embeddings(persona_id=persona_id_3)
        cache.put(_USER_ID, persona_id_3, embeddings_3)

        # First entry should be evicted
        assert cache.get(_USER_ID, persona_id_1) is None
        assert cache.get(_USER_ID, persona_id_2) is not None
        assert cache.get(_USER_ID, persona_id_3) is not None
        assert cache.stats().size == 2
        assert cache.stats().evictions == 1

    def test_get_updates_lru_order(self):
        """Getting an entry moves it to most-recently-used."""
        cache = PersonaEmbeddingCache(max_size=2)

        persona_id_1 = uuid.uuid4()
        persona_id_2 = uuid.uuid4()
        embeddings_1 = make_persona_embeddings(persona_id=persona_id_1)
        embeddings_2 = make_persona_embeddings(persona_id=persona_id_2)

        cache.put(_USER_ID, persona_id_1, embeddings_1)  # Oldest
        cache.put(_USER_ID, persona_id_2, embeddings_2)  # Newest

        # Access persona_1, making it most recently used
        cache.get(_USER_ID, persona_id_1)

        # Now persona_2 is the LRU, should be evicted
        persona_id_3 = uuid.uuid4()
        embeddings_3 = make_persona_embeddings(persona_id=persona_id_3)
        cache.put(_USER_ID, persona_id_3, embeddings_3)

        assert (
            cache.get(_USER_ID, persona_id_1) is not None
        )  # Was accessed, not evicted
        assert cache.get(_USER_ID, persona_id_2) is None  # LRU, evicted
        assert cache.get(_USER_ID, persona_id_3) is not None

    def test_get_if_fresh_updates_lru_order(self):
        """get_if_fresh also moves entry to most-recently-used."""
        cache = PersonaEmbeddingCache(max_size=2)

        persona_id_1 = uuid.uuid4()
        persona_id_2 = uuid.uuid4()
        embeddings_1 = make_persona_embeddings(persona_id=persona_id_1)
        embeddings_2 = make_persona_embeddings(persona_id=persona_id_2)

        cache.put(_USER_ID, persona_id_1, embeddings_1)  # Oldest
        cache.put(_USER_ID, persona_id_2, embeddings_2)  # Newest

        # Access persona_1 via get_if_fresh
        cache.get_if_fresh(
            _USER_ID,
            persona_id_1,
            hard_skills_text=embeddings_1.hard_skills.source_text,
        )

        # Now persona_2 is the LRU
        persona_id_3 = uuid.uuid4()
        embeddings_3 = make_persona_embeddings(persona_id=persona_id_3)
        cache.put(_USER_ID, persona_id_3, embeddings_3)

        assert cache.get(_USER_ID, persona_id_1) is not None
        assert cache.get(_USER_ID, persona_id_2) is None
        assert cache.get(_USER_ID, persona_id_3) is not None

    def test_stats_tracks_evictions(self):
        """Stats includes eviction count."""
        cache = PersonaEmbeddingCache(max_size=1)

        embeddings_1 = make_persona_embeddings()
        embeddings_2 = make_persona_embeddings()

        cache.put(_USER_ID, embeddings_1.persona_id, embeddings_1)
        assert cache.stats().evictions == 0

        cache.put(_USER_ID, embeddings_2.persona_id, embeddings_2)
        assert cache.stats().evictions == 1

    def test_update_existing_does_not_evict(self):
        """Updating an existing entry doesn't trigger eviction."""
        cache = PersonaEmbeddingCache(max_size=2)

        persona_id_1 = uuid.uuid4()
        persona_id_2 = uuid.uuid4()
        embeddings_1 = make_persona_embeddings(persona_id=persona_id_1)
        embeddings_2 = make_persona_embeddings(persona_id=persona_id_2)

        cache.put(_USER_ID, persona_id_1, embeddings_1)
        cache.put(_USER_ID, persona_id_2, embeddings_2)

        # Update persona_1 with new embeddings (same id)
        embeddings_1_v2 = make_persona_embeddings(
            persona_id=persona_id_1,
            version=datetime(2026, 6, 1, tzinfo=UTC),
        )
        cache.put(_USER_ID, persona_id_1, embeddings_1_v2)

        # No eviction should occur
        assert cache.stats().evictions == 0
        assert cache.stats().size == 2
        assert cache.get(_USER_ID, persona_id_1) is not None
        assert cache.get(_USER_ID, persona_id_2) is not None
