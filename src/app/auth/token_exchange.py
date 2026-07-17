"""
Token Exchange Module

Standalone async functions for exchanging credentials for tokens
across IBM Cloud IAM, MCSP, and CP4D authentication services.
"""

import asyncio
import base64
import logging
from typing import Optional, Tuple

import httpx  # type: ignore

logger = logging.getLogger(__name__)

# Retry configuration for DNS resolution issues during pod startup
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0  # seconds


def detect_auth_type(authentication_url: str) -> str:
    """
    Detect authentication type based on the authentication URL.

    Args:
        authentication_url: The authentication URL

    Returns:
        Either 'ibm_cloud', 'mcsp', or 'cp4d'
    """
    if '/icp4d-api/v1/authorize' in authentication_url:
        logger.debug("Detected CP4D authentication")
        return 'cp4d'
    elif 'iam.cloud.ibm.com' in authentication_url or 'iam.test.cloud.ibm.com' in authentication_url:
        logger.debug("Detected IBM Cloud OAuth2 authentication")
        return 'ibm_cloud'
    elif 'account-iam.platform' in authentication_url or 'saas.ibm.com' in authentication_url:
        logger.debug("Detected MCSP OAuth2 authentication")
        return 'mcsp'
    else:
        logger.warning(f"Could not detect auth type from URL: {authentication_url}. Defaulting to IBM Cloud.")
        return 'ibm_cloud'


async def _retry_with_backoff(func, *args, **kwargs):
    """
    Retry a function with exponential backoff.
    Handles DNS resolution failures during pod startup and rate limiting errors.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
    
    Returns:
        Result from func
    
    Raises:
        RuntimeError: If all retries fail
    """
    last_exception = None
    backoff = INITIAL_BACKOFF
    
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            last_exception = e
            # Check if it's a rate limiting error (429 Too Many Requests)
            if e.response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Rate limit exceeded (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
            # For other HTTP errors, re-raise immediately
            raise
        except httpx.RequestError as e:
            last_exception = e
            # Check if it's a DNS resolution error
            if "Temporary failure in name resolution" in str(e) or "[Errno -3]" in str(e):
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"DNS resolution failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                    continue
            # For other network errors, re-raise immediately
            raise
        except Exception as e:
            # For non-network errors, re-raise immediately
            raise
    
    # All retries exhausted
    raise RuntimeError(
        f"Failed after {MAX_RETRIES} attempts. Last error: {last_exception}"
    ) from last_exception


async def fetch_ibm_cloud_token(api_key: str, auth_url: str) -> str:
    """
    Exchange API key for IBM Cloud IAM token.
    Includes retry logic for DNS resolution issues during pod startup.

    Args:
        api_key: IBM Cloud API key
        auth_url: IBM Cloud IAM token endpoint

    Returns:
        Access token string

    Raises:
        RuntimeError: If token exchange fails
    """
    async with httpx.AsyncClient(verify=True) as client:
        async def _fetch():
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            data = {
                'grant_type': 'urn:ibm:params:oauth:grant-type:apikey',
                'apikey': api_key
            }
            logger.debug(f"Fetching IBM Cloud token from {auth_url}")
            response = await client.post(auth_url, headers=headers, data=data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            if 'access_token' in token_data:
                logger.debug("Successfully obtained IBM Cloud access token")
                return token_data['access_token']
            else:
                raise RuntimeError("'access_token' not found in IBM Cloud response")

        try:
            return await _retry_with_backoff(_fetch)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error fetching IBM Cloud token: {e}")
            raise RuntimeError(f"IBM Cloud token exchange failed ({e.response.status_code}): {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error fetching IBM Cloud token: {e}")
            raise RuntimeError(f"Network error during IBM Cloud token exchange: {e}") from e


async def fetch_mcsp_token(api_key: str, auth_url: str) -> str:
    """
    Exchange API key for MCSP token.
    Includes retry logic for DNS resolution issues during pod startup.

    Args:
        api_key: MCSP API key
        auth_url: MCSP token endpoint

    Returns:
        Access token string

    Raises:
        RuntimeError: If token exchange fails
    """
    async with httpx.AsyncClient(verify=True) as client:
        async def _fetch():
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            json_data = {
                'apikey': api_key
            }
            logger.debug(f"Fetching MCSP token from {auth_url}")
            response = await client.post(auth_url, headers=headers, json=json_data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            if 'token' in token_data:
                logger.debug("Successfully obtained MCSP token")
                return token_data['token']
            else:
                raise RuntimeError("'token' not found in MCSP response")

        try:
            return await _retry_with_backoff(_fetch)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error fetching MCSP token: {e}")
            raise RuntimeError(f"MCSP token exchange failed ({e.response.status_code}): {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error fetching MCSP token: {e}")
            raise RuntimeError(f"Network error during MCSP token exchange: {e}") from e


async def fetch_cp4d_token(username: str, password: str, auth_url: str, ssl_verify: bool = True) -> str:
    """
    Exchange credentials for CP4D token.
    Includes retry logic for DNS resolution issues during pod startup.

    Args:
        username: CP4D username
        password: CP4D password
        auth_url: CP4D authorization endpoint
        ssl_verify: Whether to verify SSL certificates

    Returns:
        Access token string

    Raises:
        RuntimeError: If token exchange fails
    """
    if not ssl_verify:
        logger.warning("SSL verification is disabled for CP4D authentication")
    async with httpx.AsyncClient(verify=ssl_verify) as client:
        async def _fetch():
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            json_data = {
                'username': username,
                'password': password
            }
            logger.debug(f"Fetching CP4D token from {auth_url}")
            response = await client.post(auth_url, headers=headers, json=json_data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            if 'token' in token_data:
                logger.debug("Successfully obtained CP4D token")
                return token_data['token']
            else:
                raise RuntimeError("'token' not found in CP4D response")

        try:
            return await _retry_with_backoff(_fetch)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error fetching CP4D token: {e}")
            raise RuntimeError(f"CP4D token exchange failed ({e.response.status_code}): {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error fetching CP4D token: {e}")
            raise RuntimeError(f"Network error during CP4D token exchange: {e}") from e


async def exchange_api_key(api_key: str, auth_url: str, ssl_verify: bool = True) -> str:
    """
    High-level API key exchange (auth type 4): detect IDP type and fetch a token.

    Used by ApiKeyTokenProvider to exchange a same-IDP API key (presented in the
    configured custom header, default ``X-Api-Key``) for an OpenPages-usable token.

    Args:
        api_key: API key to exchange
        auth_url: Authentication URL (used to detect auth type)
        ssl_verify: Whether to verify SSL certificates (reserved; the underlying
            IBM Cloud/MCSP fetchers verify by default)

    Returns:
        Access token string

    Raises:
        ValueError: If the detected auth type does not support API key exchange
        RuntimeError: If token exchange fails
    """
    auth_type = detect_auth_type(auth_url)

    if auth_type == 'ibm_cloud':
        return await fetch_ibm_cloud_token(api_key, auth_url)
    elif auth_type == 'mcsp':
        return await fetch_mcsp_token(api_key, auth_url)
    else:
        raise ValueError(f"API key exchange not supported for auth type: {auth_type}")


async def exchange_refresh_artifact(
    *,
    idp_token_endpoint: str,
    grant_type: str,
    refresh_artifact: str,
    grant_style: str,
    client_id: str,
    client_secret: str,
    audience: Optional[str] = None,
    ssl_verify: bool = True,
) -> Tuple[str, int]:
    """
    Exchange a pre-minted IDP refresh artifact for a user-scoped access token (auth type 3).

    The ``grant_style`` selects the wire protocol — it is derived by the caller from the
    IDP URL type (``detect_auth_type``), not from the redeem response:

    - ``iam`` — IBM Cloud IAM delegated-refresh-token redemption. Authenticates as
      the shared confidential OAuth client via HTTP Basic and passes
      ``receiver_client_ids`` (the API client / audience).
    - ``isv`` — RFC 8693 / OIDC refresh-token grant against the token endpoint, with
      ``client_id``/``client_secret`` in the form body.

    Args:
        idp_token_endpoint: Full IDP token endpoint URL.
        grant_type: OAuth grant_type to use (grant_style-specific; see B6).
        refresh_artifact: The opaque refresh artifact minted at chat-open.
        grant_style: ``"iam"`` or ``"isv"``.
        client_id: Shared OAuth confidential client id.
        client_secret: Shared OAuth confidential client secret.
        audience: API client id / audience (defaults to ``client_id`` for IAM).
        ssl_verify: Whether to verify SSL certificates.

    Returns:
        Tuple of (access_token, expires_in_seconds).

    Raises:
        ValueError: If ``grant_style`` is unrecognized.
        RuntimeError: If the exchange fails or no token is returned.
    """
    normalized_style = (grant_style or "").lower()
    if normalized_style not in ("iam", "isv"):
        raise ValueError(f"Unsupported refresh-artifact exchange grant_style: {grant_style!r}")

    # Build request headers and body once — fixed for all retry attempts.
    # client_secret is consumed here and deleted immediately so it does not
    # linger in memory across the retry loop or the network call.
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    }
    data: dict = {
        'grant_type': grant_type,
        'refresh_token': refresh_artifact,
    }

    if normalized_style == "iam":
        # Confidential client authenticates via HTTP Basic; API client is the receiver.
        data['receiver_client_ids'] = audience or client_id
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        del client_secret  # clear raw secret as soon as it is encoded
        headers['Authorization'] = f"Basic {basic}"
    else:  # isv
        data['client_id'] = client_id
        data['client_secret'] = client_secret
        del client_secret  # clear raw secret as soon as it is copied into form data
        if audience:
            data['audience'] = audience

    async with httpx.AsyncClient(verify=ssl_verify) as http_client:
        async def _fetch() -> Tuple[str, int]:
            logger.debug(f"Exchanging refresh artifact at {idp_token_endpoint} (grant_style={normalized_style})")
            response = await http_client.post(idp_token_endpoint, headers=headers, data=data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            # Defensive parsing: access_token per RFC 8693, else legacy fields.
            access_token = (
                token_data.get('access_token')
                or token_data.get('token')
            )
            if not access_token:
                raise RuntimeError("No access token found in refresh-artifact exchange response")

            try:
                expires_in = int(token_data.get('expires_in', 3600))
            except (TypeError, ValueError):
                expires_in = 3600

            logger.debug("Successfully exchanged refresh artifact for access token")
            return access_token, expires_in

        try:
            return await _retry_with_backoff(_fetch)
        except httpx.HTTPStatusError as e:
            logger.error(f"Error exchanging refresh artifact: {e}")
            raise RuntimeError(
                f"Refresh-artifact exchange failed ({e.response.status_code}): {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Request error exchanging refresh artifact: {e}")
            raise RuntimeError(f"Network error during refresh-artifact exchange: {e}") from e
