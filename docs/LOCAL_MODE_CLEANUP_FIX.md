# Local Mode Connection Pool Cleanup Fix

## Issue
The local (stdio) mode MCP server was not properly closing the httpx client connection pool on shutdown, leading to resource leaks.

## Root Cause
The `run_stdio_server()` function in `src/app/mcp/local/stdio_runner.py` created an `MCPServer` instance which initializes an `OpenPagesClient` with a shared httpx.AsyncClient for connection pooling. However, the function had no cleanup logic to close this client when the server shut down.

### Exit Paths Without Cleanup (Before Fix)
1. **Normal shutdown**: `should_exit` breaks the loop (line 117-118)
2. **KeyboardInterrupt**: Caught in `runner.py` but no cleanup
3. **Fatal exceptions**: `sys.exit(1)` without cleanup (line 149)

## Solution
Added a `try/finally` block to guarantee cleanup in all exit scenarios:

```python
async def run_stdio_server(custom_settings: Optional[Settings] = None) -> None:
    server = None
    try:
        # Server initialization and request processing
        server = MCPServer(custom_settings=app_settings)
        await server.initialize_client()
        
        # Main request loop
        while True:
            # ... request processing ...
            if should_exit:
                break
    
    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        # CRITICAL: Always cleanup httpx client connection pool
        if server and hasattr(server, 'client') and server.client:
            try:
                await server.client.close()
                logger.info("Closed httpx client connection pool")
            except Exception as cleanup_error:
                logger.error(f"Error during client cleanup: {cleanup_error}")
```

## Changes Made

### File: `src/app/mcp/local/stdio_runner.py`

1. **Updated docstring** (line 27-30):
   - Added note about try/finally for cleanup

2. **Restructured exception handling** (line 147-158):
   - Moved KeyboardInterrupt handling from `runner.py` to `stdio_runner.py`
   - Removed `sys.exit(1)` to allow finally block to execute
   - Changed fatal exception handling to re-raise instead of exit

3. **Added finally block** (line 149-158):
   - Checks if server and client exist
   - Calls `await server.client.close()`
   - Logs cleanup completion
   - Wraps cleanup in try/except to handle cleanup errors gracefully

## Consistency with Remote Mode

This fix makes local mode consistent with remote mode's cleanup pattern:

**Remote Mode** (`main.py:107-111`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup ...
    yield
    # Cleanup on shutdown
    server = get_server()
    if server and hasattr(server, 'client') and server.client:
        await server.client.close()
```

**Local Mode** (now):
```python
async def run_stdio_server():
    try:
        # ... server operation ...
    finally:
        # Cleanup on shutdown
        if server and hasattr(server, 'client') and server.client:
            await server.client.close()
```

## Benefits

1. **No Resource Leaks**: Connection pool is always closed
2. **Guaranteed Cleanup**: Finally block executes in all scenarios
3. **Better Error Handling**: Cleanup errors are logged but don't prevent shutdown
4. **Consistent Pattern**: Matches remote mode's cleanup approach
5. **Follows Best Practices**: Proper async resource management

## Testing

The fix ensures cleanup in these scenarios:

1. ✅ **Normal shutdown**: Shutdown request → finally block executes
2. ✅ **KeyboardInterrupt**: Ctrl+C → caught, finally block executes
3. ✅ **Fatal error**: Exception → re-raised, finally block executes first
4. ✅ **Cleanup error**: If close() fails, error is logged but doesn't prevent shutdown

## Connection Pooling Architecture

The connection pooling is implemented in `OpenPagesClient._get_http_client()`:

```python
async def _get_http_client(self) -> httpx.AsyncClient:
    """Get or lazily create a shared httpx.AsyncClient for connection pooling."""
    if self._http_client is None:
        async with self._http_client_lock:
            if self._http_client is None:
                max_connections = getattr(self.settings, 'HTTP_MAX_CONNECTIONS', 20)
                pool_limits = httpx.Limits(
                    max_connections=max_connections,
                    max_keepalive_connections=max_connections,
                )
                self._http_client = httpx.AsyncClient(
                    verify=self.settings.SSL_VERIFY,
                    limits=pool_limits,
                )
    return self._http_client
```

**Key Points:**
- Shared across all requests in both local and remote modes
- Uses double-checked locking for thread-safe lazy initialization
- Configurable via `HTTP_MAX_CONNECTIONS` setting (default: 20)
- Must be explicitly closed to release resources

## Related Files

- `src/app/core/openpages_client.py`: Connection pool implementation
- `src/app/mcp/mcp_server.py`: Creates OpenPagesClient instance
- `src/app/mcp/local/stdio_runner.py`: Local mode entry point (fixed)
- `src/app/mcp/remote/server_instance.py`: Remote mode singleton
- `main.py`: Remote mode cleanup in lifespan context manager

## Date
2026-02-25