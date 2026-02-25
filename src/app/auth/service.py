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
from src.app.auth.token_validator import PassthroughTokenValidator, TokenValidationError

logger = logging.getLogger(__name__)


class PassthroughAuthError(Exception):
    """Raised when passthrough auth key is present but the token is empty or missing."""
    pass


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
        self._token_validator = PassthroughTokenValidator()

    async def resolve_for_request(
        self,
        context_token: Optional[str] = None,
        has_context_token_key: bool = False,
    ) -> AuthResult:
        """
        Resolve auth for a single tool invocation.

        Precedence: context_token > server credentials.

        If has_context_token_key is True (the key was present in the request arguments),
        the passthrough flow is enforced strictly:
        - Empty/None token → PassthroughAuthError (never fall back to server creds)
        - Invalid/expired token → TokenValidationError propagated

        Args:
            context_token: Token from op_auth_header context variable (WXO flow)
            has_context_token_key: Whether the op_auth_header key was present in args

        Returns:
            AuthResult with resolved token and provider

        Raises:
            PassthroughAuthError: If key is present but token is empty/None
            TokenValidationError: If token is present but fails validation
        """
        if has_context_token_key:
            if not context_token:
                raise PassthroughAuthError(
                    "op_auth_header key present but token is empty — "
                    "cannot fall back to server credentials for passthrough flow"
                )
            # Validate token (raises TokenValidationError on failure)
            self._token_validator.validate(context_token)
            logger.info("Auth resolved via validated context variable (Passthrough flow)")
            provider = PassthroughTokenProvider(context_token)
        elif context_token:
            # Legacy path: token present without explicit key tracking
            logger.info("Auth resolved via context variable (Passthrough flow)")
            provider = PassthroughTokenProvider(context_token)
        else:
            logger.info("Auth resolved via server credentials (Fallback flow)")
            provider = ServerCredentialProvider()

        token = await provider.resolve()
        return AuthResult(token if token else None, provider)
