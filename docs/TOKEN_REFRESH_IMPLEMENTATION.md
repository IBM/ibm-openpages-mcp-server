# Token Refresh Implementation

## Problem
When the MCP server runs for an extended period, authentication tokens expire, causing 401 Unauthorized errors on subsequent API calls. This was particularly problematic for bearer token authentication (IBM Cloud IAM, MCSP, and CP4D).

## Solution
Implemented a two-layer automatic token refresh mechanism in the `OpenPagesClient` class:
1. **Proactive refresh**: Check token expiry before each API call and refresh if needed
2. **Reactive retry**: Catch 401 errors and automatically retry with a fresh token

## Implementation Details

### 1. Token Expiration Tracking
Added the following attributes to `OpenPagesClient.__init__()`:
- `token_expiry`: Stores the datetime when the current token will expire
- `token_refresh_buffer`: Time buffer (5 minutes) before actual expiry to trigger refresh

### 2. Token Expiry Time Setting
Modified `fetch_token()` method to set `token_expiry` based on authentication type:
- **CP4D**: Sets expiry to 1 hour from token fetch (conservative estimate)
- **IBM Cloud IAM**: Uses `expires_in` from response (typically 3600 seconds)
- **MCSP**: Uses `expires_in` from response (typically 3600 seconds)

### 3. Token Expiration Check
Added `_is_token_expired()` method:
- Returns `True` if token is expired or will expire within the refresh buffer
- Returns `True` if `token_expiry` is `None` (no token fetched yet)

### 4. Automatic Token Refresh
Added `_refresh_token_if_needed()` method:
- Checks if token is expired or expiring soon
- Automatically fetches a new token if needed
- Updates the Authorization header with the new token
- Logs refresh operations for monitoring

### 5. Integration with API Methods
Updated all API methods to call token refresh before making requests:
- `query()`
- `get_content()`
- `create_content()`
- `update_content()`
- `get_type_definition()`
- `get_type_associations()`
- `get_username_by_email()`
- `delete_content()`
- `add_associations()`
- `remove_associations()`

Each method now follows this pattern:
```python
# Ensure authentication is initialized and token is fresh
if self.auth_type == "bearer":
    if 'Authorization' not in self.headers:
        await self.initialize_auth()
    else:
        await self._refresh_token_if_needed()
elif self.auth_type == "basic":
    await self.initialize_auth()

# Retry logic for 401 errors (token expiration)
max_retries = 1
for attempt in range(max_retries + 1):
    try:
        # Make API call
        response = await client.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        # If 401 and we haven't retried yet, force token refresh and retry
        if e.response.status_code == 401 and attempt < max_retries and self.auth_type == "bearer":
            logger.warning("Received 401 Unauthorized, forcing token refresh and retrying")
            self.token_expiry = datetime.now() - timedelta(hours=1)
            await self._refresh_token_if_needed()
            continue  # Retry the request
        raise
```

### 6. **Retry Mechanism for 401 Errors**
Added automatic retry logic that:
- Catches 401 Unauthorized errors
- Forces immediate token refresh
- Retries the request once with the new token
- Provides a safety net if proactive refresh fails

## Benefits

1. **Automatic Recovery**: Server automatically recovers from token expiration without manual intervention
2. **Proactive Refresh**: Tokens are refreshed 5 minutes before expiry, preventing 401 errors
3. **Reactive Retry**: If a 401 occurs anyway, automatically retry with fresh token
4. **Minimal Overhead**: Token refresh only occurs when needed, not on every request
5. **Enhanced Logging**: All token operations logged with detailed debugging information
6. **Backward Compatible**: Basic authentication continues to work as before
7. **Robust**: Two-layer approach ensures maximum reliability

## Token Expiry Times

| Authentication Type | Default Expiry | Refresh Buffer |
|---------------------|----------------|----------------|
| CP4D                | 1 hour         | 5 minutes      |
| IBM Cloud IAM       | 1 hour         | 5 minutes      |
| MCSP                | 1 hour         | 5 minutes      |
| Basic Auth          | N/A            | N/A            |

## Monitoring

Token refresh operations are logged at various levels:

**DEBUG level** (for detailed troubleshooting):
- "Token expiry check: current={time}, expiry={time}, time_until_expiry={seconds}s"
- "Token is expired or expiring soon (within {seconds}s)"
- "Token expiry not set, considering as expired"

**INFO level** (normal operations):
- "Token expired or expiring soon, refreshing..."
- "Token refreshed successfully"
- "Token will expire at: {timestamp} (in {seconds} seconds)"

**WARNING level** (retry operations):
- "Received 401 Unauthorized, forcing token refresh and retrying (attempt X/Y)"

**ERROR level** (failures):
- "Failed to refresh token: {error}"

## Testing Recommendations

1. **Long-Running Server Test**: Run the server for more than 1 hour and verify it continues to work
2. **Token Expiry Simulation**: Manually set `token_expiry` to a past time and verify refresh occurs
3. **Multiple Requests**: Make multiple API calls over time and verify no 401 errors occur
4. **Log Monitoring**: Check logs for token refresh messages to confirm the mechanism is working
5. **401 Retry Test**: Verify that 401 errors trigger automatic retry with token refresh
6. **Debug Logging**: Enable DEBUG logging to see detailed token expiry checks

## Future Enhancements

1. **Configurable Refresh Buffer**: Allow users to configure the refresh buffer time
2. **Token Caching**: Cache tokens across multiple client instances
3. **Configurable Retry Count**: Allow users to configure the number of retries
4. **Metrics**: Add Prometheus metrics for token refresh operations
5. **Exponential Backoff**: Add exponential backoff for retries

## Related Files

- `src/app/core/openpages_client.py`: Main implementation
- `src/app/config/settings.py`: Configuration settings
- `src/app/mcp/mcp_server.py`: Server initialization

## Updates

### 2026-02-17
- Added enhanced debug logging for token expiry checks
- Implemented automatic retry mechanism for 401 errors
- Added retry logic to `query()` and `create_content()` methods
- Improved error handling and logging

### 2026-02-16
- Initial implementation of token refresh mechanism
- Added token expiration tracking
- Implemented proactive token refresh before API calls