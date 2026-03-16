# User ID Logging Enhancement for OpenPages Operations

## Problem Statement

Currently, the `user_id` field in logs is only populated when clients send the `X-User-ID` header. However, for OpenPages tool and resource operations, we should **automatically extract and log the OpenPages user** from the authentication context, following this precedence:

1. **Context Variable**: `op_username` from tool/resource call context
2. **Basic Auth**: Username from basic authentication credentials
3. **Bearer Auth**: Username extracted from JWT token or fetched via API

## Current Implementation Analysis

### Context Variables Support
- **Location**: [`src/app/mcp/context.py`](../src/app/mcp/context.py)
- **Available**: `op_username` context variable ([line 29](../src/app/mcp/context.py:29))
- **Status**: ✅ Already supported, but not logged automatically

### Authentication Service
- **Location**: [`src/app/auth/service.py`](../src/app/auth/service.py)
- **Current**: Resolves tokens but doesn't extract user identity
- **Status**: ⚠️ Needs enhancement to extract username

### OpenPages Client
- **Location**: [`src/app/core/openpages_client.py`](../src/app/core/openpages_client.py)
- **Current**: Has `username` for basic auth ([line 72](../src/app/core/openpages_client.py:72))
- **Status**: ⚠️ Username available but not exposed for logging

### Tool Handlers
- **Location**: [`src/app/mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py)
- **Current**: Extracts context but doesn't set logging context
- **Status**: ⚠️ Needs to set user_id in logging context

## Implementation Plan

### Phase 1: Extract Username from Authentication

#### 1.1 Enhance AuthResult to Include Username

**File**: `src/app/auth/service.py`

```python
class AuthResult:
    """Encapsulates resolved auth + retry capability + user identity."""

    def __init__(self, token: Optional[str], provider: AuthProvider, username: Optional[str] = None):
        self._token = token
        self.provider = provider
        self.username = username  # NEW: Store username
    
    # ... existing methods ...
```

#### 1.2 Extract Username from Basic Auth

**File**: `src/app/auth/providers.py`

```python
class ServerCredentialProvider(AuthProvider):
    """Provides authentication using server-configured credentials."""
    
    def __init__(self):
        from src.app.config.settings import settings
        self.settings = settings
        self.username = None  # NEW: Store username
    
    async def resolve(self) -> Optional[str]:
        """Returns empty string to signal use of server credentials."""
        # For basic auth, store username
        if self.settings.OPENPAGES_AUTHENTICATION_TYPE == "basic":
            self.username = self.settings.OPENPAGES_USERNAME
        return ""
    
    def get_username(self) -> Optional[str]:
        """Get the username for logging purposes."""
        return self.username
```

#### 1.3 Extract Username from JWT Token

**File**: `src/app/auth/token_utils.py` (NEW FILE)

```python
"""
JWT Token Utilities
Provides functions to decode and extract information from JWT tokens
"""

import jwt
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def decode_jwt_token(token: str, verify: bool = False) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (for extracting claims)
    
    Args:
        token: JWT token string
        verify: Whether to verify signature (default: False for logging purposes)
    
    Returns:
        Dictionary of token claims or None if decoding fails
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        # Decode without verification (we just need the username for logging)
        decoded = jwt.decode(token, options={"verify_signature": verify})
        return decoded
    except Exception as e:
        logger.warning(f"Failed to decode JWT token: {e}")
        return None


def extract_username_from_token(token: str) -> Optional[str]:
    """
    Extract username from JWT token
    
    Tries common JWT claim fields for username:
    - sub (subject)
    - username
    - preferred_username
    - email
    - uid
    
    Args:
        token: JWT token string
    
    Returns:
        Username string or None if not found
    """
    decoded = decode_jwt_token(token)
    if not decoded:
        return None
    
    # Try common username fields in order of preference
    username_fields = ['sub', 'username', 'preferred_username', 'email', 'uid', 'user_id']
    
    for field in username_fields:
        if field in decoded:
            username = decoded[field]
            if username:
                logger.debug(f"Extracted username '{username}' from JWT field '{field}'")
                return str(username)
    
    logger.warning(f"No username found in JWT token. Available fields: {list(decoded.keys())}")
    return None
```

#### 1.4 Fetch Username from OpenPages API (for MCSP)

**File**: `src/app/core/openpages_client.py`

Add new method:

```python
async def get_current_user(self, auth_override: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get current user information from OpenPages API
    
    Args:
        auth_override: Optional authentication override token
    
    Returns:
        Dictionary with user information or None if request fails
    """
    try:
        endpoint = f"{self.base_url}/opgrc/api/v2/users/current"
        
        headers = self.headers.copy()
        if auth_override:
            headers['Authorization'] = f'Bearer {auth_override}'
        
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            
            user_data = response.json()
            logger.debug(f"Fetched current user: {user_data.get('name', 'unknown')}")
            return user_data
    except Exception as e:
        logger.warning(f"Failed to fetch current user: {e}")
        return None


def extract_username_from_user_data(user_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract username from OpenPages user data
    
    Args:
        user_data: User data dictionary from API
    
    Returns:
        Username string or None
    """
    # Try common fields
    for field in ['name', 'username', 'userId', 'email']:
        if field in user_data and user_data[field]:
            return str(user_data[field])
    return None
```

### Phase 2: Update AuthService to Extract Username

**File**: `src/app/auth/service.py`

```python
from src.app.auth.token_utils import extract_username_from_token

class AuthService:
    """Central authentication coordinator with username extraction."""

    def __init__(self, settings, openpages_client=None):
        self.settings = settings
        self.openpages_client = openpages_client

    async def resolve_for_request(
        self,
        context_token: Optional[str] = None,
    ) -> AuthResult:
        """
        Resolve auth for a single tool invocation with username extraction.

        Precedence: context_token > server credentials.

        Args:
            context_token: Token from op_auth_header context variable (WXO flow)

        Returns:
            AuthResult with resolved token, provider, and username
        """
        username = None
        
        if context_token:
            logger.info("Auth resolved via context variable (Passthrough flow)")
            provider = PassthroughTokenProvider(context_token)
            
            # Try to extract username from JWT token
            username = extract_username_from_token(context_token)
            
            # If JWT extraction fails and we have OpenPages client, fetch from API
            if not username and self.openpages_client:
                try:
                    user_data = await self.openpages_client.get_current_user(
                        auth_override=context_token
                    )
                    if user_data:
                        username = extract_username_from_user_data(user_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch username from API: {e}")
        else:
            logger.debug("Auth resolved via server credentials (Fallback flow)")
            provider = ServerCredentialProvider()
            
            # For basic auth, get username from settings
            if self.settings.OPENPAGES_AUTHENTICATION_TYPE == "basic":
                username = self.settings.OPENPAGES_USERNAME
            # For bearer auth with server credentials, try JWT or API
            elif self.settings.OPENPAGES_AUTHENTICATION_TYPE == "bearer":
                # If we have an API key, we might need to fetch user info
                if self.openpages_client:
                    try:
                        user_data = await self.openpages_client.get_current_user()
                        if user_data:
                            username = extract_username_from_user_data(user_data)
                    except Exception as e:
                        logger.warning(f"Failed to fetch username from API: {e}")

        token = await provider.resolve()
        
        if username:
            logger.debug(f"Resolved username: {username}")
        else:
            logger.warning("Could not resolve username from authentication")
        
        return AuthResult(token if token else None, provider, username)
```

### Phase 3: Set User ID in Logging Context

**File**: `src/app/mcp/tool_handlers.py`

```python
from src.app.observability.logger import set_request_context

class ToolHandlers:
    """Handles execution of MCP tools with automatic user logging."""
    
    async def _resolve_auth_and_user(self, context) -> tuple:
        """
        Resolve auth override and set user_id in logging context.

        Returns:
            Tuple of (auth_override_string_or_None, AuthResult_or_None)
        """
        if not self.auth_service:
            return None, None

        # Resolve authentication and get username
        auth_result = await self.auth_service.resolve_for_request(
            context_token=context.op_auth_header,
        )
        
        # Determine user_id with precedence:
        # 1. op_username from context
        # 2. username from auth_result
        user_id = context.op_username or auth_result.username
        
        # Set user_id in logging context for all subsequent logs
        if user_id:
            set_request_context(user_id=user_id)
            logger.info(f"Set user_id in logging context: {user_id}")
        else:
            logger.warning("No user_id available for logging context")
        
        return auth_result.auth_override, auth_result
    
    # Update all tool handler methods to call _resolve_auth_and_user
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call with automatic user logging."""
        
        # Extract context variables
        cleaned_arguments, context = extract_context_from_arguments(arguments)
        
        # Resolve auth and set user_id in logging context
        auth_override, auth_result = await self._resolve_auth_and_user(context)
        
        # Now all subsequent logs will include user_id
        logger.info(f"Executing tool: {tool_name}")
        
        # ... rest of tool execution ...
```

### Phase 4: Update Middleware for HTTP Requests

**File**: `src/app/observability/middleware.py`

```python
class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracking with OpenPages user extraction."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with observability features including user extraction."""
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Extract user and session IDs from headers (existing)
        user_id = request.headers.get("X-User-ID")
        session_id = request.headers.get("X-Session-ID")
        
        # NEW: For OpenPages operations, try to extract user from auth
        if not user_id and request.url.path.startswith("/mcp"):
            # Try to extract from Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header:
                from src.app.auth.token_utils import extract_username_from_token
                user_id = extract_username_from_token(auth_header)
        
        # Set request context for logging
        set_request_context(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
        )
        
        # ... rest of middleware ...
```

## Testing Plan

### Test 1: Context Variable Username

```python
# Test with op_username in context
arguments = {
    "op_username": "testuser@example.com",
    "query": "SELECT * FROM SOXControl"
}

# Expected log:
# {"user_id": "testuser@example.com", "message": "Executing tool: openpages_query"}
```

### Test 2: Basic Auth Username

```bash
# Configure basic auth
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=OpenPagesAdministrator

# Make tool call
# Expected log:
# {"user_id": "OpenPagesAdministrator", "message": "Executing tool: openpages_query"}
```

### Test 3: Bearer Auth with JWT

```bash
# Configure bearer auth with JWT token
OPENPAGES_AUTHENTICATION_TYPE=bearer

# Make tool call with JWT token
# Expected log:
# {"user_id": "user@example.com", "message": "Executing tool: openpages_query"}
```

### Test 4: Bearer Auth with API Fetch

```bash
# Configure MCSP bearer auth
OPENPAGES_AUTHENTICATION_TYPE=bearer
OPENPAGES_APIKEY=...

# Make tool call
# System fetches user from /api/v2/users/current
# Expected log:
# {"user_id": "mcsp_user@ibm.com", "message": "Executing tool: openpages_query"}
```

## Implementation Checklist

- [ ] Create `src/app/auth/token_utils.py` with JWT decoding functions
- [ ] Add `pyjwt` dependency to `requirements.txt`
- [ ] Update `AuthResult` class to include `username` field
- [ ] Update `ServerCredentialProvider` to extract username for basic auth
- [ ] Add `get_current_user()` method to `OpenPagesClient`
- [ ] Update `AuthService.resolve_for_request()` to extract username
- [ ] Update `ToolHandlers._resolve_auth_and_user()` to set logging context
- [ ] Update `ObservabilityMiddleware` to extract user from auth headers
- [ ] Add unit tests for username extraction
- [ ] Add integration tests for all auth types
- [ ] Update documentation

## Dependencies

Add to `requirements.txt`:
```
pyjwt>=2.8.0  # For JWT token decoding
```

## Benefits

1. **Automatic User Tracking**: Every OpenPages operation automatically logs the user
2. **Audit Trail**: Complete audit trail of who performed what operation
3. **Security**: Better security monitoring and compliance
4. **Debugging**: Easier to debug user-specific issues
5. **Precedence Chain**: Flexible user resolution with clear precedence

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

### After Enhancement
```json
{
  "timestamp": "2026-02-24T05:00:00Z",
  "level": "INFO",
  "message": "Executing tool: openpages_query_risks",
  "request_id": "abc-123",
  "user_id": "john.doe@example.com"
}
```

## Precedence Summary

```
User ID Resolution Precedence:
┌─────────────────────────────────────┐
│ 1. op_username (Context Variable)   │ ← Highest Priority
├─────────────────────────────────────┤
│ 2. Basic Auth Username              │
├─────────────────────────────────────┤
│ 3. JWT Token Claims                 │
├─────────────────────────────────────┤
│ 4. OpenPages API /users/current     │ ← Lowest Priority
└─────────────────────────────────────┘
```

---

**Status**: 📋 Implementation Plan  
**Priority**: High  
**Estimated Effort**: 4-6 hours  
**Last Updated**: 2026-02-24