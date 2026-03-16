"""
Authentication Providers Module

Strategy pattern for authentication resolution.
Each provider handles a specific authentication flow.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

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


class ServerCredentialProvider(AuthProvider):
    """
    Fallback flow: marker that server credentials should be used.

    Returns empty string to signal that the OpenPages client should
    use its own configured credentials (self.headers).
    """

    def __init__(self):
        from src.app.config.settings import settings
        self.settings = settings
        self.username = None

    async def resolve(self) -> str:
        logger.debug("Using server-configured credentials")
        # Store username for basic auth
        if self.settings.OPENPAGES_AUTHENTICATION_TYPE == "basic":
            self.username = self.settings.OPENPAGES_USERNAME
            logger.debug(f"Extracted user ID from basic auth")
        return ""

    def can_retry(self) -> bool:
        return False

    async def refresh(self) -> Optional[str]:
        return None
    
    def get_username(self) -> Optional[str]:
        """Get the username for logging purposes."""
        return self.username
