"""
Passthrough Token Validator

Offline JWT validation for passthrough (WXO/embedded chat) tokens.
Decodes the JWT payload to check the `exp` claim without signature verification.
Includes a single-token cache to avoid repeated decoding of the same token.
"""

import asyncio
import base64
import binascii
import json
import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class TokenValidationError(Exception):
    """Raised when a passthrough token fails validation (expired, malformed, missing exp)."""
    pass


class PassthroughTokenValidator:
    """
    Validates passthrough JWT tokens by decoding the payload and checking expiry.

    Uses only stdlib (no cryptographic signature verification) since the token
    originates from a trusted upstream identity provider.

    Maintains a single-token cache: stores the last (raw_token, exp) pair.
    On cache hit, only re-checks expiry. On miss, performs full decode.
    """

    def __init__(self):
        self._cached_token: Optional[str] = None
        self._cached_exp: Optional[float] = None
        self._cache_lock = asyncio.Lock()

    async def validate(self, raw_token: str) -> None:
        """
        Validate a passthrough token.

        Strips "Bearer " prefix if present, decodes the JWT payload,
        and checks the `exp` claim against current time.

        Args:
            raw_token: The raw token string, optionally prefixed with "Bearer ".

        Raises:
            TokenValidationError: If the token is malformed, missing exp, or expired.
        """
        token = self._strip_bearer_prefix(raw_token)

        # Cache hit — same token string, just re-check expiry
        async with self._cache_lock:
            if token == self._cached_token and self._cached_exp is not None:
                if time.time() >= self._cached_exp:
                    self._clear_cache()
                    raise TokenValidationError("Passthrough token has expired")
                return

            # Cache miss — full decode
            exp = self._decode_exp(token)
            if time.time() >= exp:
                raise TokenValidationError("Passthrough token has expired")

            # Update cache
            self._cached_token = token
            self._cached_exp = exp

    def _strip_bearer_prefix(self, raw_token: str) -> str:
        """Strip 'Bearer ' or 'bearer ' prefix if present."""
        if raw_token.lower().startswith("bearer "):
            return raw_token[7:]
        return raw_token

    def _decode_exp(self, token: str) -> float:
        """
        Decode the JWT payload and extract the exp claim.

        Args:
            token: JWT string without Bearer prefix.

        Returns:
            The exp claim as a float (epoch seconds).

        Raises:
            TokenValidationError: On any decoding or validation failure.
        """
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenValidationError(
                f"Malformed JWT: expected 3 segments, got {len(parts)}"
            )

        payload_b64 = parts[1]

        # Add padding if necessary
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
        except (ValueError, binascii.Error) as e:
            logger.debug(f"Base64 decode error: {e}")
            raise TokenValidationError("Malformed JWT: invalid base64 in payload")

        try:
            payload = json.loads(payload_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise TokenValidationError("Malformed JWT: payload is not valid JSON")

        if "exp" not in payload:
            raise TokenValidationError("JWT missing required 'exp' claim")

        try:
            exp = float(payload["exp"])
        except (TypeError, ValueError):
            raise TokenValidationError("JWT 'exp' claim is not a valid number")

        return exp

    def _clear_cache(self) -> None:
        """Clear the cached token."""
        self._cached_token = None
        self._cached_exp = None
