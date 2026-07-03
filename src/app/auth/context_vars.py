"""
Auth Context Variables Module

Request-scoped ContextVars for passing transport-level authentication artifacts
(HTTP headers) from the ingress layer to the tool handlers without exposing them
on the agent/LLM tool-argument surface.

Set by the HTTP ingress (`http_router`), read by `tool_handlers` during request
processing:
- `auth_authorization_var`  — type 1: raw HTTP `Authorization` header value.
- `auth_apikey_var`         — type 3: raw value of the configured API-key header
                              (default `X-Api-Key`).

The `op_auth_header` (type 2) and `op_auth_ticket` (type 4) artifacts arrive as
context-var tool arguments instead and are handled via `mcp/context.py`.
"""

from contextvars import ContextVar
from typing import Optional

# Type 1 — raw HTTP Authorization header captured at ingress (remote mode only).
auth_authorization_var: ContextVar[Optional[str]] = ContextVar(
    "auth_authorization", default=None
)

# Type 3 — raw API key captured from the configured custom header at ingress.
auth_apikey_var: ContextVar[Optional[str]] = ContextVar(
    "auth_apikey", default=None
)
