"""
Authentication Providers Module

Strategy pattern for authentication resolution. Each provider handles one of the
four supported auth types and returns an ``Authorization`` header value (or "" to
signal server credentials).

Types, in fixed priority (highest first):
    1. AuthorizationHeaderProvider  — HTTP ``Authorization`` bearer (passthrough)
    2. PassthroughTokenProvider     — ``op_auth_header`` context var (passthrough)
    3. ApiKeyTokenProvider          — configurable API-key header, same-IDP exchange
    4. TicketTokenProvider          — ``op_auth_ticket``, redeem + IAM/ISV exchange

``ServerCredentialProvider`` is NOT a user-auth type: it is reached only via the
non-production env-gated fallback or the internal redeem call.
"""

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.app.auth.cache import TokenCache
from src.app.auth.token_exchange import detect_auth_type, exchange_api_key, exchange_refresh_artifact
from src.app.auth.token_utils import decode_jwt_token

logger = logging.getLogger(__name__)

# IDP grant types for the refresh-artifact exchange (auth type 3).
_IAM_GRANT_TYPE = "urn:ibm:params:oauth:grant-type:delegated-refresh-token"
_ISV_GRANT_TYPE = "refresh_token"


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
    Type 2 (WXO) flow: use the token as-is from the ``op_auth_header`` context var.

    The token comes directly from the OP-embedded chat and is used without
    modification.
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


class AuthorizationHeaderProvider(PassthroughTokenProvider):
    """
    Type 1 flow: use the raw HTTP ``Authorization`` header value as-is.

    Behaviourally identical to the passthrough provider (no exchange, no retry);
    the distinct class exists to label the source for logging and tests.
    """

    async def resolve(self) -> str:
        logger.info("Using passthrough token from HTTP Authorization header")
        return self._token


class ApiKeyTokenProvider(AuthProvider):
    """
    Type 4 (Same IDP) flow: exchange an API key for a token, with caching.

    Checks the shared TokenCache first; on miss, exchanges the API key at the same
    IDP and caches the resulting bearer. ``refresh()`` evicts and re-exchanges.
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


class TicketTokenProvider(AuthProvider):
    """
    Type 3 (embedded-chat ticket) flow — per-pod local session cache, no shared store.

    Each pod maintains its own session entirely in the in-process ``TokenCache``,
    keyed by ``sha256(ticket)``. The OpenPages ``redeemTicket`` endpoint is
    **multi-use**, so any pod may redeem the same ticket independently; the ticket
    stays valid for as long as its bound IDP refresh artifact is alive.

    resolve():
      1. local in-process TokenCache hit (by ticket hash) → return.
      2. miss → redeem the ticket → exchange the artifact for a user bearer →
         cache it with TTL = the exchanged token's lifetime → return.

    refresh() (on 401 / expiry): evict the local entry and re-redeem + re-exchange.
    Re-redeeming is safe because the ticket is multi-use and lives until the
    artifact expires; once the artifact dies the redeem fails and the front-end
    re-issues a fresh ticket.

    Keying is per ``sha256(ticket)`` so one user's bearer is never served to another.
    """

    def __init__(self, ticket: str, client: Any, settings: Any, local_cache: TokenCache):
        self._ticket = ticket
        self._client = client
        self._settings = settings
        self._local_cache = local_cache
        self._h = hashlib.sha256(ticket.encode()).hexdigest()[:32]
        self._cache_key = f"ticket:{self._h}"
        self._skew = int(getattr(settings, "AUTH_TOKEN_EXP_SKEW_SECONDS", 60))
        # Short, non-reversible correlation id for logs (NOT the ticket itself).
        self._tid = self._h[:8]

    # ── public AuthProvider API ───────────────────────────────────────────────

    async def resolve(self) -> str:
        cached = self._local_cache.get(self._cache_key)
        if cached:
            logger.info("Ticket auth [%s]: local cache HIT — using cached user token", self._tid)
            return cached
        logger.info("Ticket auth [%s]: local cache MISS — redeeming + exchanging", self._tid)
        return await self._redeem_and_exchange()

    def can_retry(self) -> bool:
        return True

    async def refresh(self) -> Optional[str]:
        self._local_cache.evict(self._cache_key)
        logger.info(
            "Ticket auth [%s]: refresh requested (e.g. 401) — evicted local token, re-redeeming",
            self._tid,
        )
        return await self._redeem_and_exchange()

    # ── internal helpers ──────────────────────────────────────────────────────

    async def _redeem_and_exchange(self) -> str:
        logger.info("Ticket auth [%s]: calling OpenPages redeemTicket (server creds)", self._tid)
        redeem = await self._client.redeem_ticket(self._ticket)
        # ``mode`` from the redeem response only tells us what the artifact IS:
        #   "access_token" → it is already the user's access token (use directly);
        #   anything else   → it is a refresh artifact that must be exchanged at the IDP.
        # The exchange grant flow is NOT taken from here — it is derived from the IDP
        # URL type inside _exchange().
        mode = (redeem.get("mode") or "").lower()
        refresh_artifact = redeem["refreshArtifact"]

        if mode == "access_token":
            # IBM Cloud IAM passthrough: the artifact IS the user's access token — use it directly
            # as the bearer, no IDP exchange (OP REST accepts the raw IAM token).
            bearer = f"Bearer {refresh_artifact}"
            expires_in = await self._access_token_lifetime(refresh_artifact)
            if expires_in <= self._skew:
                # Classic IBM Cloud IAM has no refresh artifact to exchange — the access token IS
                # the credential. If it is already expired (or within the safety skew), we cannot
                # recover here: re-redeeming the same ticket yields the same dead token. Fail fast
                # with a clear message so the front-end re-issues a ticket from a live session,
                # instead of presenting a stale bearer that OP REST rejects with an opaque 401.
                raise RuntimeError(
                    f"Ticket auth [{self._tid}]: redeemed user access token is expired "
                    f"(remaining={expires_in}s) — a fresh ticket is required "
                    f"(the user's OpenPages session token must be renewed)."
                )
            logger.debug("Ticket auth [%s]: redeem OK (mode=access_token) — using token directly (no IDP exchange)", self._tid)
        else:
            logger.debug("Ticket auth [%s]: redeem OK (mode=%s) — exchanging refresh artifact at IDP", self._tid, mode or "?")
            bearer, expires_in = await self._exchange(refresh_artifact)

        ttl = max(int(expires_in) - self._skew, 0)
        if ttl > 0:
            self._local_cache.set(self._cache_key, bearer, ttl=ttl)
        logger.info(
            "Ticket auth [%s]: user token ready (expires_in=%ss), cached locally (ttl=%ss)",
            self._tid, expires_in, ttl,
        )
        return bearer

    async def _access_token_lifetime(self, token: str) -> int:
        """Remaining lifetime (seconds) of a JWT access token from its ``exp`` claim.

        Falls back to the configured local-cache TTL if the token isn't a decodable JWT or has
        no ``exp``. No signature verification — the token was already validated by OpenPages/IAM.
        """
        default = int(getattr(self._settings, "AUTH_TOKEN_CACHE_TTL", 3600))
        try:
            claims = await decode_jwt_token(token)
            if claims and "exp" in claims:
                # Honor the token's real exp. If it is already expired (<= 0), return 0 so the
                # caller neither caches nor keeps serving a dead token — a stale access token must
                # force a fresh ticket, not be replayed for the default TTL. Only undecodable /
                # exp-less tokens fall back to the configured default below.
                remaining = int(float(claims["exp"]) - time.time())
                return max(remaining, 0)
        except Exception:
            logger.debug("Ticket auth [%s]: could not read access token exp; using default ttl", self._tid)
        return default

    def _resolve_idp_token_url(self) -> str:
        """The IDP token endpoint for the exchange: OPENPAGES_USER_IDP_TOKEN_URL if set,
        otherwise fall back to OPENPAGES_AUTHENTICATION_URL (the same IDP in the common
        IBM Cloud case)."""
        s = self._settings
        return (
            getattr(s, "OPENPAGES_USER_IDP_TOKEN_URL", "")
            or getattr(s, "OPENPAGES_AUTHENTICATION_URL", "")
        )

    async def _exchange(self, refresh_artifact: str) -> tuple:
        """Exchange the refresh artifact for a bearer. Returns (bearer, expires_in).

        The grant flow is derived from the resolved IDP URL's type: IBM Cloud IAM uses
        the delegated-refresh-token grant; every other IDP uses the RFC 8693
        refresh_token grant.
        """
        s = self._settings
        endpoint = self._resolve_idp_token_url()
        # The IDP token endpoint has no hardcoded default — fail fast rather than
        # POSTing to an empty URL.
        if not endpoint:
            raise RuntimeError(
                "Ticket exchange requires an IDP token endpoint, but neither "
                "OPENPAGES_USER_IDP_TOKEN_URL nor OPENPAGES_AUTHENTICATION_URL is configured"
            )
        # Grant mechanics follow the IDP family inferred from the URL.
        grant_style = "iam" if detect_auth_type(endpoint) == "ibm_cloud" else "isv"
        grant_type = _IAM_GRANT_TYPE if grant_style == "iam" else _ISV_GRANT_TYPE
        client_id = getattr(s, "OPENPAGES_OAUTH_CLIENT_ID", "")
        client_secret = (
            s.OPENPAGES_OAUTH_CLIENT_SECRET.get_secret_value()
            if getattr(s, "OPENPAGES_OAUTH_CLIENT_SECRET", None)
            else ""
        )
        # The confidential OAuth client credentials are required for an IDP exchange and have
        # no defaults — fail fast rather than calling the IDP with empty credentials.
        if not client_id or not client_secret:
            raise RuntimeError(
                "Ticket exchange requires the confidential OAuth client credentials, "
                "but OPENPAGES_OAUTH_CLIENT_ID and/or OPENPAGES_OAUTH_CLIENT_SECRET "
                "(or their *_FILE) are not configured"
            )
        # Non-secret exchange parameters — handy for verifying the right IDP/client/audience.
        logger.debug(
            "Ticket auth [%s]: IDP exchange — endpoint=%s grant=%s client_id=%s audience=%s",
            self._tid, endpoint, grant_style, client_id,
            getattr(s, "OPENPAGES_OAUTH_AUDIENCE", None) or "(unset)",
        )
        access_token, expires_in = await exchange_refresh_artifact(
            idp_token_endpoint=endpoint,
            grant_type=grant_type,
            refresh_artifact=refresh_artifact,
            grant_style=grant_style,
            client_id=client_id,
            client_secret=client_secret,
            audience=getattr(s, "OPENPAGES_OAUTH_AUDIENCE", None) or None,
            ssl_verify=getattr(s, "SSL_VERIFY", True),
        )
        bearer = f"Bearer {access_token}"
        return bearer, expires_in


class ServerCredentialProvider(AuthProvider):
    """
    Internal/fallback only: marker that server credentials should be used.

    Returns "" to signal the OpenPages client should use its own configured
    credentials (``self.headers``). Reached only via the env-gated non-production
    fallback — never as a user-auth type in production.
    """

    def __init__(self):
        from src.app.config.settings import settings
        self.settings = settings
        self.username = None

    async def resolve(self) -> str:
        logger.debug("Using server-configured credentials")
        if self.settings.OPENPAGES_AUTHENTICATION_TYPE == "basic":
            self.username = self.settings.OPENPAGES_USERNAME
            logger.debug("Extracted user ID from basic auth")
        return ""

    def can_retry(self) -> bool:
        return False

    async def refresh(self) -> Optional[str]:
        return None

    def get_username(self) -> Optional[str]:
        """Get the username for logging purposes."""
        return self.username
