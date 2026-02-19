"""
Auth Service Module

Central coordinator for resolving authentication for each request.
Implements precedence: context_token (WXO/Passthrough) > server credentials (Fallback).
"""

import logging
from typing import Optional

from src.app.auth.providers import (
    AuthProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
)

logger = logging.getLogger(__name__)


class AuthResult:
    """Encapsulates resolved auth + retry capability."""

    def __init__(self, token: Optional[str], provider: AuthProvider):
        self._token = token
        self.provider = provider

    @property
    def auth_override(self) -> Optional[str]:
        """
        Returns the token string to pass as auth_override, or None for server creds.

        Empty string from ServerCredentialProvider is treated as None.
        """
        if self._token:
            return self._token
        return None

    async def retry(self) -> Optional[str]:
        """On 401, attempt refresh. Returns new token or None."""
        if not self.provider.can_retry():
            return None
        new_token = await self.provider.refresh()
        if new_token:
            self._token = new_token
        return new_token


class AuthService:
    """
    Central authentication coordinator.

    Resolves the correct authentication strategy for each request based on
    available credentials, following the precedence chain:
    1. Passthrough (WXO): Token from op_auth_header context variable
    2. Fallback: Server-configured credentials
    """

    def __init__(self, settings):
        self.settings = settings

    async def resolve_for_request(
        self,
        context_token: Optional[str] = None,
    ) -> AuthResult:
        """
        Resolve auth for a single tool invocation.

        Precedence: context_token > server credentials.

        Args:
            context_token: Token from op_auth_header context variable (WXO flow)

        Returns:
            AuthResult with resolved token and provider
        """
        if context_token:
            logger.info("Auth resolved via context variable (Passthrough flow)")
            provider = PassthroughTokenProvider(context_token)
        else:
            logger.debug("Auth resolved via server credentials (Fallback flow)")
            provider = ServerCredentialProvider()

        token = await provider.resolve()
        return AuthResult(token if token else None, provider)
