"""
Authentication Framework for GRC MCP Server

Provides multi-source request authentication:
- WXO (OP-embedded chat): Pass-through token from context variables
- Same IDP (shared identity): API key exchange with caching
- Different IDP (separate identity): Server-configured credentials
"""

from src.app.auth.service import AuthService, AuthResult
from src.app.auth.middleware import AuthMiddleware
from src.app.auth.cache import TokenCache
from src.app.auth.providers import (
    AuthProvider,
    PassthroughTokenProvider,
    ApiKeyTokenProvider,
    ServerCredentialProvider,
)

__all__ = [
    "AuthService",
    "AuthResult",
    "AuthMiddleware",
    "TokenCache",
    "AuthProvider",
    "PassthroughTokenProvider",
    "ApiKeyTokenProvider",
    "ServerCredentialProvider",
]
