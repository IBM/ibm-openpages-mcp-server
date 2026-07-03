"""
Token Cache Module

TTL-based in-memory cache for authentication tokens.
Thread-safe for single-threaded asyncio (Python dicts are safe).

Used per-process by both ApiKeyTokenProvider (type 3) and TicketTokenProvider's
hot-path layer (type 4). A single shared instance is owned by AuthService so that
repeated tool calls within a token's lifetime never touch the IDP or Redis.
"""

import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached token with expiration time."""
    token: str
    expires_at: float


class TokenCache:
    """
    TTL-based token cache with max size enforcement.

    Tokens are cached by a hashed key and automatically evicted
    when expired or when the cache exceeds max_size.
    """

    def __init__(self, default_ttl: int = 3600, max_size: int = 100):
        """
        Initialize the token cache.

        Args:
            default_ttl: Default time-to-live in seconds for cached tokens
            max_size: Maximum number of entries before oldest is evicted
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size

    def get(self, key: str) -> Optional[str]:
        """
        Get a cached token if not expired.

        Args:
            key: Cache key

        Returns:
            Token string if found and not expired, None otherwise
        """
        entry = self._cache.get(key)
        if entry is None:
            return None

        if time.monotonic() >= entry.expires_at:
            # Token expired, evict it
            del self._cache[key]
            logger.debug("Cache entry expired, evicted")
            return None

        return entry.token

    def set(self, key: str, token: str, ttl: Optional[int] = None) -> None:
        """
        Cache a token with TTL.

        Args:
            key: Cache key
            token: Token string to cache
            ttl: Time-to-live in seconds (uses default_ttl if not specified)
        """
        # Evict oldest if at max size
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_oldest()

        effective_ttl = ttl if ttl is not None else self.default_ttl
        self._cache[key] = CacheEntry(
            token=token,
            expires_at=time.monotonic() + effective_ttl
        )
        logger.debug("Token cached successfully")

    def evict(self, key: str) -> None:
        """
        Remove a specific cache entry.

        Args:
            key: Cache key to evict
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug("Cache entry evicted")

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.debug("Cache cleared")

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry by expiration time."""
        if not self._cache:
            return

        oldest_key = min(self._cache, key=lambda k: self._cache[k].expires_at)
        del self._cache[oldest_key]
        logger.debug("Evicted oldest cache entry")

    def __len__(self) -> int:
        return len(self._cache)
