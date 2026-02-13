"""
Authentication Providers Module

Strategy pattern for authentication resolution.
Each provider handles a specific authentication flow.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.app.auth.cache import TokenCache
from src.app.auth.token_exchange import exchange_api_key

logger = logging.getLogger(__name__)


class AuthProvider(ABC):
    """Base class for authentication strategies."""

    @abstractmethod
    async def resolve(self) -> str:
        """Return Authorization header value (e.g., 'Bearer <token>')."""

    @abstractmethod
    def can_retry(self) -> bool:
        """Whether refresh is possible on 401."""

    @abstractmethod
    async def refresh(self) -> Optional[str]:
        """Attempt to get a fresh token. Returns new header value or None."""


class PassthroughTokenProvider(AuthProvider):
    """
    WXO flow: use token as-is from context variable.

    The token comes directly from the OP-embedded chat (op_auth_header)
    and is used without modification.
    """

    def __init__(self, token: str):
        self._token = token

    async def resolve(self) -> str:
        logger.info("Using passthrough token from context variable")
        return self._token

    def can_retry(self) -> bool:
        return False

    async def refresh(self) -> Optional[str]:
        return None


class ApiKeyTokenProvider(AuthProvider):
    """
    Same IDP flow: exchange API key for token via cache.

    Checks cache first; on miss, exchanges the API key for a token
    and caches the result.
    """

    def __init__(self, api_key: str, cache: TokenCache, auth_url: str, ssl_verify: bool = True):
        self._api_key = api_key
        self._cache = cache
        self._auth_url = auth_url
        self._ssl_verify = ssl_verify
        self._cache_key = f"apikey:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

    @property
    def cache_key(self) -> str:
        return self._cache_key

    async def resolve(self) -> str:
        cached = self._cache.get(self._cache_key)
        if cached:
            logger.info("Using cached token for API key")
            return cached

        token = await exchange_api_key(self._api_key, self._auth_url, self._ssl_verify)
        bearer = f"Bearer {token}"
        self._cache.set(self._cache_key, bearer)
        logger.info("Exchanged API key for token and cached")
        return bearer

    def can_retry(self) -> bool:
        return True

    async def refresh(self) -> Optional[str]:
        self._cache.evict(self._cache_key)
        logger.info("Evicted cached token, re-exchanging API key")
        token = await exchange_api_key(self._api_key, self._auth_url, self._ssl_verify)
        bearer = f"Bearer {token}"
        self._cache.set(self._cache_key, bearer)
        return bearer


class ServerCredentialProvider(AuthProvider):
    """
    Different IDP flow: marker that server credentials should be used.

    Returns empty string to signal that the OpenPages client should
    use its own configured credentials (self.headers).
    """

    async def resolve(self) -> str:
        logger.debug("Using server-configured credentials")
        return ""

    def can_retry(self) -> bool:
        return False

    async def refresh(self) -> Optional[str]:
        return None
