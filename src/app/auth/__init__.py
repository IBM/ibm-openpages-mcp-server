"""
Authentication Framework for GRC MCP Server

Provides two authentication flows:
- Passthrough (WXO/OP-embedded chat): Pass-through token from context variables
- Fallback (Server credentials): Server-configured credentials
"""

from src.app.auth.service import AuthService, AuthResult
from src.app.auth.providers import (
    AuthProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
)

__all__ = [
    "AuthService",
    "AuthResult",
    "AuthProvider",
    "PassthroughTokenProvider",
    "ServerCredentialProvider",
]
