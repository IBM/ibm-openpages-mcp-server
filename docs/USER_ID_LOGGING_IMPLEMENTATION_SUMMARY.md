# User ID Logging Implementation Summary

## Overview

Successfully implemented automatic user ID extraction and logging for all OpenPages operations. The system now automatically logs the OpenPages user for every tool/resource call, following a clear precedence chain.

## Implementation Date
2026-02-24

## Changes Made

### 1. Created JWT Token Utilities Module
**File**: [`src/app/auth/token_utils.py`](../src/app/auth/token_utils.py)

**Functions**:
- `decode_jwt_token(token, verify=False)`: Decodes JWT tokens without verification
- `extract_username_from_token(token)`: Extracts username from JWT claims (sub, username, email, etc.)
- `extract_username_from_user_data(user_data)`: Extracts username from OpenPages API user data

**Dependencies Added**: `PyJWT>=2.8.0` in [`requirements.txt`](../requirements.txt)

### 2. Enhanced Authentication Classes

#### AuthResult Class
**File**: [`src/app/auth/service.py`](../src/app/auth/service.py:20-26)

**Changes**:
- Added `username` parameter to `__init__`
- Now stores extracted username for logging purposes

```python
class AuthResult:
    def __init__(self, token: Optional[str], provider: AuthProvider, username: Optional[str] = None):
        self._token = token
        self.provider = provider
        self.username = username  # NEW
```

#### ServerCredentialProvider Class
**File**: [`src/app/auth/providers.py`](../src/app/auth/providers.py:53-78)

**Changes**:
- Added `__init__` method to store settings
- Extracts username from `OPENPAGES_USERNAME` for basic auth
- Added `get_username()` method

```python
class ServerCredentialProvider(AuthProvider):
    def __init__(self):
        from src.app.config.settings import settings
        self.settings = settings
        self.username = None

    async def resolve(self) -> str:
        # Store username for basic auth
        if self.settings.OPENPAGES_AUTHENTICATION_TYPE == "basic":
            self.username = self.settings.OPENPAGES_USERNAME
        return ""
    
    def get_username(self) -> Optional[str]:
        return self.username
```

### 3. Updated AuthService

**File**: [`src/app/auth/service.py`](../src/app/auth/service.py:61-107)

**Changes**:
- Imports `extract_username_from_token` from token_utils
- Extracts username from JWT tokens (passthrough auth)
- Extracts username from basic auth credentials (server auth)
- Returns `AuthResult` with username included

**Username Extraction Logic**:
1. **Passthrough Auth**: Extract from JWT token claims
2. **Server Auth**: Get from `ServerCredentialProvider.get_username()`

### 4. Updated ToolHandlers

**File**: [`src/app/mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py:61-103)

**Changes**:
- Imports `set_request_context` from observability logger
- Renamed `_resolve_auth_override` to `_resolve_auth_and_user`
- Sets `user_id` in logging context with precedence:
  1. `op_username` from context variable (highest priority)
  2. `username` from `AuthResult` (from JWT or basic auth)
- Kept old method name for backward compatibility

**Key Code**:
```python
async def _resolve_auth_and_user(self, context) -> tuple:
    auth_result = await self.auth_service.resolve_for_request(
        context_token=context.op_auth_header,
    )
    
    # Precedence: op_username > auth_result.username
    user_id = context.op_username or auth_result.username
    
    if user_id:
        set_request_context(user_id=user_id)
        logger.info(f"Set user_id in logging context: {user_id}")
    
    return auth_result.auth_override, auth_result
```

### 5. Updated ObservabilityMiddleware

**File**: [`src/app/observability/middleware.py`](../src/app/observability/middleware.py:19-26, 244-251)

**Changes**:
- Imports `extract_username_from_token` with error handling
- For `/mcp` endpoints, extracts username from `Authorization` header if `X-User-ID` not present
- Sets extracted username in logging context

**Key Code**:
```python
# For OpenPages MCP operations, try to extract user from Authorization header
if not user_id and request.url.path.startswith("/mcp") and TOKEN_UTILS_AVAILABLE and _extract_username:
    auth_header = request.headers.get("Authorization")
    if auth_header:
        extracted_user = _extract_username(auth_header)
        if extracted_user:
            user_id = extracted_user
            logger.debug(f"Extracted user_id from Authorization header: {user_id}")
```

### 6. Created Test Suite

**File**: [`tests/test_user_id_logging.py`](../tests/test_user_id_logging.py)

**Test Classes**:
- `TestJWTUsernameExtraction`: Tests JWT token parsing
- `TestUserDataExtraction`: Tests user data parsing
- `TestBasicAuthUsernameExtraction`: Tests basic auth username extraction
- `TestAuthServiceUsernameExtraction`: Tests end-to-end username extraction

## User ID Precedence Chain

```
┌─────────────────────────────────────────┐
│ 1. op_username (Context Variable)       │ ← Highest Priority
│    - Explicitly provided by client      │
│    - Tool/resource call parameter       │
├─────────────────────────────────────────┤
│ 2. JWT Token Claims                     │
│    - Extracted from Bearer token        │
│    - Fields: sub, username, email, etc. │
├─────────────────────────────────────────┤
│ 3. Basic Auth Username                  │
│    - From OPENPAGES_USERNAME setting    │
│    - Server-configured credentials      │
└─────────────────────────────────────────┘
```

## How It Works

### For Tool/Resource Calls

1. **Client makes MCP tool call** (e.g., `openpages_query_risks`)
2. **ToolHandlers extracts context** from arguments
3. **AuthService resolves authentication**:
   - If `op_auth_header` present: Extract username from JWT
   - If basic auth: Get username from settings
4. **ToolHandlers sets logging context**: `set_request_context(user_id=username)`
5. **All subsequent logs include `user_id`**

### For HTTP Requests

1. **Client makes HTTP request** to `/mcp` endpoint
2. **ObservabilityMiddleware intercepts request**
3. **Checks for `X-User-ID` header** (explicit user ID)
4. **If not present, extracts from `Authorization` header** (JWT token)
5. **Sets logging context** with extracted user_id
6. **All logs for this request include `user_id`**

## Example Log Output

### Before Enhancement
```json
{
  "timestamp": "2026-02-24T05:00:00Z",
  "level": "INFO",
  "message": "Executing tool: openpages_query_risks",
  "request_id": "abc-123"
}
```

### After Enhancement - Basic Auth
```json
{
  "timestamp": "2026-02-24T05:00:00Z",
  "level": "INFO",
  "message": "Executing tool: openpages_query_risks",
  "request_id": "abc-123",
  "user_id": "OpenPagesAdministrator"
}
```

### After Enhancement - JWT Token
```json
{
  "timestamp": "2026-02-24T05:00:00Z",
  "level": "INFO",
  "message": "Executing tool: openpages_query_risks",
  "request_id": "abc-123",
  "user_id": "john.doe@example.com"
}
```

### After Enhancement - Context Variable
```json
{
  "timestamp": "2026-02-24T05:00:00Z",
  "level": "INFO",
  "message": "Executing tool: openpages_query_risks",
  "request_id": "abc-123",
  "user_id": "custom.user@example.com"
}
```

## Testing

### Run Unit Tests
```bash
# Install PyJWT first
pip install PyJWT>=2.8.0

# Run tests
pytest tests/test_user_id_logging.py -v
```

### Manual Testing

#### Test 1: Basic Auth
```bash
# Configure basic auth in .env
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=TestUser
OPENPAGES_PASSWORD=password

# Start server
python main.py

# Make tool call - check logs for user_id=TestUser
```

#### Test 2: JWT Token
```bash
# Configure bearer auth
OPENPAGES_AUTHENTICATION_TYPE=bearer

# Make request with JWT token
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/call","params":{"name":"openpages_query_risks"}}'

# Check logs for extracted user_id from JWT
```

#### Test 3: Context Variable
```bash
# Make tool call with op_username
{
  "method": "tools/call",
  "params": {
    "name": "openpages_query_risks",
    "arguments": {
      "op_username": "explicit.user@example.com",
      "query": "SELECT * FROM SOXRisk"
    }
  }
}

# Check logs for user_id=explicit.user@example.com
```

## Benefits

1. ✅ **Automatic Audit Trail**: Every OpenPages operation logs the user
2. ✅ **Security Compliance**: Complete user tracking for compliance
3. ✅ **Better Debugging**: Easier to debug user-specific issues
4. ✅ **No Client Changes**: Works automatically with existing clients
5. ✅ **Flexible Precedence**: Clear priority chain for user resolution
6. ✅ **Multiple Auth Types**: Supports basic auth, JWT, and explicit context

## Files Modified

1. [`src/app/auth/token_utils.py`](../src/app/auth/token_utils.py) - NEW
2. [`requirements.txt`](../requirements.txt) - Added PyJWT
3. [`src/app/auth/service.py`](../src/app/auth/service.py) - Enhanced AuthResult and AuthService
4. [`src/app/auth/providers.py`](../src/app/auth/providers.py) - Enhanced ServerCredentialProvider
5. [`src/app/mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py) - Added user context setting
6. [`src/app/observability/middleware.py`](../src/app/observability/middleware.py) - Added JWT extraction
7. [`tests/test_user_id_logging.py`](../tests/test_user_id_logging.py) - NEW

## Next Steps

1. Install PyJWT: `pip install -r requirements.txt`
2. Run tests: `pytest tests/test_user_id_logging.py -v`
3. Test with your OpenPages environment
4. Monitor logs to verify user_id appears correctly
5. Update any monitoring dashboards to use user_id field

## Troubleshooting

### User ID Not Appearing

**Check**:
1. PyJWT installed: `pip list | grep PyJWT`
2. Authentication type configured correctly
3. For JWT: Token is valid JWT format
4. For basic auth: `OPENPAGES_USERNAME` is set
5. Check logs for warnings about username extraction

### JWT Decoding Fails

**Possible Causes**:
- Token is not a JWT (e.g., API key)
- Token format is invalid
- Token is encrypted (not supported)

**Solution**: System will log warning and continue without user_id

### Basic Auth Username Not Extracted

**Check**:
- `OPENPAGES_AUTHENTICATION_TYPE=basic` in .env
- `OPENPAGES_USERNAME` is set
- ServerCredentialProvider is being used

## Related Documentation

- [Observability Testing Guide](./OBSERVABILITY_TESTING_GUIDE.md)
- [Logging Review and Testing](./LOGGING_REVIEW_AND_TESTING.md)
- [User ID Logging Enhancement Plan](./USER_ID_LOGGING_ENHANCEMENT.md)

---

**Implementation Status**: ✅ Complete  
**Last Updated**: 2026-02-24  
**Implemented By**: Bob (AI Assistant)