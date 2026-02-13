"""
Tests for Token Cache Module
"""

import time
import pytest
from unittest.mock import patch

from src.app.auth.cache import TokenCache


class TestTokenCache:
    """Test TokenCache functionality"""

    def test_set_and_get(self):
        """Token stored and retrieved within TTL"""
        cache = TokenCache(default_ttl=3600)
        cache.set("key1", "token_value_1")

        result = cache.get("key1")
        assert result == "token_value_1"

    def test_get_nonexistent_key(self):
        """Getting a nonexistent key returns None"""
        cache = TokenCache()
        assert cache.get("nonexistent") is None

    def test_token_expired(self):
        """Token expired after TTL returns None"""
        cache = TokenCache(default_ttl=1)
        cache.set("key1", "token_value_1")

        # Simulate expiration by manipulating the entry
        entry = cache._cache["key1"]
        entry.expires_at = time.monotonic() - 1  # Already expired

        result = cache.get("key1")
        assert result is None
        assert "key1" not in cache._cache

    def test_eviction(self):
        """Eviction removes entry"""
        cache = TokenCache()
        cache.set("key1", "token_value_1")
        assert cache.get("key1") == "token_value_1"

        cache.evict("key1")
        assert cache.get("key1") is None

    def test_evict_nonexistent_key(self):
        """Evicting a nonexistent key does not raise"""
        cache = TokenCache()
        cache.evict("nonexistent")  # Should not raise

    def test_max_size_enforcement(self):
        """Max size enforcement evicts oldest entry"""
        cache = TokenCache(default_ttl=3600, max_size=3)

        cache.set("key1", "token1")
        cache.set("key2", "token2")
        cache.set("key3", "token3")

        assert len(cache) == 3

        # Adding a 4th entry should evict the oldest
        cache.set("key4", "token4")
        assert len(cache) == 3
        assert cache.get("key4") == "token4"

    def test_clear(self):
        """Clear removes all entries"""
        cache = TokenCache()
        cache.set("key1", "token1")
        cache.set("key2", "token2")
        assert len(cache) == 2

        cache.clear()
        assert len(cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_custom_ttl_per_entry(self):
        """Custom TTL per entry is respected"""
        cache = TokenCache(default_ttl=3600)
        cache.set("key1", "token1", ttl=1)

        assert cache.get("key1") == "token1"

        # Simulate expiration
        entry = cache._cache["key1"]
        entry.expires_at = time.monotonic() - 1
        assert cache.get("key1") is None

    def test_overwrite_existing_key(self):
        """Overwriting an existing key updates the value"""
        cache = TokenCache(max_size=2)
        cache.set("key1", "old_token")
        cache.set("key1", "new_token")

        assert cache.get("key1") == "new_token"
        assert len(cache) == 1  # Should not increase size

    def test_len(self):
        """__len__ returns correct count"""
        cache = TokenCache()
        assert len(cache) == 0

        cache.set("key1", "token1")
        assert len(cache) == 1

        cache.set("key2", "token2")
        assert len(cache) == 2
