"""
Tests for Auth Middleware Module
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from src.app.auth.middleware import AuthMiddleware
from src.app.auth.cache import TokenCache
from src.app.auth.context_vars import auth_token_var, auth_api_key_var


async def _read_context_endpoint(request):
    """Test endpoint that reads auth context vars"""
    return JSONResponse({
        "auth_token": auth_token_var.get(),
        "auth_api_key": auth_api_key_var.get(),
    })


def _create_test_app(header_name="X-Api-Key", auth_url="https://iam.cloud.ibm.com/identity/token", cache=None):
    """Create a test Starlette app with AuthMiddleware"""
    app = Starlette(routes=[Route("/test", _read_context_endpoint)])
    app.add_middleware(
        AuthMiddleware,
        header_name=header_name,
        auth_url=auth_url,
        ssl_verify=True,
        cache=cache or TokenCache(),
    )
    return app


class TestAuthMiddleware:
    """Test AuthMiddleware"""

    def test_request_with_api_key_sets_context_var(self):
        """Request with X-Api-Key header sets ContextVar with resolved token"""
        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = "resolved_access_token"

            app = _create_test_app()
            client = TestClient(app)

            response = client.get("/test", headers={"X-Api-Key": "my_api_key"})
            assert response.status_code == 200

            data = response.json()
            assert data["auth_token"] == "Bearer resolved_access_token"
            assert data["auth_api_key"] == "my_api_key"

    def test_request_without_api_key_leaves_context_var_none(self):
        """Request without X-Api-Key header leaves ContextVar as None"""
        app = _create_test_app()
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200

        data = response.json()
        assert data["auth_token"] is None
        assert data["auth_api_key"] is None

    def test_token_exchange_failure_proceeds(self):
        """Token exchange failure lets request proceed (fallback to server creds)"""
        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.side_effect = RuntimeError("Exchange failed")

            app = _create_test_app()
            client = TestClient(app)

            response = client.get("/test", headers={"X-Api-Key": "bad_key"})
            assert response.status_code == 200

            data = response.json()
            assert data["auth_token"] is None
            assert data["auth_api_key"] is None

    def test_custom_header_name(self):
        """Custom header name from settings is used"""
        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = "token_from_custom_header"

            app = _create_test_app(header_name="X-Custom-Auth")
            client = TestClient(app)

            # Default header should not work
            response = client.get("/test", headers={"X-Api-Key": "my_key"})
            data = response.json()
            assert data["auth_token"] is None

            # Custom header should work
            response = client.get("/test", headers={"X-Custom-Auth": "my_key"})
            data = response.json()
            assert data["auth_token"] == "Bearer token_from_custom_header"

    def test_cached_token_is_reused(self):
        """Cached token is reused without calling exchange_api_key again"""
        cache = TokenCache()

        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = "fresh_token"

            app = _create_test_app(cache=cache)
            client = TestClient(app)

            # First request should call exchange
            response1 = client.get("/test", headers={"X-Api-Key": "my_key"})
            assert response1.json()["auth_token"] == "Bearer fresh_token"
            assert mock_exchange.call_count == 1

            # Second request with same key should use cache
            response2 = client.get("/test", headers={"X-Api-Key": "my_key"})
            assert response2.json()["auth_token"] == "Bearer fresh_token"
            assert mock_exchange.call_count == 1  # Not called again
