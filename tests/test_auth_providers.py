"""
Tests for Authentication Providers Module
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.app.auth.providers import (
    PassthroughTokenProvider,
    ServerCredentialProvider,
)


class TestPassthroughTokenProvider:
    """Test PassthroughTokenProvider (WXO flow)"""

    @pytest.mark.asyncio
    async def test_resolve_returns_token_as_is(self):
        """resolve() returns token as-is"""
        provider = PassthroughTokenProvider("Bearer my_token_123")
        result = await provider.resolve()
        assert result == "Bearer my_token_123"

    def test_can_retry_returns_false(self):
        """can_retry() returns False"""
        provider = PassthroughTokenProvider("Bearer token")
        assert provider.can_retry() is False

    @pytest.mark.asyncio
    async def test_refresh_returns_none(self):
        """refresh() returns None"""
        provider = PassthroughTokenProvider("Bearer token")
        result = await provider.refresh()
        assert result is None


class TestServerCredentialProvider:
    """Test ServerCredentialProvider (Fallback flow)"""

    @pytest.mark.asyncio
    async def test_resolve_returns_empty_string(self):
        """resolve() returns empty string"""
        provider = ServerCredentialProvider()
        result = await provider.resolve()
        assert result == ""

    def test_can_retry_returns_false(self):
        """can_retry() returns False"""
        provider = ServerCredentialProvider()
        assert provider.can_retry() is False

    @pytest.mark.asyncio
    async def test_refresh_returns_none(self):
        """refresh() returns None"""
        provider = ServerCredentialProvider()
        result = await provider.refresh()
        assert result is None
