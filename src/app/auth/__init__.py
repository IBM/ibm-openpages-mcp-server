"""
Authentication Framework for GRC MCP Server

Provides two authentication flows:
- Passthrough (WXO/OP-embedded chat): Pass-through token from context variables
- Fallback (Server credentials): Server-configured credentials
"""

from src.app.auth.errors import PassthroughAuthError
from src.app.auth.service import (
    AuthService,
    AuthResult,
    is_basic_auth_scheme,
)
from src.app.auth.providers import (
    AuthProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
)
from src.app.auth.token_validator import PassthroughTokenValidator, TokenValidationError

__all__ = [
    "AuthService",
    "AuthResult",
    "PassthroughAuthError",
    "is_basic_auth_scheme",
    "AuthProvider",
    "PassthroughTokenProvider",
    "ServerCredentialProvider",
    "PassthroughTokenValidator",
    "TokenValidationError",
]
