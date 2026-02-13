"""
Auth Middleware Module

FastAPI middleware that extracts API keys from HTTP headers and
exchanges them for tokens before the request reaches tool handlers.
"""

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.app.auth.cache import TokenCache
from src.app.auth.providers import ApiKeyTokenProvider
from src.app.auth.context_vars import auth_token_var, auth_api_key_var

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles API key to token exchange for Same IDP flow.

    Extracts X-Api-Key (or configured header) from the request,
    exchanges it for a token using the configured auth service,
    and stores the result in a ContextVar for downstream use.
    """

    def __init__(
        self,
        app,
        header_name: str = "X-Api-Key",
        auth_url: str = "",
        ssl_verify: bool = True,
        cache: Optional[TokenCache] = None,
    ):
        super().__init__(app)
        self.header_name = header_name
        self.auth_url = auth_url
        self.ssl_verify = ssl_verify
        self.cache = cache or TokenCache()

    async def dispatch(self, request: Request, call_next) -> Response:
        api_key = request.headers.get(self.header_name)

        if api_key:
            try:
                provider = ApiKeyTokenProvider(
                    api_key, self.cache, self.auth_url, self.ssl_verify
                )
                token = await provider.resolve()
                auth_token_var.set(token)
                auth_api_key_var.set(api_key)
                logger.info("Auth middleware: resolved API key to token")
            except Exception as e:
                logger.error(f"Auth middleware: token exchange failed: {e}")
                # Let request proceed — tool handler will use server credentials as fallback

        response = await call_next(request)
        return response
