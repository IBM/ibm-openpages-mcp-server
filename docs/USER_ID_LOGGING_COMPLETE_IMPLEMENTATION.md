# User ID Logging - Complete Implementation Summary

## Overview
The user_id logging feature extracts and logs the OpenPages username for every tool call using a three-tier precedence system.

## Implementation Details

### Precedence Chain (Priority Order)

#### 1. **op_username Parameter** (Highest Priority)
**Location**: [`src/app/mcp/tool_handlers.py:1239`](../src/app/mcp/tool_handlers.py:1239)

```python
# Check for op_username directly in arguments
user_id = arguments.get("op_username")
```

**Usage Example**:
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

**When Used**: When the client explicitly provides a username override in the tool arguments.

---

#### 2. **Basic Authentication Username** (Medium Priority)
**Location**: [`src/app/auth/providers.py:66-82`](../src/app/auth/providers.py:66)

```python
class ServerCredentialProvider(AuthProvider):
    async def resolve(self) -> str:
        # Store username for basic auth
        if self.settings.OPENPAGES_AUTHENTICATION_TYPE == "basic":
            self.username = self.settings.OPENPAGES_USERNAME
            logger.debug(f"Extracted username from basic auth: {self.username}")
        return ""
    
    def get_username(self) -> Optional[str]:
        """Get the username for logging purposes."""
        return self.username
```

**How It Works**:
1. When no `op_username` is provided in arguments
2. And authentication type is "basic"
3. The username is extracted from `OPENPAGES_USERNAME` environment variable
4. Retrieved via `provider.get_username()` in [`src/app/auth/service.py:100-103`](../src/app/auth/service.py:100)

**Configuration**:
```bash
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=admin
OPENPAGES_PASSWORD=password
```

---

#### 3. **JWT Token Username** (Low Priority)
**Location**: [`src/app/auth/token_utils.py:44-88`](../src/app/auth/token_utils.py:44)

```python
def extract_username_from_token(token: str) -> Optional[str]:
    """
    Extract username from JWT token
    
    Tries common JWT claim fields in order:
    - sub (subject) - standard JWT claim
    - username - common custom claim
    - preferred_username - OIDC standard claim
    - email - email address as username
    - uid - user ID
    - user_id - alternative user ID field
    - name - full name
    """
    decoded = decode_jwt_token(token)
    if not decoded:
        return None
    
    username_fields = ['sub', 'username', 'preferred_username', 
                       'email', 'uid', 'user_id', 'name']
    
    for field in username_fields:
        if field in decoded and decoded[field]:
            return str(decoded[field])
    
    return None
```

**How It Works**:
1. When no `op_username` is provided in arguments
2. And authentication type is "bearer"
3. The JWT token is decoded (without signature verification)
4. Username is extracted from standard JWT claims
5. Called from [`src/app/auth/service.py:89-94`](../src/app/auth/service.py:89)

**Supported JWT Claims** (in order of preference):
- `sub` - Standard JWT subject claim
- `username` - Common custom claim
- `preferred_username` - OIDC standard
- `email` - Email address
- `uid` - User ID
- `user_id` - Alternative user ID
- `name` - Full name

**Configuration**:
```bash
OPENPAGES_AUTHENTICATION_TYPE=bearer
OPENPAGES_API_KEY=your-api-key
```

---

## Complete Flow Diagram

```
Tool Call Received
    ↓
Check arguments.get("op_username")
    ↓
    ├─ Found? → Use it (Priority 1) ✓
    ↓
    └─ Not Found → Check Authentication Type
        ↓
        ├─ Basic Auth?
        │   ↓
        │   └─ Extract from OPENPAGES_USERNAME (Priority 2) ✓
        ↓
        └─ Bearer Auth?
            ↓
            └─ Decode JWT token
                ↓
                └─ Extract from JWT claims (Priority 3) ✓
                    ↓
                    └─ Try: sub, username, preferred_username, 
                           email, uid, user_id, name
```

## Code Integration Points

### 1. Tool Handler Entry Point
**File**: [`src/app/mcp/tool_handlers.py:1236-1260`](../src/app/mcp/tool_handlers.py:1236)

```python
async def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
    # ... tool name extraction ...
    
    # Resolve authentication and extract user identity for logging
    user_id = None
    try:
        # Priority 1: Check op_username in arguments
        user_id = arguments.get("op_username")
        
        if user_id:
            logger.debug(f"Using op_username from arguments: {user_id}")
        else:
            # Priority 2 & 3: Extract from authentication
            context = extract_context_from_arguments(arguments)
            auth_override, auth_result = await self._resolve_auth_and_user(context)
            
            if auth_result and auth_result.username:
                user_id = auth_result.username
                logger.debug(f"Extracted username from auth: {user_id}")
        
        # Set user_id in logging context
        if user_id:
            set_request_context(user_id=user_id)
            logger.info(f"Auth resolved for tool '{name}': user_id={user_id}")
    except Exception as e:
        logger.warning(f"Failed to extract user identity for logging: {e}")
```

### 2. Authentication Service
**File**: [`src/app/auth/service.py:75-112`](../src/app/auth/service.py:75)

Handles Priority 2 & 3 by:
- Extracting username from JWT tokens (bearer auth)
- Extracting username from basic auth credentials
- Returning `AuthResult` with username field

### 3. JWT Token Utilities
**File**: [`src/app/auth/token_utils.py`](../src/app/auth/token_utils.py)

Provides:
- `decode_jwt_token()` - Decodes JWT without verification
- `extract_username_from_token()` - Extracts username from JWT claims
- `extract_username_from_user_data()` - Extracts from API responses (future use)

### 4. Authentication Providers
**File**: [`src/app/auth/providers.py`](../src/app/auth/providers.py)

Implements:
- `ServerCredentialProvider.get_username()` - Returns basic auth username
- `PassthroughTokenProvider` - Handles bearer token passthrough

## Testing Each Priority Level

### Test Priority 1: op_username Parameter
```bash
# Request with explicit username
curl -X POST http://localhost:8025/mcp/v1/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "openpages_query_controls",
      "arguments": {
        "name": "control",
        "op_username": "jaynair"
      }
    },
    "id": 1
  }'
```

**Expected Log**:
```json
{"message": "Using op_username from arguments: jaynair", ...}
{"message": "Auth resolved for tool 'openpages_query_controls': user_id=jaynair", "user_id": "jaynair", ...}
```

### Test Priority 2: Basic Auth
```bash
# Set environment variables
export OPENPAGES_AUTHENTICATION_TYPE=basic
export OPENPAGES_USERNAME=admin
export OPENPAGES_PASSWORD=password

# Make request without op_username
curl -X POST http://localhost:8025/mcp/v1/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "openpages_query_controls",
      "arguments": {
        "name": "control"
      }
    },
    "id": 1
  }'
```

**Expected Log**:
```json
{"message": "Extracted username from basic auth: admin", ...}
{"message": "Extracted username from auth: admin", ...}
{"message": "Auth resolved for tool 'openpages_query_controls': user_id=admin", "user_id": "admin", ...}
```

### Test Priority 3: JWT Token
```bash
# Set environment variables
export OPENPAGES_AUTHENTICATION_TYPE=bearer
export OPENPAGES_API_KEY=your-api-key

# Make request with bearer token (token should contain username in JWT claims)
curl -X POST http://localhost:8025/mcp/v1/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGc..." \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "openpages_query_controls",
      "arguments": {
        "name": "control"
      }
    },
    "id": 1
  }'
```

**Expected Log**:
```json
{"message": "Extracted username 'john.doe' from JWT field 'sub'", ...}
{"message": "Extracted username from auth: john.doe", ...}
{"message": "Auth resolved for tool 'openpages_query_controls': user_id=john.doe", "user_id": "john.doe", ...}
```

## Dependencies

### Required Package
```bash
pip install PyJWT>=2.8.0
```

### Environment Variables
```bash
# For Basic Auth (Priority 2)
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=admin
OPENPAGES_PASSWORD=password

# For Bearer Auth (Priority 3)
OPENPAGES_AUTHENTICATION_TYPE=bearer
OPENPAGES_API_KEY=your-api-key
```

## Logging Context

Once `user_id` is set via `set_request_context(user_id=...)`, it appears in **all subsequent log entries** for that request:

```json
{"timestamp": "...", "message": "Handling call_tool request", "user_id": "jaynair", ...}
{"timestamp": "...", "message": "Executing query operation", "user_id": "jaynair", ...}
{"timestamp": "...", "message": "OpenPages API Query Request", "user_id": "jaynair", ...}
{"timestamp": "...", "message": "Query completed successfully", "user_id": "jaynair", ...}
```

## Related Documentation
- [User ID Logging Fix](USER_ID_LOGGING_FIX.md) - Implementation fix details
- [User ID Logging Enhancement](USER_ID_LOGGING_ENHANCEMENT.md) - Original enhancement plan
- [Observability Testing Guide](OBSERVABILITY_TESTING_GUIDE.md) - Complete observability testing
- [Authentication Methods](AUTHENTICATION_METHODS.md) - Authentication configuration

## Summary

✅ **Priority 1**: `op_username` parameter - Implemented in [`tool_handlers.py:1239`](../src/app/mcp/tool_handlers.py:1239)
✅ **Priority 2**: Basic auth username - Implemented in [`providers.py:66-82`](../src/app/auth/providers.py:66)
✅ **Priority 3**: JWT token username - Implemented in [`token_utils.py:44-88`](../src/app/auth/token_utils.py:44)

All three priority levels are fully implemented and working together in the precedence chain.