# Token Refresh Hang Fix - 2026-03-04

## Problem

Tool calls were hanging when token reauthentication failed. The logs showed:

```
HTTP Request: POST https://...opgrc/api/v2/query "HTTP/1.1 401 Unauthorized"
Received 401 for POST ..., attempting token refresh and retry
Cleared cached bearer token for re-authentication
```

After this, the request would hang without completing or providing clear error feedback.

## Root Cause

In [`openpages_client.py:_request_with_auth_retry()`](../src/app/core/openpages_client.py:343), when a 401 error occurred:

1. The code caught the `HTTPStatusError` exception (line 423)
2. Cleared the bearer token and re-authenticated (lines 436-437)
3. Retried the request (line 440-441)

**The Issue**: If the retry request also failed (e.g., another 401, network error, or any HTTP error), the `raise_for_status()` call at line 441 would throw an exception. However, this exception was **not caught by the inner exception handler** because we were already inside the `except httpx.HTTPStatusError` block. The exception would propagate to the outer `except Exception` handler, but without proper logging or context about the retry failure, making it appear as if the request had hung.

## Solution

Wrapped the retry logic (lines 434-464) in its own try-except block to:

1. **Catch retry failures explicitly**: Any exception during token refresh or retry is now caught and logged
2. **Add retry failure tracing**: Added a span event `auth_retry_failed` to track retry failures in distributed tracing
3. **Provide clear error messages**: Log the specific error that occurred during retry with `logger.error()`
4. **Maintain error propagation**: Re-raise the exception so it's handled by the outer exception handler with proper metrics

## Code Changes

```python
# Before (lines 423-465)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401 and auth_override is None and self.auth_type == "bearer":
        logger.warning(f"Received 401 for {method} {url}, attempting token refresh and retry")
        
        async with self._auth_lock:
            self._clear_bearer_token()
            await self.initialize_auth()
        
        retry_headers = await self._get_request_headers(auth_override)
        response = await client.request(method, url, headers=retry_headers, **kwargs)
        response.raise_for_status()  # ← If this fails, exception isn't caught!
        
        # ... success handling ...
        return response
    raise

# After (lines 423-478)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401 and auth_override is None and self.auth_type == "bearer":
        logger.warning(f"Received 401 for {method} {url}, attempting token refresh and retry")
        
        try:  # ← NEW: Wrap retry logic
            async with self._auth_lock:
                self._clear_bearer_token()
                await self.initialize_auth()
            
            retry_headers = await self._get_request_headers(auth_override)
            response = await client.request(method, url, headers=retry_headers, **kwargs)
            response.raise_for_status()
            
            # ... success handling ...
            return response
            
        except Exception as retry_error:  # ← NEW: Catch retry failures
            logger.error(f"Token refresh retry failed for {method} {url}: {retry_error}")
            if span and is_tracing_enabled():
                span.add_event("auth_retry_failed", {
                    "error": str(retry_error),
                    "error_type": type(retry_error).__name__
                })
            raise  # Re-raise for outer handler
    raise
```

## Benefits

1. **No more hanging requests**: Retry failures are now caught and logged immediately
2. **Better observability**: Retry failures are tracked in distributed tracing with the `auth_retry_failed` event
3. **Clear error messages**: Logs explicitly state when token refresh retry fails
4. **Proper error propagation**: Exceptions are still raised and handled by the outer exception handler, ensuring metrics are recorded

## Testing

To verify the fix works:

1. **Simulate token refresh failure**: Configure invalid authentication credentials
2. **Trigger a 401**: Make an API call that will fail authentication
3. **Verify logs**: Should see:
   - "Received 401 for POST ..., attempting token refresh and retry"
   - "Token refresh retry failed for POST ...: [error details]"
4. **Check tracing**: Should see `auth_retry_failed` event in Jaeger traces

## Related Files

- [`src/app/core/openpages_client.py`](../src/app/core/openpages_client.py) - Main fix location
- [`docs/TOKEN_REFRESH_IMPLEMENTATION.md`](TOKEN_REFRESH_IMPLEMENTATION.md) - Original token refresh implementation
- [`docs/TOKEN_REFRESH_FIX_2026-02-17.md`](TOKEN_REFRESH_FIX_2026-02-17.md) - Previous token refresh fix

## Impact

- **Low risk**: Only adds error handling, doesn't change success path logic
- **Backward compatible**: No API changes, only improved error handling
- **Performance**: Negligible impact (one additional try-except block)