# User ID Logging Fix - Final Implementation

## Issue
The user_id logging implementation was incomplete - the `handle_call_tool` method was missing the code to extract and log user identity.

## Root Causes
1. The implementation added the `_resolve_auth_and_user()` helper method but forgot to call it in the main `handle_call_tool` method where all tool executions flow through.
2. The initial fix had the wrong precedence - it was looking for `op_username` in `_meta` context variables instead of directly in the tool arguments.
3. The logic needed to check `arguments.get("op_username")` first before falling back to authentication-based username extraction.

## Fix Applied
Added the following code to [`src/app/mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py:1236) in the `handle_call_tool` method:

```python
# Resolve authentication and extract user identity for logging
# Precedence: 1) op_username from arguments, 2) JWT token, 3) Basic auth
user_id = None
try:
    # 1. First check for op_username directly in arguments (highest priority)
    user_id = arguments.get("op_username")
    
    if user_id:
        logger.debug(f"Using op_username from arguments: {user_id}")
    else:
        # 2. Try to extract from authentication (JWT or Basic auth)
        context = extract_context_from_arguments(arguments)
        auth_override, auth_result = await self._resolve_auth_and_user(context)
        
        if auth_result and auth_result.username:
            user_id = auth_result.username
            logger.debug(f"Extracted username from auth: {user_id}")
    
    # Set user_id in logging context for all subsequent logs
    if user_id:
        set_request_context(user_id=user_id)
        logger.info(f"Auth resolved for tool '{name}': user_id={user_id}")
    else:
        logger.debug(f"No username available for tool '{name}'")
        
except Exception as e:
    logger.warning(f"Failed to extract user identity for logging: {e}")
```

**Key Points:**
- **Priority 1**: Checks `arguments.get("op_username")` first - this is the explicit user override
- **Priority 2**: Falls back to JWT token username extraction if bearer auth is used
- **Priority 3**: Falls back to basic auth username if basic auth is used
- Sets the user_id in logging context using `set_request_context(user_id=...)`
- Logs confirmation when user_id is successfully set

## Testing Steps

### 1. Install PyJWT (if not already installed)
```bash
pip install PyJWT>=2.8.0
```

### 2. Restart the Server
The server must be restarted to load the new code:
```bash
# Stop the current server (Ctrl+C)
# Then restart it
python main.py
```

### 3. Test with Bearer Token Authentication
Make a tool call with bearer token authentication. The logs should now show:
```json
{
  "timestamp": "...",
  "level": "INFO",
  "message": "Auth resolved for tool 'openpages_upsert_object': user_id=john.doe@example.com",
  "user_id": "john.doe@example.com",
  ...
}
```

### 4. Test with op_username Parameter (Highest Priority)
Pass `op_username` **directly in the tool arguments** (not in `_meta`):
```json
{
  "method": "tools/call",
  "params": {
    "name": "openpages_query_controls",
    "arguments": {
      "name": "control",
      "op_username": "jaynair"
    }
  }
}
```

Expected log output:
```json
{
  "timestamp": "...",
  "level": "INFO",
  "message": "Auth resolved for tool 'openpages_upsert_object': user_id=admin@openpages.com",
  "user_id": "admin@openpages.com",
  ...
}
```

### 5. Test with Basic Authentication
If using basic auth, the username from the Authorization header should be logged:
```json
{
  "timestamp": "...",
  "level": "INFO",
  "message": "Auth resolved for tool 'openpages_upsert_object': user_id=basicuser",
  "user_id": "basicuser",
  ...
}
```

## Expected Behavior

After the fix, **every tool call** should log the user_id using this precedence:

1. **op_username Parameter (Highest Priority)**: If `op_username` is passed directly in tool arguments, it will be used
   - Example: `"arguments": {"name": "control", "op_username": "jaynair"}`
2. **JWT Token**: If bearer token authentication is used, username is extracted from the token
3. **Basic Auth**: If basic authentication is used, username is extracted from the Authorization header
4. **No User**: If none of the above are available, no user_id will be logged (but a debug message will indicate this)

## Verification

Check the logs for:
- ✅ `"Auth resolved for tool"` message with user_id
- ✅ `"user_id": "..."` field in all subsequent log entries for that request
- ✅ User identity appears in OpenPages API calls, tool executions, and error logs

## Files Modified
- [`src/app/mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py) - Added user identity extraction in `handle_call_tool`

## Related Documentation
- [User ID Logging Implementation Summary](USER_ID_LOGGING_IMPLEMENTATION_SUMMARY.md)
- [User ID Logging Enhancement Plan](USER_ID_LOGGING_ENHANCEMENT.md)
- [Observability Testing Guide](OBSERVABILITY_TESTING_GUIDE.md)