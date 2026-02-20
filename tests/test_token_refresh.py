"""
Tests for bearer token auto-refresh on 401 responses.
Validates that:
- _clear_bearer_token() removes the cached Authorization header
- initialize_auth() re-fetches after token is cleared
- 401 with server credentials triggers token refresh and retry
- 401 with auth_override (passthrough token) is re-raised without retry
- Non-401 errors are not retried
- Successful requests pass through without retry
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.app.core.openpages_client import OpenPagesClient


@pytest.fixture
def bearer_client():
    """Create an OpenPagesClient configured for bearer auth with a cached token."""
    with patch("src.app.config.settings.settings") as mock_settings:
        mock_settings.SSL_VERIFY = True
        mock_settings.DEBUG = False
        mock_settings.OPENPAGES_INSTANCE_NAME = None
        client = OpenPagesClient(
            base_url="https://openpages.example.com",
            auth_type="bearer",
            api_key="test-api-key",
            authentication_url="https://iam.cloud.ibm.com/identity/token",
            custom_settings=mock_settings,
        )
        # Simulate that initialize_auth() has already run
        client.headers["Authorization"] = "Bearer old-token"
        return client


@pytest.fixture
def basic_client():
    """Create an OpenPagesClient configured for basic auth."""
    with patch("src.app.config.settings.settings") as mock_settings:
        mock_settings.SSL_VERIFY = True
        mock_settings.DEBUG = False
        mock_settings.OPENPAGES_INSTANCE_NAME = None
        client = OpenPagesClient(
            base_url="https://openpages.example.com",
            auth_type="basic",
            username="admin",
            password="password",
            custom_settings=mock_settings,
        )
        return client


class TestClearBearerToken:
    """Tests for _clear_bearer_token()."""

    def test_removes_authorization_header(self, bearer_client):
        """_clear_bearer_token should remove Authorization from headers."""
        assert "Authorization" in bearer_client.headers
        bearer_client._clear_bearer_token()
        assert "Authorization" not in bearer_client.headers

    def test_preserves_other_headers(self, bearer_client):
        """_clear_bearer_token should not affect non-auth headers."""
        bearer_client._clear_bearer_token()
        assert bearer_client.headers["Content-Type"] == "application/json"
        assert bearer_client.headers["Accept"] == "application/json"

    def test_noop_for_basic_auth(self, basic_client):
        """_clear_bearer_token should not remove Authorization for basic auth."""
        assert "Authorization" in basic_client.headers
        basic_client._clear_bearer_token()
        # Basic auth should NOT be cleared
        assert "Authorization" in basic_client.headers

    def test_noop_when_no_authorization(self, bearer_client):
        """_clear_bearer_token should be safe to call when no Authorization header exists."""
        del bearer_client.headers["Authorization"]
        # Should not raise
        bearer_client._clear_bearer_token()
        assert "Authorization" not in bearer_client.headers


class TestInitializeAuthAfterClear:
    """Tests that initialize_auth() re-fetches after _clear_bearer_token()."""

    @pytest.mark.asyncio
    async def test_reinitializes_after_clear(self, bearer_client):
        """After clearing, initialize_auth should fetch a new token."""
        bearer_client._clear_bearer_token()
        assert "Authorization" not in bearer_client.headers

        with patch.object(
            bearer_client, "_create_bearer_auth_header", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = "Bearer new-token"
            await bearer_client.initialize_auth()

        assert bearer_client.headers["Authorization"] == "Bearer new-token"

    @pytest.mark.asyncio
    async def test_skips_if_already_initialized(self, bearer_client):
        """initialize_auth should not re-fetch if Authorization header exists."""
        with patch.object(
            bearer_client, "_create_bearer_auth_header", new_callable=AsyncMock
        ) as mock_create:
            await bearer_client.initialize_auth()

        mock_create.assert_not_called()
        assert bearer_client.headers["Authorization"] == "Bearer old-token"


def _make_401_response(url="https://openpages.example.com/opgrc/api/v2/query"):
    """Helper to create a mock 401 httpx.Response."""
    response = httpx.Response(
        status_code=401,
        request=httpx.Request("POST", url),
        text="Unauthorized",
    )
    return response


def _make_200_response(url="https://openpages.example.com/opgrc/api/v2/query", json_data=None):
    """Helper to create a mock 200 httpx.Response."""
    import json as json_mod
    body = json_mod.dumps(json_data or {"rows": []}).encode()
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", url),
        content=body,
        headers={"content-type": "application/json"},
    )
    return response


def _make_500_response(url="https://openpages.example.com/opgrc/api/v2/query"):
    """Helper to create a mock 500 httpx.Response."""
    response = httpx.Response(
        status_code=500,
        request=httpx.Request("POST", url),
        text="Internal Server Error",
    )
    return response


class TestRequestWithAuthRetry:
    """Tests for _request_with_auth_retry()."""

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self, bearer_client):
        """Successful request should return without any retry."""
        ok_response = _make_200_response()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=ok_response)

            response = await bearer_client._request_with_auth_retry(
                "POST", "https://openpages.example.com/opgrc/api/v2/query",
                auth_override=None, json={"statement": "SELECT 1"}, timeout=30.0
            )

        assert response.status_code == 200
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_401_with_server_creds_retries(self, bearer_client):
        """401 with server credentials should clear token, re-auth, and retry."""
        fail_response = _make_401_response()
        ok_response = _make_200_response(json_data={"rows": [{"id": 1}]})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First call raises 401, second succeeds
            mock_client.request = AsyncMock(side_effect=[fail_response, ok_response])

            with patch.object(
                bearer_client, "initialize_auth", new_callable=AsyncMock
            ) as mock_init_auth:
                async def restore_token():
                    bearer_client.headers["Authorization"] = "Bearer refreshed-token"
                mock_init_auth.side_effect = restore_token

                response = await bearer_client._request_with_auth_retry(
                    "POST", "https://openpages.example.com/opgrc/api/v2/query",
                    auth_override=None, json={"statement": "SELECT 1"}, timeout=30.0
                )

        assert response.status_code == 200
        assert mock_client.request.call_count == 2
        # initialize_auth is called multiple times: from _get_request_headers (initial + retry) and from the retry logic
        assert mock_init_auth.call_count >= 2

    @pytest.mark.asyncio
    async def test_401_with_auth_override_no_retry(self, bearer_client):
        """401 with auth_override should re-raise without retry."""
        fail_response = _make_401_response()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=fail_response)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await bearer_client._request_with_auth_retry(
                    "POST", "https://openpages.example.com/opgrc/api/v2/query",
                    auth_override="Bearer user-token", json={"statement": "SELECT 1"}, timeout=30.0
                )

        assert exc_info.value.response.status_code == 401
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_401_error_not_retried(self, bearer_client):
        """Non-401 HTTP errors should be raised without retry."""
        fail_response = _make_500_response()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=fail_response)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await bearer_client._request_with_auth_retry(
                    "POST", "https://openpages.example.com/opgrc/api/v2/query",
                    auth_override=None, json={"statement": "SELECT 1"}, timeout=30.0
                )

        assert exc_info.value.response.status_code == 500
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_401_basic_auth_not_retried(self, basic_client):
        """401 with basic auth should not trigger retry (only bearer gets retry)."""
        fail_response = _make_401_response()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(return_value=fail_response)

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await basic_client._request_with_auth_retry(
                    "GET", "https://openpages.example.com/opgrc/api/v2/contents/123",
                    auth_override=None, timeout=30.0
                )

        assert exc_info.value.response.status_code == 401
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_401_retry_also_fails(self, bearer_client):
        """If retry after 401 also returns an error, that error should be raised."""
        fail_401 = _make_401_response()
        fail_403 = httpx.Response(
            status_code=403,
            request=httpx.Request("POST", "https://openpages.example.com/opgrc/api/v2/query"),
            text="Forbidden",
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.request = AsyncMock(side_effect=[fail_401, fail_403])

            with patch.object(
                bearer_client, "initialize_auth", new_callable=AsyncMock
            ) as mock_init_auth:
                async def restore_token():
                    bearer_client.headers["Authorization"] = "Bearer refreshed-token"
                mock_init_auth.side_effect = restore_token

                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await bearer_client._request_with_auth_retry(
                        "POST", "https://openpages.example.com/opgrc/api/v2/query",
                        auth_override=None, json={"statement": "SELECT 1"}, timeout=30.0
                    )

        assert exc_info.value.response.status_code == 403
        assert mock_client.request.call_count == 2