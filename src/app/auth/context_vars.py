"""
Auth Context Variables Module

ContextVars for passing authentication data from middleware to tool handlers.
Set by AuthMiddleware, read by tool handlers during request processing.
"""

from contextvars import ContextVar
from typing import Optional

# Token resolved by middleware from API key exchange
auth_token_var: ContextVar[Optional[str]] = ContextVar("auth_token", default=None)

# Original API key from the request header (for retry/refresh)
auth_api_key_var: ContextVar[Optional[str]] = ContextVar("auth_api_key", default=None)
