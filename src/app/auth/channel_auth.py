"""
Connection Gate (connection-level ingress auth)

A lightweight gate on every HTTP request to the MCP endpoint (including
``initialize``/``tools/list``/``ping``) so no fully-anonymous caller can establish
a session. The rule is deliberately simple:

  * **Server-credential deployments** (dev / local stdio / on-prem — see
    ``settings.uses_server_credentials()``) run entirely on the server's own
    credentials, so the gate is **skipped** — no header is required.
  * **Everywhere else** (production-remote SaaS) a request is allowed iff a
    credential is present in a request **header**: the ``Authorization`` header
    (type 1) or any configured API-key header (type 3, ``get_apikey_header_names()``).
    Otherwise the connection is rejected with 401.

This is the **channel** layer (is the caller allowed to connect?), distinct from
the per-call **user** resolver in ``AuthService`` (which OP user?). The gate looks
only at headers; the body context vars ``op_auth_header``/``op_auth_ticket`` (types
2 & 4) are not inspected here — in the Orchestrate flow the API-key header secures
the connection while the higher-priority ``op_auth_ticket`` drives tool calls.

No credential value is ever logged.
"""

import logging

from fastapi import HTTPException, Request

from src.app.config.settings import settings

logger = logging.getLogger(__name__)


def _has_user_header(request: Request) -> bool:
    """Whether a user credential header is present (type 1 Authorization or type 3 API key)."""
    if request.headers.get("Authorization"):
        return True
    for header_name in settings.get_apikey_header_names():
        if request.headers.get(header_name):
            return True
    return False


async def require_channel_auth(request: Request) -> None:
    """FastAPI dependency: require a header credential to connect, except for
    server-credential deployments where the gate is skipped.

    Raises:
        HTTPException(401): If the gate is enforced and no accepted credential is present.
    """
    if settings.uses_server_credentials():
        # dev / local / on-prem: server credentials run everything, no gate.
        return

    if _has_user_header(request):
        return

    logger.warning("Rejecting connection: no Authorization or API-key header present")
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
