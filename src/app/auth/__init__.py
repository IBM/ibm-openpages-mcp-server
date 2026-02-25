"""
Authentication Framework for GRC MCP Server

Provides two authentication flows:
- Passthrough (WXO/OP-embedded chat): Pass-through token from context variables
- Fallback (Server credentials): Server-configured credentials
"""

from src.app.auth.service import AuthService, AuthResult, PassthroughAuthError
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
    "AuthProvider",
    "PassthroughTokenProvider",
    "ServerCredentialProvider",
    "PassthroughTokenValidator",
    "TokenValidationError",
]
