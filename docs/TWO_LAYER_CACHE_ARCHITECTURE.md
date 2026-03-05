# Two-Layer Cache Architecture

**Implementation Date:** 2026-02-26  
**Status:** ✅ Complete

## Overview

The OpenPages MCP server now implements a **two-layer caching architecture** for optimal performance:

1. **Layer 1: Type Definition Cache** (SchemaBuilder) - Raw API data
2. **Layer 2: Formatted Schema Cache** (ResourceHandlers) - Built schemas per mode

This architecture eliminates redundant API calls AND redundant schema building, providing near-instant responses for cached schemas.

## Architecture Diagram

```
AI Agent Request: openpages://schema/SOXRisk?mode=compact
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Formatted Schema Cache (ResourceHandlers)          │
│ Cache Key: "SOXRisk:compact"                                │
│                                                              │
│ ┌──────────────┐                                            │
│ │ Cache Hit?   │ YES → Return cached JSON (0ms)             │
│ └──────────────┘                                            │
│        │ NO                                                  │
│        ↓                                                     │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Layer 1: Type Definition Cache (SchemaBuilder)          │ │
│ │ Cache Key: "SOXRisk"                                     │ │
│ │                                                          │ │
│ │ ┌──────────────┐                                        │ │
│ │ │ Cache Hit?   │ YES → Return type def (0.1ms)          │ │
│ │ └──────────────┘                                        │ │
│ │        │ NO                                              │ │
│ │        ↓                                                 │ │
│ │ Fetch from OpenPages API (200-500ms)                    │ │
│ │ Cache type definition                                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│        ↓                                                     │
│ Build schema for mode (1-5ms)                               │
│ Format as JSON (0.5ms)                                      │
│ Cache formatted schema                                      │
│ Return to AI agent                                          │
└─────────────────────────────────────────────────────────────┘
```

## Performance Comparison

| Scenario | Layer 1 | Layer 2 | Total Time | Speedup |
|----------|---------|---------|------------|---------|
| **Cold start** (no cache) | Miss (500ms) | Miss | ~506ms | 1x |
| **Warm Layer 1** (type cached) | Hit (0.1ms) | Miss | ~6ms | 84x |
| **Hot** (both cached) | N/A | Hit | ~0ms | ∞ |

## Implementation Details

### Layer 1: Type Definition Cache

**Location:** [`src/app/mcp/schema_builder.py`](../src/app/mcp/schema_builder.py)

**What it caches:**
- Raw type definitions from OpenPages Content API
- Field definitions with metadata
- Association information
- Enum values

**Cache key:** `type_id` (e.g., "SOXRisk")

**Configuration:**
```python
SCHEMA_CACHE_MAX_SIZE = 20  # Max type definitions
SCHEMA_CACHE_TTL = 3600     # 1 hour TTL
```

**Features:**
- LRU eviction when full
- TTL-based expiration
- Thread-safe (asyncio.Lock)
- Statistics tracking (hits, misses, evictions)

### Layer 2: Formatted Schema Cache

**Location:** [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py)

**What it caches:**
- Formatted JSON schemas (minified)
- Mode-specific schemas (minimal/compact/full)
- Ready-to-send responses

**Cache key:** `{type_id}:{mode}` (e.g., "SOXRisk:compact")

**Configuration:**
```python
# Automatically sized: SCHEMA_CACHE_MAX_SIZE * 3 (for 3 modes)
_schema_cache_max_size = 20 * 3 = 60  # Max formatted schemas
_schema_cache_ttl = 3600              # Same TTL as Layer 1
```

**Features:**
- LRU eviction when full
- TTL-based expiration
- Per-mode caching (minimal, compact, full)
- Statistics tracking (hits, misses, evictions)

## Cache Statistics

Both layers provide detailed statistics for monitoring:

### Layer 1 (Type Definitions)
```python
schema_builder.get_cache_stats()
# Returns:
{
    "hits": 45,
    "misses": 12,
    "current_size": 18,
    "max_size": 20,
    "evictions": 3,
    "hit_rate": "78.9%"
}
```

### Layer 2 (Formatted Schemas)
```python
resource_handlers.get_schema_cache_stats()
# Returns:
{
    "hits": 120,
    "misses": 15,
    "evictions": 5,
    "current_size": 54,
    "max_size": 60,
    "hit_rate": "88.9%",
    "ttl_seconds": 3600
}
```

## Memory Usage

**Layer 1:** ~20 type definitions × 10KB = ~200KB
**Layer 2:** ~60 formatted schemas × 5KB = ~300KB
**Total:** ~500KB maximum

This is negligible for modern systems and provides massive performance benefits.

## Cache Invalidation

Both caches use **TTL-based invalidation**:
- Default: 1 hour (3600 seconds)
- Configurable via `SCHEMA_CACHE_TTL`
- Automatic cleanup on expiration

**Manual invalidation** (if needed):
```python
# Clear Layer 1
schema_builder.type_definitions.clear()
schema_builder._cache_timestamps.clear()

# Clear Layer 2
resource_handlers._schema_cache.clear()
```

## Benefits

### 1. Eliminates Redundant API Calls
- Layer 1 caches raw type definitions
- Multiple mode requests use same type definition
- 200-500ms saved per API call

### 2. Eliminates Redundant Schema Building
- Layer 2 caches formatted schemas per mode
- Same mode requests return instantly
- 1-5ms saved per schema build

### 3. Optimal Memory Usage
- Only caches what's actually used (LRU)
- Bounded memory growth (max size limits)
- Automatic cleanup (TTL expiration)

### 4. Mode-Specific Optimization
- Each mode (minimal/compact/full) cached separately
- AI agents can switch modes without penalty
- Progressive disclosure works efficiently

## Example Usage Patterns

### Pattern 1: Initial Exploration
```
Request 1: openpages://schema/SOXRisk?mode=minimal
  → Layer 1 miss (500ms) + Layer 2 miss (1ms) = 501ms
  → Caches: type def + minimal schema

Request 2: openpages://schema/SOXRisk?mode=minimal (same)
  → Layer 2 hit = 0ms ✨
```

### Pattern 2: Mode Progression
```
Request 1: openpages://schema/SOXRisk?mode=compact
  → Layer 1 miss (500ms) + Layer 2 miss (2ms) = 502ms
  → Caches: type def + compact schema

Request 2: openpages://schema/SOXRisk?mode=full
  → Layer 1 hit (0.1ms) + Layer 2 miss (3ms) = 3.1ms
  → Caches: full schema (type def already cached)

Request 3: openpages://schema/SOXRisk?mode=compact (back to compact)
  → Layer 2 hit = 0ms ✨
```

### Pattern 3: Multiple Types
```
Request 1: openpages://schema/SOXRisk?mode=compact
  → Layer 1 miss (500ms) + Layer 2 miss = 502ms

Request 2: openpages://schema/SOXControl?mode=compact
  → Layer 1 miss (500ms) + Layer 2 miss = 502ms

Request 3: openpages://schema/SOXRisk?mode=compact (revisit)
  → Layer 2 hit = 0ms ✨

Request 4: openpages://schema/SOXControl?mode=full
  → Layer 1 hit (0.1ms) + Layer 2 miss (3ms) = 3.1ms
```

## Monitoring

### Log Messages

**Layer 1 (Type Definition Cache):**
```
INFO: Using cached type definition for SOXRisk (age: 45.2s)
INFO: Cache entry for SOXRisk expired (age: 3601.5s), will refresh
DEBUG: Evicted SOXIssue from cache (LRU)
```

**Layer 2 (Formatted Schema Cache):**
```
DEBUG: Using cached formatted schema for SOXRisk:compact (hit rate: 88.9%)
DEBUG: Cache miss for SOXRisk:full, building schema (hit rate: 88.9%)
DEBUG: Cached formatted schema for SOXRisk:full (cache size: 54/60)
DEBUG: Evicted schema cache entry: SOXIssue:minimal
```

### Metrics

Both caches expose Prometheus metrics (if observability enabled):
```
# Layer 1
openpages_type_cache_hits_total
openpages_type_cache_misses_total
openpages_type_cache_size
openpages_type_cache_evictions_total

# Layer 2
openpages_schema_cache_hits_total
openpages_schema_cache_misses_total
openpages_schema_cache_size
openpages_schema_cache_evictions_total
```

## Configuration

All cache settings are configurable via environment variables:

```bash
# .env file
SCHEMA_CACHE_MAX_SIZE=20      # Max type definitions (Layer 1)
SCHEMA_CACHE_TTL=3600         # Cache TTL in seconds (both layers)
```

Layer 2 size is automatically calculated as `SCHEMA_CACHE_MAX_SIZE * 3` to accommodate all three modes.

## Testing

Comprehensive tests in [`tests/test_phase2_optimizations.py`](../tests/test_phase2_optimizations.py):

- LRU eviction behavior
- TTL expiration
- Cache statistics
- Thread safety
- Hit rate calculations

Run tests:
```bash
pytest tests/test_phase2_optimizations.py -v
```

## Future Enhancements

Potential improvements for Phase 3:

1. **Persistent cache** - Redis/Memcached for multi-instance deployments
2. **Preloading** - Warm cache on startup with common types
3. **Adaptive TTL** - Longer TTL for stable types, shorter for volatile
4. **Cache warming** - Background refresh before expiration
5. **Compression** - Compress cached schemas for memory efficiency

## Conclusion

The two-layer cache architecture provides:
- ✅ **Near-instant responses** for cached schemas (0ms)
- ✅ **Minimal memory footprint** (~500KB max)
- ✅ **Automatic management** (LRU + TTL)
- ✅ **Full observability** (statistics + metrics)
- ✅ **Thread-safe** (asyncio.Lock)
- ✅ **Configurable** (environment variables)

This architecture is production-ready and provides optimal performance for AI agent interactions with OpenPages schemas.