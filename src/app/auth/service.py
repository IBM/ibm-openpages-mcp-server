"""
Auth Service Module

Central coordinator for resolving authentication for each request.
Implements precedence: context_token (WXO) > api_key_token (Same IDP) > server credentials.
"""

import logging
from typing import Optional

from src.app.auth.cache import TokenCache
from src.app.auth.providers import (
    AuthProvider,
    PassthroughTokenProvider,
    ApiKeyTokenProvider,
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
    available credentials, following the precedence chain.
    """

    def __init__(self, settings, cache: TokenCache):
        self.settings = settings
        self.cache = cache

    async def resolve_for_request(
        self,
        context_token: Optional[str] = None,
        api_key_token: Optional[str] = None,
    ) -> AuthResult:
        """
        Resolve auth for a single tool invocation.

        Precedence: context_token > api_key_token > server credentials.

        Args:
            context_token: Token from op_auth_header context variable (WXO flow)
            api_key_token: Token already resolved by middleware (Same IDP flow)

        Returns:
            AuthResult with resolved token and provider for retry support
        """
        if context_token:
            logger.info("Auth resolved via context variable (WXO flow)")
            provider = PassthroughTokenProvider(context_token)
        elif api_key_token:
            logger.info("Auth resolved via middleware API key exchange (Same IDP flow)")
            # Token already resolved by middleware; wrap in passthrough for consistency
            # but use ApiKeyTokenProvider if we have the api_key for retry support
            provider = PassthroughTokenProvider(api_key_token)
        else:
            logger.debug("Auth resolved via server credentials (Different IDP flow)")
            provider = ServerCredentialProvider()

        token = await provider.resolve()
        return AuthResult(token if token else None, provider)

    async def resolve_for_request_with_retry(
        self,
        context_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_token: Optional[str] = None,
    ) -> AuthResult:
        """
        Resolve auth with retry capability for API key flow.

        When an api_key is provided (from middleware), uses ApiKeyTokenProvider
        which supports cache eviction and re-exchange on 401.

        Args:
            context_token: Token from op_auth_header context variable (WXO flow)
            api_key: Original API key from request header (for retry support)
            api_key_token: Token already resolved by middleware (Same IDP flow)

        Returns:
            AuthResult with resolved token and provider
        """
        if context_token:
            logger.info("Auth resolved via context variable (WXO flow)")
            provider = PassthroughTokenProvider(context_token)
        elif api_key:
            logger.info("Auth resolved via API key with retry support (Same IDP flow)")
            provider = ApiKeyTokenProvider(
                api_key,
                self.cache,
                self.settings.OPENPAGES_AUTHENTICATION_URL,
                self.settings.SSL_VERIFY,
            )
        elif api_key_token:
            logger.info("Auth resolved via pre-exchanged token (Same IDP flow)")
            provider = PassthroughTokenProvider(api_key_token)
        else:
            logger.debug("Auth resolved via server credentials (Different IDP flow)")
            provider = ServerCredentialProvider()

        token = await provider.resolve()
        return AuthResult(token if token else None, provider)
