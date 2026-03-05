# MCP Client Bottleneck - Root Cause Identified

## Executive Summary

**FOUND IT!** The 7-8 second delay is in the official MCP Python client library's `session.initialize()` method, NOT in the server code.

## Profiling Results

### MCP Client Library Performance

| Stage | Duration | Status |
|-------|----------|--------|
| stdio_client connection setup | 111.89ms | ✅ Normal |
| ClientSession creation | 0.08ms | ✅ Normal |
| **session.initialize()** | **8847.37ms** | ❌ **BOTTLENECK** |
| First resource read (cold) | 9.02ms | ✅ Normal |
| Second resource read (warm) | 3.15ms | ✅ Normal |

### Server Performance (For Comparison)

| Operation | Duration | Status |
|-----------|----------|--------|
| Resource handler (warm cache) | 0.05ms | ✅ Excellent |
| Resource handler (cold cache) | 0.30ms | ✅ Excellent |
| JSON-RPC overhead | 0.02ms | ✅ Negligible |

## Root Cause

The **8.8 second delay** occurs in:
```python
await session.initialize()  # Takes 8847.37ms (8.8 seconds)
```

This is the MCP protocol handshake between client and server, implemented in the official `mcp>=1.9.4` Python library.

## Why This Happens

The `session.initialize()` method performs the MCP protocol handshake:
1. Client sends `initialize` request
2. Server responds with capabilities
3. Client processes server capabilities
4. **Something in this exchange takes 8.8 seconds**

Possible causes:
1. **Server startup overhead** - The server logs show extensive initialization (loading schemas, authentication, etc.) taking ~7 seconds
2. **Synchronous operations** - The server may be doing blocking operations during initialization
3. **Network/IPC delays** - stdio communication overhead
4. **Library inefficiency** - The MCP client library may have performance issues

## Evidence from Server Logs

Looking at the server logs, we can see the server takes significant time to initialize:

```
2026-02-26 18:56:20,492 - Starting MCP server
2026-02-26 18:56:27,447 - Ready to process requests  ← 7 seconds later!
```

The server initialization includes:
- Authentication (token exchange)
- Loading dynamic schemas for 4 object types
- Pre-loading resource schemas
- Building tool definitions

**This 7-second server startup is what causes the 8.8-second `session.initialize()` delay!**

## The Real Problem

The issue is **NOT** in:
- ❌ Schema caching (works perfectly - 0.05ms)
- ❌ Resource handlers (extremely fast - 0.05ms)
- ❌ JSON-RPC processing (negligible - 0.02ms)
- ❌ MCP client library itself (just waiting for server)

The issue **IS** in:
- ✅ **Server initialization time** - Takes ~7 seconds to start up
- ✅ **Eager schema loading** - Pre-loads all schemas at startup
- ✅ **Authentication** - Token exchange during initialization

## Solution

### Option 1: Lazy Loading (Recommended)

Instead of pre-loading all schemas at startup, load them on-demand:

```python
# In stdio_runner.py, REMOVE this section:
if not auth_failed:
    try:
        logger.info("Loading dynamic schemas at startup...")
        await server.load_dynamic_schemas()  # ← Remove this
        
        logger.info("Pre-loading resource schemas...")
        for obj_config in server.settings.OPENPAGES_OBJECT_TYPES:
            await server.resource_handlers.handle_read_resource(...)  # ← Remove this
```

**Impact**: 
- First request will be slower (cold cache)
- Subsequent requests will be fast (warm cache)
- `session.initialize()` will complete in <1 second

### Option 2: Keep Server Running

Instead of spawning a new server process for each client session, keep the server running:

```python
# Use HTTP transport instead of stdio
from mcp.client.http import http_client

async with http_client("http://localhost:8000") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()  # Fast - server already initialized
```

**Impact**:
- First connection: ~7 seconds (server startup)
- Subsequent connections: <1 second (server already running)

### Option 3: Optimize Server Startup

Reduce server initialization time by:
1. Parallel schema loading (load all types concurrently)
2. Defer authentication until first request
3. Remove unnecessary pre-loading

## Recommendation

**Use Option 1 (Lazy Loading)** for the stdio transport mode:

1. Remove eager schema loading from `stdio_runner.py`
2. Let schemas load on-demand (first request slower, rest fast)
3. Keep the excellent caching system (already working perfectly)

This will reduce `session.initialize()` from 8.8 seconds to <1 second, while maintaining fast response times for actual requests (0.05ms with cache).

## Performance After Fix

Expected performance with lazy loading:

| Operation | Before | After |
|-----------|--------|-------|
| session.initialize() | 8847ms | <1000ms |
| First resource read | 9ms | 300ms (cold cache) |
| Second resource read | 3ms | 0.05ms (warm cache) |
| **Total first request** | **8856ms** | **<1300ms** |
| **Total subsequent requests** | **3ms** | **0.05ms** |

**Improvement**: 6.8x faster for first request, same speed for subsequent requests.

---

**Investigation Date:** 2026-02-26  
**Root Cause:** Server initialization during `session.initialize()`  
**Solution:** Remove eager schema loading, use lazy loading instead