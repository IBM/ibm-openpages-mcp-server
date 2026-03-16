"""
Auth Service Module

Central coordinator for resolving authentication for each request.
Implements precedence: context_token (WXO/Passthrough) > server credentials (Fallback).
Also extracts username from authentication context for logging purposes.
"""

import logging
from typing import Optional

from src.app.auth.providers import (
    AuthProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
)
from src.app.auth.token_validator import PassthroughTokenValidator, TokenValidationError
from src.app.auth.token_utils import extract_user_id_from_token

logger = logging.getLogger(__name__)


class PassthroughAuthError(Exception):
    """Raised when passthrough auth key is present but the token is empty or missing."""
    pass


class AuthResult:
    """Encapsulates resolved auth + retry capability + user identity."""

    def __init__(self, token: Optional[str], provider: AuthProvider, username: Optional[str] = None):
        self._token = token
        self.provider = provider
        self.username = username

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
    
    def _extract_and_log_username(self, token: Optional[str], source: str) -> Optional[str]:
        """
        Extract username from token and log the result.
        
        Args:
            token: The token to extract username from
            source: Description of the token source for logging (e.g., "JWT token", "bearer token")
        
        Returns:
            Extracted user ID or None
        """
        if not token:
            return None
        
        user_id = extract_user_id_from_token(token)
        if user_id:
            logger.debug(f"Extracted user ID from {source}: {user_id}")
        else:
            logger.debug(f"Could not extract user ID from {source} (may not be JWT)")
        return user_id

    async def resolve_for_request(
        self,
        context_token: Optional[str] = None,
        has_context_token_key: bool = False,
    ) -> AuthResult:
        """
        Resolve auth for a single tool invocation with username extraction.

        Precedence: context_token > server credentials.
        
        Username extraction precedence:
        1. JWT token claims (for bearer/passthrough auth)
        2. Basic auth username (from settings)

        If has_context_token_key is True (the key was present in the request arguments),
        the passthrough flow is enforced strictly:
        - Empty/None token → PassthroughAuthError (never fall back to server creds)
        - Invalid/expired token → TokenValidationError propagated

        Args:
            context_token: Token from op_auth_header context variable (WXO flow)
            has_context_token_key: Whether the op_auth_header key was present in args

        Returns:
            AuthResult with resolved token, provider, and username

        Raises:
            PassthroughAuthError: If key is present but token is empty/None
            TokenValidationError: If token is present but fails validation
        """
        username = None
        token = None
        
        if has_context_token_key:
            if not context_token:
                raise PassthroughAuthError(
                    "op_auth_header key present but token is empty — "
                    "cannot fall back to server credentials for passthrough flow"
                )
            # Validate token (raises TokenValidationError on failure)
            await self._token_validator.validate(context_token)
            logger.info("Auth resolved via validated context variable (Passthrough flow)")
            provider = PassthroughTokenProvider(context_token)
            
            # Extract username from passthrough token
            username = self._extract_and_log_username(context_token, "passthrough JWT token")
        else:
            logger.info("Auth resolved via server credentials (Fallback flow)")
            provider = ServerCredentialProvider()
            
            # For basic auth, get username from provider
            if hasattr(provider, 'get_username'):
                username = provider.get_username()
                if username:
                    logger.debug(f"Extracted user name from basic auth: {username}")
        
        # Resolve token after username extraction
        token = await provider.resolve()
        
        # For bearer token, try to extract username from JWT if not already extracted
        if not username and token:
            username = self._extract_and_log_username(token, "server bearer token")
        
        if username:
            logger.debug(f"Resolved user ID for logging")
        else:
            logger.debug("Could not resolve user ID from authentication context")
        
        return AuthResult(token if token else None, provider, username)
