# Authentication Methods

## Overview

The GRC MCP Server implements a **two-layer authentication model**:

1. **Layer 1: MCP Client to MCP Server** - Currently open (no authentication required)
2. **Layer 2: MCP Server to OpenPages** - Fully implemented with multiple methods and advanced features

## Layer 1: MCP Client to MCP Server

The HTTP endpoint at `/mcp` accepts all incoming requests **without authentication**. Security relies on network-level controls (firewalls, VPNs, private networks).

The middleware extracts `X-User-ID` and `X-Session-ID` headers for observability and rate limiting purposes only.

## Layer 2: MCP Server to OpenPages

The server supports **4 authentication methods** with advanced features including automatic token refresh and per-request authentication override.

### Authentication Methods

#### 1. Basic Authentication

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `basic` |
| Required credentials | `OPENPAGES_USERNAME` + `OPENPAGES_PASSWORD` |

The simplest method. On client initialization, an HTTP Basic Auth header is constructed:

```
Authorization: Basic {base64("username:password")}
```

The header is cached and reused for all subsequent API calls.

**Implementation**: `_create_basic_auth_header()` in [`openpages_client.py`](../src/app/core/openpages_client.py)

#### 2. Bearer — IBM Cloud IAM

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `bearer` |
| Required credentials | `OPENPAGES_APIKEY` + `OPENPAGES_AUTHENTICATION_URL` |
| URL detection pattern | `iam.cloud.ibm.com` or `iam.test.cloud.ibm.com` |

**Token exchange flow:**
- **POST** to auth URL with `Content-Type: application/x-www-form-urlencoded`
- Body: `grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}`
- Response JSON field: `access_token`
- Result: `Authorization: Bearer {access_token}`
- SSL verification: always enabled (hardcoded `verify=True`)

#### 3. Bearer — MCSP (Managed Cloud Services Platform)

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `bearer` |
| Required credentials | `OPENPAGES_APIKEY` + `OPENPAGES_AUTHENTICATION_URL` |
| URL detection pattern | `account-iam.platform` or `saas.ibm.com` |

**Token exchange flow:**
- **POST** to auth URL with `Content-Type: application/json`
- Body: `{"apikey": "<api_key>"}`
- Response JSON field: `token` (note: not `access_token`)
- Result: `Authorization: Bearer {token}`
- SSL verification: always enabled (hardcoded `verify=True`)

#### 4. Bearer — CP4D (Cloud Pak for Data)

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `bearer` |
| Required credentials | `OPENPAGES_USERNAME` + `OPENPAGES_PASSWORD` + `OPENPAGES_AUTHENTICATION_URL` |
| URL detection pattern | `/icp4d-api/v1/authorize` |

**Token exchange flow:**
- Uses **username/password** instead of API key
- **POST** to auth URL with `Content-Type: application/json`
- Body: `{"username": "<username>", "password": "<password>"}`
- Response JSON field: `token`
- Result: `Authorization: Bearer {token}`
- SSL verification: **configurable** via `SSL_VERIFY` (often `false` for self-signed certs)
- Special API path construction: appends `-opgrc` instead of `/opgrc`
- Instance name extraction logic from the base URL

## Advanced Features

### Automatic Token Refresh on 401

For bearer authentication methods, the server implements **automatic token refresh** when receiving a 401 Unauthorized response:

**Implementation** ([`openpages_client.py:437-470`](../src/app/core/openpages_client.py)):
- On 401 response, the server automatically:
  1. Acquires an async lock to prevent concurrent refresh attempts
  2. Uses double-checked locking pattern to avoid redundant refreshes
  3. Clears the cached bearer token
  4. Fetches a new token from the authentication endpoint
  5. Updates the cached token
  6. Retries the original request with the new token

**Key features:**
- Thread-safe with async locking (`asyncio.Lock`)
- Prevents token refresh storms with double-checked locking
- Only applies to server-configured credentials (not passthrough tokens)
- Automatic retry happens transparently to the caller

**Code reference:**
```python
if e.response.status_code == 401 and auth_override is None and self.auth_type == "bearer":
    async with self._auth_lock:
        if self.headers.get('Authorization') == token_before_request:
            self._clear_bearer_token()
            self.auth_header = await self._create_bearer_auth_header(...)
            self.headers['Authorization'] = self.auth_header
```

### Per-Request Authentication Override

The server supports **per-request authentication** via the `op_auth_header` context variable, enabling different authentication for each tool call.

**Implementation** ([`tool_handlers.py`](../src/app/mcp/tool_handlers.py) and [`auth/service.py`](../src/app/auth/service.py)):

1. **Context Variable Extraction**: Each tool handler extracts `op_auth_header` from request arguments
2. **Authentication Resolution**: `AuthService.resolve_for_request()` determines which credentials to use:
   - If `op_auth_header` is provided → Use passthrough token (WXO flow)
   - If `op_auth_header` is empty/missing → Use server-configured credentials
3. **Token Validation**: Passthrough tokens are validated for expiry before use
4. **Request Execution**: The resolved auth token is passed as `auth_override` to OpenPages API calls

**Authentication Precedence:**
1. **Passthrough Token** (from `op_auth_header`) - Highest priority
2. **Server Credentials** (from environment variables) - Fallback

**Code flow:**
```python
# In tool handler
cleaned_args, context = extract_context_from_arguments(arguments)
auth_override, auth_result = await self._resolve_auth_override(context)

# In OpenPages client
request_headers = await self._get_request_headers(auth_override)
# If auth_override is provided, it overrides self.headers['Authorization']
```

**Benefits:**
- Enables multi-user scenarios where different users have different permissions
- Supports WXO (Watson Orchestrate) embedded chat scenarios
- Maintains security by validating passthrough tokens
- Falls back gracefully to server credentials when no override is provided

### Token Validation

Passthrough tokens (from `op_auth_header`) are validated before use:

**Implementation** ([`auth/token_validator.py`](../src/app/auth/token_validator.py)):
- Decodes JWT payload without signature verification
- Checks for `exp` (expiration) claim
- Validates token is not expired
- Caches validation results for performance
- Raises `TokenValidationError` if token is expired or malformed

## Authentication Flow

```
MCP Client Request
    │
    ▼
HTTP Router (no auth check)
    │
    ▼
JSON-RPC Request Processing
    │
    ▼
Tool Handler
    │
    ▼
extract_context_from_arguments()
    ├── Extracts: op_auth_header (if present)
    └── Validates: only whitelisted context vars accepted
    │
    ▼
AuthService.resolve_for_request()
    ├── If op_auth_header provided:
    │   ├── Validate token (check expiry)
    │   └── Return PassthroughTokenProvider
    └── Else:
        └── Return ServerCredentialProvider
    │
    ▼
Tool Execution (e.g., GenericObjectTools.upsert_object)
    ├── Receives: auth_override from AuthService
    └── Passes to: OpenPages client
    │
    ▼
OpenPages API Call
    ├── Uses: auth_override if provided
    ├── Else: server-configured credentials
    └── On 401: automatic token refresh (server creds only)
```

## Configuration

### Environment Variables

All authentication settings are managed through [`settings.py`](../src/app/config/settings.py) loaded from `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `"basic"` | `"basic"` or `"bearer"` |
| `OPENPAGES_USERNAME` | `""` | Required for basic and CP4D |
| `OPENPAGES_PASSWORD` | `""` | Required for basic and CP4D |
| `OPENPAGES_APIKEY` | `""` | Required for IBM Cloud IAM and MCSP |
| `OPENPAGES_AUTHENTICATION_URL` | `""` | Required for all bearer methods |
| `OPENPAGES_INSTANCE_NAME` | `""` | Optional, for CP4D deployments |
| `SSL_VERIFY` | `True` | Disable for self-signed certs (CP4D) |
| `OPENPAGES_BASE_URL` | `""` | Full URL including CP4D instance path |

See [`.env.example`](../.env.example) for all available options.

### Example Configurations

#### Basic Authentication
```env
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=admin
OPENPAGES_PASSWORD=your_password
OPENPAGES_BASE_URL=https://openpages.example.com
```

#### IBM Cloud IAM
```env
OPENPAGES_AUTHENTICATION_TYPE=bearer
OPENPAGES_APIKEY=your_api_key
OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token
OPENPAGES_BASE_URL=https://openpages.cloud.ibm.com
```

#### CP4D
```env
OPENPAGES_AUTHENTICATION_TYPE=bearer
OPENPAGES_USERNAME=admin
OPENPAGES_PASSWORD=your_password
OPENPAGES_AUTHENTICATION_URL=https://cpd-instance.example.com/icp4d-api/v1/authorize
OPENPAGES_BASE_URL=https://cpd-instance.example.com
OPENPAGES_INSTANCE_NAME=openpagesinstance-with-25
SSL_VERIFY=False
```

## Summary

| Feature | Status | Implementation |
|---------|--------|----------------|
| **Basic Authentication** | ✅ Fully implemented | Username/password with cached header |
| **Bearer Authentication** | ✅ Fully implemented | IBM Cloud IAM, MCSP, CP4D |
| **Automatic Token Refresh** | ✅ Fully implemented | On 401, with double-checked locking |
| **Per-Request Auth Override** | ✅ Fully implemented | Via `op_auth_header` context variable |
| **Token Validation** | ✅ Fully implemented | JWT expiry checking with caching |
| **Multi-User Support** | ✅ Enabled | Via passthrough tokens |
| **Thread Safety** | ✅ Implemented | Async locks for token operations |

## Code References

| Functionality | File | Key Methods |
|---------------|------|-------------|
| Basic auth header | [`openpages_client.py`](../src/app/core/openpages_client.py) | `_create_basic_auth_header()` |
| Bearer auth header | [`openpages_client.py`](../src/app/core/openpages_client.py) | `_create_bearer_auth_header()` |
| Token refresh | [`openpages_client.py`](../src/app/core/openpages_client.py) | `_request_with_auth_retry()` |
| Auth resolution | [`auth/service.py`](../src/app/auth/service.py) | `resolve_for_request()` |
| Token validation | [`auth/token_validator.py`](../src/app/auth/token_validator.py) | `validate()` |
| Context extraction | [`mcp/context.py`](../src/app/mcp/context.py) | `extract_context_from_arguments()` |
| Tool auth handling | [`mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py) | `_resolve_auth_override()` |
