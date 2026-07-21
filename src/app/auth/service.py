"""
Auth Service Module

Central coordinator that resolves authentication for each tool request.

Implements an ordered, pluggable resolver over four auth types, in fixed priority:
    1. HTTP ``Authorization`` bearer  (AuthorizationHeaderProvider)
    2. ``op_auth_header`` context var (PassthroughTokenProvider)
    3. ``op_auth_ticket`` context var (TicketTokenProvider, redeem + IAM/ISV exchange)
    4. API key in a configurable header (ApiKeyTokenProvider, same-IDP exchange)

The ticket outranks the API key: in the Orchestrate flow the API key secures the
*connection* (channel gate) while per-call tool execution binds to the user's
``op_auth_ticket``.

Fail-fast: the highest-priority artifact *present* is authoritative; if it fails
validation/exchange/redeem the request is rejected — never downgraded to a
lower-priority credential.

Server-credential deployments (``OPENPAGES_AUTH_MODE=server`` — dev / local stdio /
on-prem, typically basic auth) bypass this user-auth framework entirely: the resolver
short-circuits to the server's own credentials and never inspects incoming artifacts
(``OPENPAGES_AUTHENTICATION_TYPE`` only selects the *kind* of server credential —
basic vs bearer — and does not participate in resolution). In user-auth mode the four
types above apply and an artifact-less request is rejected. The internal
``redeemTicket`` call bypasses this resolver.
"""

import logging
from typing import Optional

from src.app.auth.cache import TokenCache
from src.app.auth.providers import (
    ApiKeyTokenProvider,
    AuthProvider,
    AuthorizationHeaderProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
    TicketTokenProvider,
)
from src.app.auth.token_validator import PassthroughTokenValidator
from src.app.auth.token_utils import extract_user_id_from_token

logger = logging.getLogger(__name__)

# Upper bounds on attacker-controlled auth artifacts, enforced fail-fast at ingress so an
# oversized value is rejected before any hashing / redeem / IDP round-trip. This is
# defense-in-depth — the HTTP layer already caps header sizes — and keeps a malformed input
# from doing work. The ticket additionally has a fixed OpenPages format.
_TICKET_PREFIX = "opct_"  # must match grc-core TicketCache.TICKET_PREFIX
_MAX_TICKET_LENGTH = 256  # a real ticket is ~32 chars (opct_ + base64url of 20 random bytes)
_MAX_API_KEY_LENGTH = 8192  # IDP-dependent and can be long; bound rejects megabyte payloads


class PassthroughAuthError(Exception):
    """Raised when a user auth artifact is required/present but unusable, and no
    lower-priority credential may be substituted (fail-fast)."""
    pass


class AuthResult:
    """Encapsulates resolved auth + retry capability + user identity."""

    def __init__(self, token: Optional[str], provider: AuthProvider, username: Optional[str] = None):
        self._token = token
        self.provider = provider
        self.username = username

    @property
    def auth_override(self) -> Optional[str]:
        """
        Returns the token string to pass as auth_override, or None for server creds.

        Empty string from ServerCredentialProvider is treated as None.
        """
        if self._token:
            return self._token
        return None

    async def retry(self) -> Optional[str]:
        """On 401, attempt refresh. Returns new token or None."""
        if not self.provider.can_retry():
            return None
        new_token = await self.provider.refresh()
        if new_token:
            self._token = new_token
        return new_token


class AuthService:
    """
    Central authentication coordinator.

    Resolves the correct authentication strategy for each request based on the
    artifact presented, following the fixed precedence 1 > 2 > 3 > 4 and failing
    fast on the highest-priority present artifact.
    """

    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client
        self._token_validator = PassthroughTokenValidator()

        # Shared per-process token cache for types 3 & 4 (constructed once). Type 3
        # ticket sessions live entirely in this per-pod cache — no shared store.
        self._token_cache = TokenCache(
            default_ttl=getattr(settings, "AUTH_TOKEN_CACHE_TTL", 3600),
            max_size=getattr(settings, "AUTH_TOKEN_CACHE_MAX_SIZE", 100),
        )

    async def _extract_and_log_username(self, token: Optional[str], source: str) -> Optional[str]:
        """Extract a user id from a token for logging (best-effort)."""
        if not token:
            return None
        user_id = await extract_user_id_from_token(token)
        if user_id:
            logger.debug(f"Extracted user ID from {source}")
        else:
            logger.debug(f"Could not extract user ID from {source} (may not be JWT)")
        return user_id

    async def resolve_for_request(
        self,
        authorization: Optional[str] = None,
        op_auth_header: Optional[str] = None,
        has_op_auth_header: bool = False,
        api_key: Optional[str] = None,
        op_auth_ticket: Optional[str] = None,
        has_op_auth_ticket: bool = False,
        # Legacy aliases (back-compat with the previous 2-flow signature).
        context_token: Optional[str] = None,
        has_context_token_key: bool = False,
    ) -> AuthResult:
        """
        Resolve auth for a single tool invocation in fixed priority order.

        Args:
            authorization: Type 1 — raw HTTP ``Authorization`` header value.
            op_auth_header: Type 2 — ``op_auth_header`` context var value.
            has_op_auth_header: Whether the ``op_auth_header`` key was present.
            op_auth_ticket: Type 3 — ``op_auth_ticket`` context var value (redeem + IAM/ISV exchange).
            has_op_auth_ticket: Whether the ``op_auth_ticket`` key was present.
            api_key: Type 4 — raw API key from the configured header (same-IDP exchange).
            context_token / has_context_token_key: Legacy aliases for type 2.

        Returns:
            AuthResult with resolved token, provider, and (best-effort) username.

        Raises:
            PassthroughAuthError: A present user artifact is empty/unusable, or no
                user artifact is present in production remote mode.
            TokenValidationError: A present passthrough token failed validation.
        """
        # Fold legacy aliases into type 2.
        if context_token is not None or has_context_token_key:
            op_auth_header = op_auth_header if op_auth_header is not None else context_token
            has_op_auth_header = has_op_auth_header or has_context_token_key

        # ── Server-credential deployments: bypass the user-auth framework ────
        # When the deployment runs entirely on its own credentials (OPENPAGES_AUTH_MODE=server,
        # e.g. a basic-auth on-prem / local / dev install) the per-user resolver (types 1-4)
        # does not apply at all. OPENPAGES_AUTHENTICATION_TYPE only selects the *kind* of
        # server credential (basic vs bearer); it must never feed the user-auth resolver. Any
        # incoming Authorization / api-key / ticket is at most a channel-gate credential (and
        # the connection gate is itself skipped in this posture), so we resolve straight to
        # server credentials without inspecting those artifacts. This is not a downgrade —
        # in server-credential mode there is no user-auth path to begin with.
        if self._server_cred_fallback_allowed():
            logger.info("Server-credential deployment; using server credentials (user-auth resolver bypassed)")
            provider = ServerCredentialProvider()
            username = provider.get_username() if hasattr(provider, "get_username") else None
            token = await provider.resolve()
            if not username and token:
                username = await self._extract_and_log_username(token, "server bearer token")
            return AuthResult(token or None, provider, username)

        # ── Priority 1: HTTP Authorization bearer ────────────────────────────
        if authorization:
            await self._token_validator.validate(authorization)
            logger.info("Auth resolved via HTTP Authorization header (type 1)")
            username = await self._extract_and_log_username(authorization, "Authorization header")
            return AuthResult(authorization, AuthorizationHeaderProvider(authorization), username)

        # ── Priority 2: op_auth_header context var ───────────────────────────
        if has_op_auth_header or op_auth_header:
            if not op_auth_header:
                raise PassthroughAuthError(
                    "op_auth_header key present but token is empty — "
                    "cannot fall back to a lower-priority credential (fail-fast)"
                )
            await self._token_validator.validate(op_auth_header)
            logger.info("Auth resolved via op_auth_header context variable (type 2)")
            username = await self._extract_and_log_username(op_auth_header, "passthrough JWT token")
            return AuthResult(op_auth_header, PassthroughTokenProvider(op_auth_header), username)

        # ── Priority 3: op_auth_ticket (redeem + exchange) ───────────────────
        # Deployment-driven: there is no enable/disable toggle. The ticket is only ever present
        # when the OpenPages deployment issued one (SaaS / Cloud Pak); if it's here, we honor it.
        if has_op_auth_ticket or op_auth_ticket:
            if not op_auth_ticket:
                raise PassthroughAuthError(
                    "op_auth_ticket key present but ticket is empty — "
                    "cannot fall back to a lower-priority credential (fail-fast)"
                )
            # Validate format/length before doing any work. Reject (fail-fast) rather than
            # downgrade — the ticket value is never logged.
            if len(op_auth_ticket) > _MAX_TICKET_LENGTH or not op_auth_ticket.startswith(_TICKET_PREFIX):
                raise PassthroughAuthError(
                    "op_auth_ticket is malformed (unexpected prefix or length) — "
                    "cannot fall back to a lower-priority credential (fail-fast)"
                )
            if self.client is None:
                raise PassthroughAuthError("Ticket auth requires an OpenPages client for redeem")
            logger.info("Auth resolved via op_auth_ticket context variable (type 3)")
            provider = TicketTokenProvider(
                op_auth_ticket,
                self.client,
                self.settings,
                self._token_cache,
            )
            token = await provider.resolve()
            username = await self._extract_and_log_username(token, "ticket-exchanged token")
            return AuthResult(token or None, provider, username)

        # ── Priority 4: API key (same-IDP exchange) ──────────────────────────
        if api_key:
            # Bound the attacker-controlled key before hashing/exchange (fail-fast; key never logged).
            if len(api_key) > _MAX_API_KEY_LENGTH:
                raise PassthroughAuthError(
                    "API key exceeds the maximum accepted length — rejecting (fail-fast)"
                )
            logger.info("Auth resolved via API key header (type 4)")
            # On AWS Marketplace the shared OPENPAGES_AUTHENTICATION_URL only accepts
            # service-level keys, so a user-presented key is exchanged at the
            # instance-specific MCSP endpoint instead. Every other environment keeps
            # using OPENPAGES_AUTHENTICATION_URL. (The internal MCP→OpenPages call that
            # exchanges the server's own OPENPAGES_APIKEY is unaffected — it does not
            # pass through this resolver.)
            resolve_url = getattr(self.settings, "resolve_user_apikey_auth_url", None)
            auth_url = (
                resolve_url()
                if callable(resolve_url)
                else getattr(self.settings, "OPENPAGES_AUTHENTICATION_URL", "")
            )
            provider = ApiKeyTokenProvider(
                api_key,
                self._token_cache,
                auth_url,
                getattr(self.settings, "SSL_VERIFY", True),
            )
            token = await provider.resolve()
            username = await self._extract_and_log_username(token, "exchanged API-key token")
            return AuthResult(token or None, provider, username)

        # ── No user artifact present in user-auth mode: reject (fail-fast) ───
        # Server-credential deployments were already resolved at the top of this method;
        # reaching here means we are in user-auth mode with no usable artifact.
        raise PassthroughAuthError(
            "No user authentication present and server-credential fallback is "
            "disabled in production remote mode"
        )

    def _server_cred_fallback_allowed(self) -> bool:
        """Server creds may stand in for a user only in server-credential deployments
        (dev / local stdio / on-prem); production-remote SaaS rejects artifact-less calls."""
        return self.settings.uses_server_credentials()
