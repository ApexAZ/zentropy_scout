"""Persona embedding cache service.

REQ-008 §10.2: Caching for scoring performance.

Provides in-memory caching for persona embeddings with freshness validation
using source text hashes. Embeddings are cached until the persona changes,
detected by comparing source text hashes.

Cache invalidation triggers:
- Any persona data change (skills, preferences, etc.)
- Manual invalidation via invalidate() or clear_all()
- Freshness check failure (source hash mismatch)
- LRU eviction when cache exceeds max_size

The skill synonym dictionary and title normalization mappings (also mentioned
in §10.2) are currently hardcoded in-memory in hard_skills_match.py and
role_title_match.py respectively. When these become dynamic (loaded from
database or API), TTL-based caching with 24h expiry should be added here.
"""

import uuid
from collections import OrderedDict
from dataclasses import dataclass

from app.services.embedding_storage import compute_source_hash
from app.services.persona_embedding_generator import PersonaEmbeddingsResult

# =============================================================================
# Constants
# =============================================================================

# Default maximum cache size (prevents unbounded memory growth)
# Each entry is ~37KB (3 * 1536 * 8 bytes for float64 vectors + hashes)
# 1000 entries ≈ 37MB
_DEFAULT_MAX_SIZE = 1000


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CachedPersonaEmbeddings:
    """Cached embedding result with source hashes for freshness validation.

    REQ-008 §10.2: Cache persona embeddings until persona update.

    Stores the embeddings along with hashes of the source text that was
    embedded. When retrieving from cache, the current source text can be
    hashed and compared to detect staleness.

    Attributes:
        embeddings: The cached PersonaEmbeddingsResult.
        hard_skills_hash: SHA-256 hash of hard skills source text.
        soft_skills_hash: SHA-256 hash of soft skills source text.
        logistics_hash: SHA-256 hash of logistics source text.
    """

    embeddings: PersonaEmbeddingsResult
    hard_skills_hash: str
    soft_skills_hash: str
    logistics_hash: str


@dataclass
class CacheStats:
    """Cache statistics for monitoring.

    Attributes:
        size: Number of entries currently in cache.
        max_size: Maximum cache size (entries evicted when exceeded).
        hits: Number of cache hits since creation.
        misses: Number of cache misses since creation.
        invalidations: Number of invalidations since creation.
        evictions: Number of LRU evictions since creation.
    """

    size: int
    max_size: int
    hits: int
    misses: int
    invalidations: int
    evictions: int


# =============================================================================
# Persona Embedding Cache
# =============================================================================


class PersonaEmbeddingCache:
    """In-memory cache for persona embeddings with LRU eviction.

    REQ-008 §10.2: Cache persona embeddings until persona update.

    The cache stores PersonaEmbeddingsResult objects keyed by persona_id,
    along with source text hashes for freshness validation. When embeddings
    are retrieved, the caller can optionally provide current source texts
    to validate freshness — if the source has changed, the cache entry is
    invalidated and None is returned.

    This enables the optimization described in REQ-008 §10.1 (batch scoring):
    persona embeddings are loaded once and reused across multiple job scores.

    Cache Size:
        The cache has a configurable max_size (default 1000 entries). When
        the cache is full, the least-recently-used entry is evicted to make
        room for new entries. This prevents unbounded memory growth.

    Thread Safety:
        This implementation is designed for single-threaded asyncio usage
        (the typical FastAPI pattern). For multi-threaded usage, wrap
        operations in a lock or use a thread-safe dict implementation.

    Example:
        >>> cache = PersonaEmbeddingCache()
        >>> embeddings = await generate_persona_embeddings(persona, embed_fn)
        >>> cache.put(persona.id, embeddings)
        >>>
        >>> # Later, check if cached embeddings are still fresh
        >>> current_text = build_hard_skills_text(persona.skills)
        >>> cached = cache.get_if_fresh(persona.id, hard_skills_text=current_text)
        >>> if cached:
        ...     # Use cached embeddings
        ...     result = cached.embeddings
        >>> else:
        ...     # Regenerate embeddings
        ...     result = await generate_persona_embeddings(persona, embed_fn)
        ...     cache.put(persona.id, result)
    """

    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        """Initialize empty cache.

        Args:
            max_size: Maximum number of entries before LRU eviction.
                Default is 1000 entries (~37MB memory).
        """
        if max_size <= 0:
            msg = f"max_size must be positive, got {max_size}"
            raise ValueError(msg)

        self._max_size = max_size
        self._cache: OrderedDict[uuid.UUID, CachedPersonaEmbeddings] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        self._evictions = 0

    def get(self, persona_id: uuid.UUID) -> CachedPersonaEmbeddings | None:
        """Get cached embeddings without freshness validation.

        Moves the accessed entry to most-recently-used position.

        Args:
            persona_id: UUID of the persona.

        Returns:
            CachedPersonaEmbeddings if found, None if not cached.
        """
        entry = self._cache.get(persona_id)
        if entry is None:
            self._misses += 1
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(persona_id)
        self._hits += 1
        return entry

    def get_if_fresh(
        self,
        persona_id: uuid.UUID,
        *,
        hard_skills_text: str | None = None,
        soft_skills_text: str | None = None,
        logistics_text: str | None = None,
    ) -> CachedPersonaEmbeddings | None:
        """Get cached embeddings if they are fresh.

        Validates cached embeddings against current source texts. If any
        provided source text doesn't match its cached hash, the entry is
        invalidated and None is returned.

        Args:
            persona_id: UUID of the persona.
            hard_skills_text: Current hard skills text to validate against.
            soft_skills_text: Current soft skills text to validate against.
            logistics_text: Current logistics text to validate against.

        Returns:
            CachedPersonaEmbeddings if cached and fresh, None otherwise.
            If stale, the cache entry is removed.
        """
        entry = self._cache.get(persona_id)
        if entry is None:
            self._misses += 1
            return None

        # Validate freshness for each provided source text
        is_stale = False

        if hard_skills_text is not None:
            current_hash = compute_source_hash(hard_skills_text)
            if current_hash != entry.hard_skills_hash:
                is_stale = True

        if soft_skills_text is not None:
            current_hash = compute_source_hash(soft_skills_text)
            if current_hash != entry.soft_skills_hash:
                is_stale = True

        if logistics_text is not None:
            current_hash = compute_source_hash(logistics_text)
            if current_hash != entry.logistics_hash:
                is_stale = True

        if is_stale:
            # Invalidate stale entry
            self._invalidate_internal(persona_id)
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(persona_id)
        self._hits += 1
        return entry

    def put(
        self,
        persona_id: uuid.UUID,
        embeddings: PersonaEmbeddingsResult,
    ) -> None:
        """Cache embeddings for a persona.

        Computes source hashes from the embeddings' source texts for
        future freshness validation. If the cache is full, evicts the
        least-recently-used entry.

        Args:
            persona_id: UUID of the persona.
            embeddings: The embeddings to cache.
        """
        # If updating existing entry, remove it first (will be re-added at end)
        if persona_id in self._cache:
            del self._cache[persona_id]
        # Evict LRU entries if at capacity
        while len(self._cache) >= self._max_size:
            # popitem(last=False) removes the oldest (least recently used)
            self._cache.popitem(last=False)
            self._evictions += 1

        self._cache[persona_id] = CachedPersonaEmbeddings(
            embeddings=embeddings,
            hard_skills_hash=compute_source_hash(embeddings.hard_skills.source_text),
            soft_skills_hash=compute_source_hash(embeddings.soft_skills.source_text),
            logistics_hash=compute_source_hash(embeddings.logistics.source_text),
        )

    def invalidate(self, persona_id: uuid.UUID) -> None:
        """Remove cached embeddings for a persona.

        No-op if persona_id is not in cache.

        Args:
            persona_id: UUID of the persona to invalidate.
        """
        self._invalidate_internal(persona_id)

    def _invalidate_internal(self, persona_id: uuid.UUID) -> None:
        """Internal invalidation that tracks stats."""
        if persona_id in self._cache:
            del self._cache[persona_id]
            self._invalidations += 1

    def clear_all(self) -> None:
        """Remove all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        self._invalidations += count

    def stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with current size, max_size, hits, misses,
            invalidations, and evictions.
        """
        return CacheStats(
            size=len(self._cache),
            max_size=self._max_size,
            hits=self._hits,
            misses=self._misses,
            invalidations=self._invalidations,
            evictions=self._evictions,
        )
