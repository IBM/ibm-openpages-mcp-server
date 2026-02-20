# Token Refresh Fix - February 17, 2026

## Issue Reproduced
After the initial token refresh implementation on 2026-02-16, the 401 Unauthorized error was reproduced again on 2026-02-17 after a long idle period.

## Root Cause Analysis

### Logs Analysis
```
"Auth already initialized or using basic auth (type: bearer)"
```

The logs showed that:
1. The token refresh code WAS deployed
2. The `_refresh_token_if_needed()` method was being called
3. However, `_is_token_expired()` was returning `False` even though the token was actually expired
4. This caused the 401 error to occur because the expired token was still being used

### The Problem
The token expiry check in `_is_token_expired()` was not working correctly. Possible reasons:
- Timezone issues between when token was fetched and when it's checked
- The comparison `time_until_expiry <= self.token_refresh_buffer` was not detecting expired tokens
- No visibility into why the check was failing (insufficient logging)

## Solution Implemented

### 1. Enhanced Debug Logging
Added detailed logging to `_is_token_expired()` to track:
- Current time
- Token expiry time
- Time until expiry in seconds
- Refresh buffer in seconds
- Whether token is considered expired

This helps diagnose why token expiry detection might fail.

### 2. Automatic Retry Mechanism (Safety Net)
Implemented a retry mechanism that catches 401 errors and automatically:
1. Detects 401 Unauthorized response
2. Forces token refresh by setting `token_expiry` to the past
3. Calls `_refresh_token_if_needed()` to get a new token
4. Retries the request with the fresh token
5. Logs the retry attempt for monitoring

This provides a **safety net** in case the proactive token refresh fails for any reason.

### 3. Applied to Critical Methods
Added retry logic to:
- `query()` - Most frequently used method
- `create_content()` - Critical for creating objects

## Code Changes

### Enhanced Token Expiry Check
```python
def _is_token_expired(self) -> bool:
    if self.token_expiry is None:
        logger.debug("Token expiry not set, considering as expired")
        return True
    
    current_time = datetime.now()
    time_until_expiry = self.token_expiry - current_time
    
    # Log the comparison for debugging
    logger.debug(f"Token expiry check: current={current_time}, expiry={self.token_expiry}, "
                 f"time_until_expiry={time_until_expiry.total_seconds()}s, "
                 f"buffer={self.token_refresh_buffer.total_seconds()}s")
    
    is_expired = time_until_expiry <= self.token_refresh_buffer
    if is_expired:
        logger.debug(f"Token is expired or expiring soon")
    
    return is_expired
```

### Retry Mechanism Pattern
```python
# Retry logic for 401 errors (token expiration)
max_retries = 1
last_error = None

for attempt in range(max_retries + 1):
    async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
        try:
            response = await client.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            last_error = e
            # If 401 and we haven't retried yet, force token refresh and retry
            if e.response.status_code == 401 and attempt < max_retries and self.auth_type == "bearer":
                logger.warning(f"Received 401 Unauthorized, forcing token refresh and retrying "
                              f"(attempt {attempt + 1}/{max_retries + 1})")
                # Force token refresh by setting expiry to past
                self.token_expiry = datetime.now() - timedelta(hours=1)
                await self._refresh_token_if_needed()
                continue  # Retry the request
            raise

# If we exhausted retries, raise the last error
if last_error:
    raise last_error
```

## Expected Behavior After Fix

### Normal Operation (Proactive Refresh)
1. Before each API call, check if token will expire within 5 minutes
2. If yes, refresh token proactively
3. Make API call with fresh token
4. No 401 errors occur

### Fallback Operation (Reactive Retry)
1. If proactive refresh fails or token expires unexpectedly
2. API call returns 401 Unauthorized
3. Automatically force token refresh
4. Retry the API call with fresh token
5. Request succeeds on retry

### Logging
You should see these messages in the logs:

**DEBUG level** (when token expiry is checked):
```
Token expiry check: current=2026-02-17 10:00:00, expiry=2026-02-17 10:03:00, 
time_until_expiry=180s, buffer=300s
Token is expired or expiring soon (within 300s)
```

**INFO level** (when token is refreshed):
```
Token expired or expiring soon, refreshing...
Token refreshed successfully
Token will expire at: 2026-02-17 11:00:00 (in 3600 seconds)
```

**WARNING level** (when 401 triggers retry):
```
Received 401 Unauthorized, forcing token refresh and retrying (attempt 1/2)
```

## Deployment Instructions

1. **Rebuild Docker image** with the updated code:
   ```bash
   docker-compose build
   ```

2. **Restart the container**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Verify deployment** by checking logs for the new debug messages

4. **Monitor for 401 errors** - they should no longer occur, or if they do, should be automatically retried

## Testing

### Enable Debug Logging
To see detailed token expiry checks, set log level to DEBUG in your environment:
```bash
LOG_LEVEL=DEBUG
```

### Simulate Token Expiry
You can test the retry mechanism by:
1. Letting the server run for more than 1 hour
2. Making an API call
3. Checking logs for retry messages if a 401 occurs

### Expected Results
- No 401 errors in normal operation
- If a 401 occurs, it should be automatically retried and succeed
- Detailed logging shows token expiry checks and refresh operations

## Files Modified

1. `src/app/core/openpages_client.py`
   - Enhanced `_is_token_expired()` with debug logging
   - Added retry mechanism to `create_content()`
   - Added retry mechanism to `query()`

2. `docs/TOKEN_REFRESH_IMPLEMENTATION.md`
   - Updated with retry mechanism documentation
   - Added enhanced logging details
   - Updated testing recommendations

3. `docs/TOKEN_REFRESH_FIX_2026-02-17.md` (this file)
   - Documented the issue and fix

## Conclusion

This fix provides a **two-layer defense** against token expiration:
1. **Proactive**: Check and refresh before each call
2. **Reactive**: Catch 401 errors and retry with fresh token

The enhanced logging will help diagnose any future issues with token expiry detection.

## Date
2026-02-17