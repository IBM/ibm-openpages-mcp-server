"""
Tests for Token Exchange Module
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.app.auth.token_exchange import (
    detect_auth_type,
    exchange_api_key,
    fetch_ibm_cloud_token,
    fetch_mcsp_token,
    fetch_cp4d_token,
)


class TestDetectAuthType:
    """Test detect_auth_type function"""

    def test_ibm_cloud_detection(self):
        """Detects IBM Cloud from URL"""
        assert detect_auth_type("https://iam.cloud.ibm.com/identity/token") == "ibm_cloud"
        assert detect_auth_type("https://iam.test.cloud.ibm.com/identity/token") == "ibm_cloud"

    def test_mcsp_detection(self):
        """Detects MCSP from URL"""
        assert detect_auth_type("https://account-iam.platform.saas.ibm.com/token") == "mcsp"
        assert detect_auth_type("https://some.saas.ibm.com/api/token") == "mcsp"

    def test_cp4d_detection(self):
        """Detects CP4D from URL"""
        assert detect_auth_type("https://cpd-zen.apps.example.com/icp4d-api/v1/authorize") == "cp4d"
        assert detect_auth_type("https://cpd-instance.example.com/auth") == "cp4d"

    def test_unknown_defaults_to_ibm_cloud(self):
        """Unknown URL defaults to ibm_cloud"""
        assert detect_auth_type("https://unknown.example.com/token") == "ibm_cloud"


class TestExchangeApiKey:
    """Test exchange_api_key function"""

    @pytest.mark.asyncio
    async def test_ibm_cloud_exchange(self):
        """exchange_api_key with IBM Cloud URL calls fetch_ibm_cloud_token"""
        with patch("src.app.auth.token_exchange.fetch_ibm_cloud_token", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "ibm_cloud_token"

            result = await exchange_api_key(
                "my_api_key",
                "https://iam.cloud.ibm.com/identity/token"
            )

            assert result == "ibm_cloud_token"
            mock_fetch.assert_called_once_with("my_api_key", "https://iam.cloud.ibm.com/identity/token")

    @pytest.mark.asyncio
    async def test_mcsp_exchange(self):
        """exchange_api_key with MCSP URL calls fetch_mcsp_token"""
        with patch("src.app.auth.token_exchange.fetch_mcsp_token", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "mcsp_token"

            result = await exchange_api_key(
                "my_api_key",
                "https://account-iam.platform.saas.ibm.com/token"
            )

            assert result == "mcsp_token"
            mock_fetch.assert_called_once_with("my_api_key", "https://account-iam.platform.saas.ibm.com/token")

    @pytest.mark.asyncio
    async def test_cp4d_raises_value_error(self):
        """exchange_api_key with CP4D URL raises ValueError"""
        with pytest.raises(ValueError, match="API key exchange not supported"):
            await exchange_api_key(
                "my_api_key",
                "https://cpd-zen.apps.example.com/icp4d-api/v1/authorize"
            )


class TestFetchIbmCloudToken:
    """Test fetch_ibm_cloud_token function"""

    @pytest.mark.asyncio
    async def test_successful_exchange(self):
        """Successful IBM Cloud token exchange"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "ibm_cloud_access_token"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.app.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_ibm_cloud_token(
                "my_api_key",
                "https://iam.cloud.ibm.com/identity/token"
            )
            assert result == "ibm_cloud_access_token"

    @pytest.mark.asyncio
    async def test_missing_access_token_raises(self):
        """Missing access_token in response raises RuntimeError"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "invalid_key"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.app.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="access_token"):
                await fetch_ibm_cloud_token(
                    "bad_key",
                    "https://iam.cloud.ibm.com/identity/token"
                )


class TestFetchMcspToken:
    """Test fetch_mcsp_token function"""

    @pytest.mark.asyncio
    async def test_successful_exchange(self):
        """Successful MCSP token exchange"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "mcsp_access_token"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.app.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_mcsp_token(
                "my_api_key",
                "https://account-iam.platform.saas.ibm.com/token"
            )
            assert result == "mcsp_access_token"


class TestFetchCp4dToken:
    """Test fetch_cp4d_token function"""

    @pytest.mark.asyncio
    async def test_successful_exchange(self):
        """Successful CP4D token exchange"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "cp4d_access_token"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.app.auth.token_exchange.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_cp4d_token(
                "admin",
                "password123",
                "https://cpd-zen.apps.example.com/icp4d-api/v1/authorize",
                ssl_verify=False
            )
            assert result == "cp4d_access_token"
