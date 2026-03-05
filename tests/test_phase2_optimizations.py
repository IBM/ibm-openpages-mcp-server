"""
Tests for Phase 2 Token Optimization Features

This test suite validates:
1. LRU cache with size limits and TTL
2. Cache statistics and monitoring
3. ResourceHandlers schema cache
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.config.settings import Settings


def make_mock_client():
    """Create a mock OpenPages client"""
    client = AsyncMock()
    client.get_type_definition = AsyncMock(return_value={
        "id": "test",
        "field_definitions": []
    })
    client.get_type_associations = AsyncMock(return_value=[])
    return client


def make_mock_settings(object_types=None):
    """Create mock settings"""
    settings = MagicMock(spec=Settings)
    settings.OPENPAGES_OBJECT_TYPES = object_types or [
        {"type_id": "SOXIssue", "display_name": "Issue", "path_prefix": "Issue", "namespace": "openpages"}
    ]
    settings.SCHEMA_CACHE_MAX_SIZE = 10
    settings.SCHEMA_CACHE_TTL = 300
    return settings


class TestLRUCache:
    """Test LRU cache implementation in SchemaBuilder"""

    @pytest.mark.asyncio
    async def test_cache_size_limit(self):
        """Test that cache respects max size limit"""
        client = make_mock_client()
        builder = SchemaBuilder(client, max_cache_size=3, cache_ttl=3600)

        # Add 4 items to cache (exceeds limit of 3)
        for i in range(4):
            await builder.get_type_definition(f"type_{i}")

        # Check cache size is limited to 3
        stats = builder.get_cache_stats()
        assert stats["current_size"] == 3, "Cache should be limited to max size"
        assert stats["evictions"] == 1, "Should have evicted 1 item"

        # Verify oldest item (type_0) was evicted
        assert "type_0" not in builder.type_definitions
        assert "type_3" in builder.type_definitions

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test that cache entries expire after TTL"""
        client = make_mock_client()
        call_count = 0

        async def mock_get_type_def(type_id):
            nonlocal call_count
            call_count += 1
            return {"id": type_id, "field_definitions": []}

        async def mock_get_associations(type_id):
            return []

        client.get_type_definition = mock_get_type_def
        client.get_type_associations = mock_get_associations

        builder = SchemaBuilder(client, max_cache_size=10, cache_ttl=1)  # 1 second TTL

        # First call - should hit API
        await builder.get_type_definition("test_type")
        assert call_count == 1

        # Second call immediately - should use cache
        await builder.get_type_definition("test_type")
        assert call_count == 1, "Should use cached value"

        # Wait for TTL to expire
        await asyncio.sleep(1.5)

        # Third call after TTL - should hit API again
        await builder.get_type_definition("test_type")
        assert call_count == 2, "Should fetch fresh data after TTL"

    @pytest.mark.asyncio
    async def test_lru_ordering(self):
        """Test that LRU ordering is maintained"""
        client = make_mock_client()
        builder = SchemaBuilder(client, max_cache_size=3, cache_ttl=3600)

        # Add 3 items
        await builder.get_type_definition("type_1")
        await builder.get_type_definition("type_2")
        await builder.get_type_definition("type_3")

        # Access type_1 again (moves it to end / marks as recently used)
        await builder.get_type_definition("type_1")

        # Add type_4 (should evict type_2, not type_1)
        await builder.get_type_definition("type_4")

        # Verify type_2 was evicted, type_1 remains
        assert "type_2" not in builder.type_definitions
        assert "type_1" in builder.type_definitions
        assert "type_3" in builder.type_definitions
        assert "type_4" in builder.type_definitions

    @pytest.mark.asyncio
    async def test_cache_statistics(self):
        """Test cache statistics tracking"""
        client = make_mock_client()
        builder = SchemaBuilder(client, max_cache_size=5, cache_ttl=3600)

        # Initial stats
        stats = builder.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["current_size"] == 0

        # First access - miss
        await builder.get_type_definition("type_1")
        stats = builder.get_cache_stats()
        assert stats["misses"] == 1
        assert stats["current_size"] == 1

        # Second access - hit
        await builder.get_type_definition("type_1")
        stats = builder.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestCacheStatsStructure:
    """Test cache statistics structure"""

    def test_cache_stats_accessible(self):
        """Test that cache statistics are accessible with all expected fields"""
        client = make_mock_client()
        builder = SchemaBuilder(client, max_cache_size=10, cache_ttl=3600)

        stats = builder.get_cache_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "current_size" in stats
        assert "max_size" in stats
        assert "evictions" in stats
        assert "hit_rate" in stats
        assert "cache_ttl" in stats

    def test_cache_stats_initial_values(self):
        """Test initial cache statistics values"""
        client = make_mock_client()
        builder = SchemaBuilder(client, max_cache_size=10, cache_ttl=3600)

        stats = builder.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["current_size"] == 0
        assert stats["max_size"] == 10
        assert stats["evictions"] == 0
        assert stats["hit_rate"] == "0.0%"


class TestResourceHandlersSchemaCache:
    """Test ResourceHandlers formatted schema cache"""

    def test_resource_handlers_cache_initialized(self):
        """Test that ResourceHandlers initializes its schema cache correctly"""
        mock_schema_builder = MagicMock()
        mock_settings = make_mock_settings()

        handlers = ResourceHandlers(mock_schema_builder, mock_settings)

        # Cache should be initialized
        assert handlers._schema_cache is not None
        assert len(handlers._schema_cache) == 0
        # Max size = SCHEMA_CACHE_MAX_SIZE * 3 (3 modes per type)
        assert handlers._schema_cache_max_size == 30
        assert handlers._schema_cache_ttl == 300

    @pytest.mark.asyncio
    async def test_schema_cache_used_on_second_read(self):
        """Test that schema cache is used on second read of same resource"""
        mock_settings = make_mock_settings()

        async def mock_get_type_def(type_id):
            return {
                "localizedLabel": f"{type_id} Label",
                "description": f"Description for {type_id}",
                "field_definitions": [
                    {"name": "Name", "localized_label": "Name", "data_type": "STRING_TYPE",
                     "required": True, "read_only": False}
                ],
                "associations": []
            }

        mock_schema_builder = MagicMock()
        mock_schema_builder.get_type_definition = AsyncMock(side_effect=mock_get_type_def)

        handlers = ResourceHandlers(mock_schema_builder, mock_settings)

        params = {"uri": "openpages://schema/SOXIssue"}

        # First read - cache miss
        await handlers.handle_read_resource(params)
        assert mock_schema_builder.get_type_definition.call_count == 1
        assert handlers._schema_cache_misses == 1

        # Second read - cache hit
        await handlers.handle_read_resource(params)
        assert mock_schema_builder.get_type_definition.call_count == 1  # Not called again
        assert handlers._schema_cache_hits == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])