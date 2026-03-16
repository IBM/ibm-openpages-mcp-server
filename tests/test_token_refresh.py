"""
Tests for bearer token auto-refresh on 401 responses and auth service resolution.

Validates that:
- _clear_bearer_token() removes the cached Authorization header
- initialize_auth() re-fetches after token is cleared (with double-checked locking)
- 401 with server credentials triggers token refresh and retry
- 401 with auth_override (passthrough token) is re-raised without retry
- Non-401 errors are not retried
- Successful requests pass through without retry
- Concurrent 401s collapse into a single token refresh
- _get_request_headers returns a snapshot copy (not a mutable reference)
- AuthService with has_context_token_key strict behavior
"""

import asyncio
import base64
import json
import time

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.app.core.openpages_client import OpenPagesClient
from src.app.auth.service import AuthService, PassthroughAuthError
from src.app.auth.token_validator import TokenValidationError


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
    return httpx.Response(
        status_code=401,
        request=httpx.Request("POST", url),
        text="Unauthorized",
    )


def _make_200_response(url="https://openpages.example.com/opgrc/api/v2/query", json_data=None):
    """Helper to create a mock 200 httpx.Response."""
    import json as json_mod
    body = json_mod.dumps(json_data or {"rows": []}).encode()
    return httpx.Response(
        status_code=200,
        request=httpx.Request("POST", url),
        content=body,
        headers={"content-type": "application/json"},
    )


def _make_500_response(url="https://openpages.example.com/opgrc/api/v2/query"):
    """Helper to create a mock 500 httpx.Response."""
    return httpx.Response(
        status_code=500,
        request=httpx.Request("POST", url),
        text="Internal Server Error",
    )


class TestRequestWithAuthRetry:
    """Tests for _request_with_auth_retry()."""

    @pytest.mark.asyncio
    async def test_successful_request_no_retry(self, bearer_client):
        """Successful request should return without any retry."""
        ok_response = _make_200_response()
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=ok_response)

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
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
        mock_client = AsyncMock()
        # First call raises 401, second succeeds
        mock_client.request = AsyncMock(side_effect=[fail_response, ok_response])

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
            with patch.object(
                bearer_client, "_create_bearer_auth_header", new_callable=AsyncMock,
                return_value="Bearer refreshed-token"
            ) as mock_create_bearer:
                response = await bearer_client._request_with_auth_retry(
                    "POST", "https://openpages.example.com/opgrc/api/v2/query",
                    auth_override=None, json={"statement": "SELECT 1"}, timeout=30.0
                )

        assert response.status_code == 200
        assert mock_client.request.call_count == 2
        mock_create_bearer.assert_called_once()

    @pytest.mark.asyncio
    async def test_401_with_auth_override_no_retry(self, bearer_client):
        """401 with auth_override should re-raise without retry."""
        fail_response = _make_401_response()
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=fail_response)

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
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
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=fail_response)

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
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
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=fail_response)

        with patch.object(basic_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
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
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[fail_401, fail_403])

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
            with patch.object(
                bearer_client, "_create_bearer_auth_header", new_callable=AsyncMock,
                return_value="Bearer refreshed-token"
            ):
                with pytest.raises(httpx.HTTPStatusError) as exc_info:
                    await bearer_client._request_with_auth_retry(
                        "POST", "https://openpages.example.com/opgrc/api/v2/query",
                        auth_override=None, json={"statement": "SELECT 1"}, timeout=30.0
                    )

        assert exc_info.value.response.status_code == 403
        assert mock_client.request.call_count == 2


class TestConcurrentAuthRetry:
    """Tests that concurrent 401s collapse into a single token refresh."""

    @pytest.mark.asyncio
    async def test_concurrent_401s_single_refresh(self, bearer_client):
        """Multiple concurrent 401s should trigger only one token refresh."""
        refresh_count = 0

        async def mock_create_bearer(*args, **kwargs):
            nonlocal refresh_count
            refresh_count += 1
            await asyncio.sleep(0.05)
            return "Bearer fresh-token"

        async def mock_request(method, url, headers=None, **kwargs):
            token = (headers or {}).get("Authorization", "")
            if token == "Bearer old-token":
                return _make_401_response(url)
            return _make_200_response(url)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_request)

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
            with patch.object(
                bearer_client, "_create_bearer_auth_header", new_callable=AsyncMock,
                side_effect=mock_create_bearer
            ):
                tasks = [
                    bearer_client._request_with_auth_retry(
                        "GET", f"https://openpages.example.com/opgrc/api/v2/contents/{i}",
                        auth_override=None, timeout=30.0
                    )
                    for i in range(5)
                ]
                results = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in results)
        assert refresh_count == 1, f"Expected 1 refresh, got {refresh_count}"

    @pytest.mark.asyncio
    async def test_concurrent_401s_all_use_fresh_token(self, bearer_client):
        """After one coroutine refreshes, others should use the same fresh token."""
        tokens_used_on_retry = []

        async def mock_create_bearer(*args, **kwargs):
            await asyncio.sleep(0.05)
            return "Bearer fresh-token"

        async def mock_request(method, url, headers=None, **kwargs):
            token = (headers or {}).get("Authorization", "")
            if token == "Bearer old-token":
                return _make_401_response(url)
            tokens_used_on_retry.append(token)
            return _make_200_response(url)

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_request)

        with patch.object(bearer_client, "_get_http_client", new_callable=AsyncMock, return_value=mock_client):
            with patch.object(
                bearer_client, "_create_bearer_auth_header", new_callable=AsyncMock,
                side_effect=mock_create_bearer
            ):
                tasks = [
                    bearer_client._request_with_auth_retry(
                        "GET", f"https://openpages.example.com/opgrc/api/v2/contents/{i}",
                        auth_override=None, timeout=30.0
                    )
                    for i in range(3)
                ]
                await asyncio.gather(*tasks)

        assert all(t == "Bearer fresh-token" for t in tokens_used_on_retry)


class TestGetRequestHeadersSnapshot:
    """Tests that _get_request_headers returns a snapshot copy, not a mutable reference."""

    @pytest.mark.asyncio
    async def test_server_creds_returns_copy(self, bearer_client):
        """_get_request_headers(None) should return a copy, not self.headers."""
        headers = await bearer_client._get_request_headers(auth_override=None)
        assert headers is not bearer_client.headers
        assert headers == bearer_client.headers

    @pytest.mark.asyncio
    async def test_mutations_do_not_affect_client(self, bearer_client):
        """Mutating the returned headers should not affect self.headers."""
        headers = await bearer_client._get_request_headers(auth_override=None)
        headers["Authorization"] = "Bearer tampered"
        assert bearer_client.headers["Authorization"] == "Bearer old-token"

    @pytest.mark.asyncio
    async def test_auth_override_returns_copy(self, bearer_client):
        """_get_request_headers(override) should return a copy with the override."""
        headers = await bearer_client._get_request_headers(auth_override="Bearer user-token")
        assert headers is not bearer_client.headers
        assert headers["Authorization"] == "Bearer user-token"
        assert bearer_client.headers["Authorization"] == "Bearer old-token"


# ---------------------------------------------------------------------------
# AuthService.resolve_for_request — has_context_token_key behavior
# ---------------------------------------------------------------------------

def _make_jwt(payload: dict) -> str:
    """Build a minimal unsigned JWT."""
    header = {"alg": "none", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{h}.{p}.fakesig"


def _make_valid_bearer_token() -> str:
    return "Bearer " + _make_jwt({"sub": "u", "exp": time.time() + 3600})


def _make_expired_bearer_token() -> str:
    return "Bearer " + _make_jwt({"sub": "u", "exp": time.time() - 3600})


@pytest.fixture
def mock_settings():
    return MagicMock()


class TestAuthServiceResolve:
    """Tests for AuthService.resolve_for_request with has_context_token_key."""

    @pytest.mark.asyncio
    async def test_key_present_valid_token_passthrough(self, mock_settings):
        """has_context_token_key=True + valid token → passthrough auth."""
        svc = AuthService(mock_settings)
        token = _make_valid_bearer_token()
        result = await svc.resolve_for_request(
            context_token=token, has_context_token_key=True
        )
        assert result.auth_override == token

    @pytest.mark.asyncio
    async def test_key_present_empty_token_raises(self, mock_settings):
        """has_context_token_key=True + empty token → PassthroughAuthError."""
        svc = AuthService(mock_settings)
        with pytest.raises(PassthroughAuthError, match="empty"):
            await svc.resolve_for_request(
                context_token="", has_context_token_key=True
            )

    @pytest.mark.asyncio
    async def test_key_present_none_token_raises(self, mock_settings):
        """has_context_token_key=True + None token → PassthroughAuthError."""
        svc = AuthService(mock_settings)
        with pytest.raises(PassthroughAuthError, match="empty"):
            await svc.resolve_for_request(
                context_token=None, has_context_token_key=True
            )

    @pytest.mark.asyncio
    async def test_key_present_expired_token_raises(self, mock_settings):
        """has_context_token_key=True + expired token → TokenValidationError."""
        svc = AuthService(mock_settings)
        token = _make_expired_bearer_token()
        with pytest.raises(TokenValidationError, match="expired"):
            await svc.resolve_for_request(
                context_token=token, has_context_token_key=True
            )

    @pytest.mark.asyncio
    async def test_key_absent_no_token_server_creds(self, mock_settings):
        """has_context_token_key=False + no token → server credentials (unchanged)."""
        svc = AuthService(mock_settings)
        result = await svc.resolve_for_request(
            context_token=None, has_context_token_key=False
        )
        # ServerCredentialProvider returns empty string → auth_override is None
        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_key_absent_with_token_legacy_passthrough(self, mock_settings):
        """has_context_token_key=False + token present → legacy passthrough (no validation)."""
        svc = AuthService(mock_settings)
        token = _make_valid_bearer_token()
        result = await svc.resolve_for_request(
            context_token=token, has_context_token_key=False
        )
        assert result.auth_override == token