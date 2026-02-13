# Authentication Methods

## Overview

The GRC MCP Server implements a **two-layer authentication model**. The first layer covers how MCP clients connect to the MCP server itself. The second layer covers how the MCP server authenticates against the IBM OpenPages GRC platform. Currently, only the second layer (server-to-OpenPages) is fully implemented.

## Two-Layer Authentication Model

### Layer 1: MCP Client to MCP Server (Not Implemented)

The HTTP endpoint at `/mcp` (`src/app/mcp/remote/http_router.py`) accepts all incoming requests **without any authentication**. There are no API keys, bearer tokens, or client certificates required. Security relies entirely on network-level controls (firewalls, VPNs, etc.).

The middleware extracts `X-User-ID` and `X-Session-ID` headers for observability and rate limiting, but does not validate them for authentication purposes.

### Layer 2: MCP Server to OpenPages (Fully Implemented)

The OpenPages client (`src/app/core/openpages_client.py`) supports **4 authentication methods** across 2 categories: Basic and Bearer (with 3 bearer variants). Authentication credentials are configured at the server level via environment variables — all MCP clients share the same OpenPages credentials.

## Authentication Methods

### 1. Basic Authentication

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `basic` |
| Required credentials | `OPENPAGES_USERNAME` + `OPENPAGES_PASSWORD` |

The simplest method. On client initialization, an HTTP Basic Auth header is immediately constructed:

```
Authorization: Basic {base64("username:password")}
```

The header is cached in `self.headers` and reused for all subsequent API calls. No token exchange is needed.

**Key code**: `_create_basic_auth_header()` in `openpages_client.py`

### 2. Bearer — IBM Cloud IAM

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `bearer` |
| Required credentials | `OPENPAGES_APIKEY` + `OPENPAGES_AUTHENTICATION_URL` |
| URL detection pattern | `iam.cloud.ibm.com` or `iam.test.cloud.ibm.com` |

Token exchange flow:
- **POST** to auth URL with `Content-Type: application/x-www-form-urlencoded`
- Body: `grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}`
- Response JSON field: `access_token`
- Result: `Authorization: Bearer {access_token}`
- SSL verification: always enabled (hardcoded `verify=True`)

### 3. Bearer — MCSP (Managed Cloud Services Platform)

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `bearer` |
| Required credentials | `OPENPAGES_APIKEY` + `OPENPAGES_AUTHENTICATION_URL` |
| URL detection pattern | `account-iam.platform` or `saas.ibm.com` |

Token exchange flow:
- **POST** to auth URL with `Content-Type: application/json`
- Body: `{"apikey": "<api_key>"}`
- Response JSON field: `token` (note: not `access_token`)
- Result: `Authorization: Bearer {token}`
- SSL verification: always enabled (hardcoded `verify=True`)

### 4. Bearer — CP4D (Cloud Pak for Data)

| Setting | Value |
|---------|-------|
| `OPENPAGES_AUTHENTICATION_TYPE` | `bearer` |
| Required credentials | `OPENPAGES_USERNAME` + `OPENPAGES_PASSWORD` + `OPENPAGES_AUTHENTICATION_URL` |
| URL detection pattern | `/icp4d-api/v1/authorize` or `cpd-` |

This is the most complex method. Key differences from the other bearer flows:
- Uses **username/password** instead of API key
- **POST** to auth URL with `Content-Type: application/json`
- Body: `{"username": "<username>", "password": "<password>"}`
- Response JSON field: `token`
- Result: `Authorization: Bearer {token}`
- SSL verification: **configurable** via `SSL_VERIFY` (often `false` for self-signed certs)
- Special API path construction: appends `-opgrc` instead of `/opgrc`
- Instance name extraction logic from the base URL

## Lazy Bearer Token Initialization

For all three bearer methods, the token exchange does **not** happen at startup. Instead, `initialize_auth()` is called lazily before the first API request (e.g., in the `query()` method). The token is then cached in `self.headers['Authorization']` for subsequent calls.

There is **no token refresh/expiry logic** — once a token is fetched, it is used until the server restarts.

## Context Variable: `op_auth_header`

The context variables system (`src/app/mcp/context.py`) defines `op_auth_header` as a whitelisted context variable. MCP clients can pass it as part of tool arguments, and it gets extracted by `extract_context_from_arguments()` in every tool handler.

**However, it is currently not used.** The extracted `context.op_auth_header` value is logged at DEBUG level but never injected into the OpenPages client's headers. All tool executions use the server-configured credentials regardless of what `op_auth_header` the client sends.

This appears to be scaffolding for a future per-request auth override capability on the `auth-framework-dev` branch.

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
Tool Execution (e.g., GenericObjectTools.upsert_object)
    ├── Uses: self.client (configured with server auth)
    └── Ignores: context.op_auth_header (not implemented)
    │
    ▼
OpenPages API Call
    └── Authorization: [Server-configured header]
```

## Summary Table

| Method | Auth Type Setting | Credentials Needed | Detection | Token Field | SSL Configurable |
|--------|-------------------|-------------------|-----------|-------------|------------------|
| **Basic** | `basic` | username + password | Explicit | N/A (no exchange) | Yes |
| **IBM Cloud IAM** | `bearer` | apikey + auth URL | `iam.cloud.ibm.com` in URL | `access_token` | No (always on) |
| **MCSP** | `bearer` | apikey + auth URL | `account-iam.platform` / `saas.ibm.com` in URL | `token` | No (always on) |
| **CP4D** | `bearer` | username + password + auth URL | `/icp4d-api/v1/authorize` / `cpd-` in URL | `token` | Yes |

## Configuration Reference

All authentication settings are managed through Pydantic Settings (`src/app/config/settings.py`) loaded from the `.env` file at project root.

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

See `.env.example` for all available options.

## Key Code References

| Functionality | File | Method |
|---------------|------|--------|
| Basic auth header | `src/app/core/openpages_client.py` | `_create_basic_auth_header()` |
| Bearer auth header | `src/app/core/openpages_client.py` | `_create_bearer_auth_header()` |
| Auth type detection | `src/app/core/openpages_client.py` | `_detect_auth_type()` |
| Token fetching | `src/app/core/openpages_client.py` | `fetch_token()` |
| Async auth init | `src/app/core/openpages_client.py` | `initialize_auth()` |
| CP4D instance name | `src/app/core/openpages_client.py` | `_extract_instance_name()` |
| API path construction | `src/app/core/openpages_client.py` | `_get_api_path()` |
| Settings | `src/app/config/settings.py` | `Settings` class |
| Context variables | `src/app/mcp/context.py` | `ALLOWED_CONTEXT_VARIABLES`, `op_auth_header` |
| Context extraction | `src/app/mcp/context.py` | `extract_context_from_arguments()` |
| Tool context usage | `src/app/mcp/tool_handlers.py` | All handler methods |
