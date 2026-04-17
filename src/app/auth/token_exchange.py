"""
Token Exchange Module

Standalone async functions for exchanging credentials for tokens
across IBM Cloud IAM, MCSP, and CP4D authentication services.
"""

import logging
from typing import Optional

import httpx  # type: ignore

logger = logging.getLogger(__name__)


def detect_auth_type(authentication_url: str) -> str:
    """
    Detect authentication type based on the authentication URL.

    Args:
        authentication_url: The authentication URL

    Returns:
        Either 'ibm_cloud', 'mcsp', or 'cp4d'
    """
    if '/icp4d-api/v1/authorize' in authentication_url in authentication_url:
        logger.info("Detected CP4D authentication")
        return 'cp4d'
    elif 'iam.cloud.ibm.com' in authentication_url or 'iam.test.cloud.ibm.com' in authentication_url:
        logger.info("Detected IBM Cloud OAuth2 authentication")
        return 'ibm_cloud'
    elif 'account-iam.platform' in authentication_url or 'saas.ibm.com' in authentication_url:
        logger.info("Detected MCSP OAuth2 authentication")
        return 'mcsp'
    else:
        logger.warning(f"Could not detect auth type from URL: {authentication_url}. Defaulting to IBM Cloud.")
        return 'ibm_cloud'


async def fetch_ibm_cloud_token(api_key: str, auth_url: str) -> str:
    """
    Exchange API key for IBM Cloud IAM token.

    Args:
        api_key: IBM Cloud API key
        auth_url: IBM Cloud IAM token endpoint

    Returns:
        Access token string

    Raises:
        RuntimeError: If token exchange fails
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    data = {
        'grant_type': 'urn:ibm:params:oauth:grant-type:apikey',
        'apikey': api_key
    }

    try:
        async with httpx.AsyncClient(verify=True) as client:
            logger.info(f"Fetching IBM Cloud token from {auth_url}")
            response = await client.post(auth_url, headers=headers, data=data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            if 'access_token' in token_data:
                logger.info("Successfully obtained IBM Cloud access token")
                return token_data['access_token']
            else:
                raise RuntimeError("'access_token' not found in IBM Cloud response")

    except httpx.HTTPStatusError as e:
        logger.error(f"Error fetching IBM Cloud token: {e}")
        raise RuntimeError(f"IBM Cloud token exchange failed ({e.response.status_code}): {e.response.text}") from e
    except httpx.RequestError as e:
        logger.error(f"Request error fetching IBM Cloud token: {e}")
        raise RuntimeError(f"Network error during IBM Cloud token exchange: {e}") from e


async def fetch_mcsp_token(api_key: str, auth_url: str) -> str:
    """
    Exchange API key for MCSP token.

    Args:
        api_key: MCSP API key
        auth_url: MCSP token endpoint

    Returns:
        Access token string

    Raises:
        RuntimeError: If token exchange fails
    """
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    json_data = {
        'apikey': api_key
    }

    try:
        async with httpx.AsyncClient(verify=True) as client:
            logger.info(f"Fetching MCSP token from {auth_url}")
            response = await client.post(auth_url, headers=headers, json=json_data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            if 'token' in token_data:
                logger.info("Successfully obtained MCSP token")
                return token_data['token']
            else:
                raise RuntimeError("'token' not found in MCSP response")

    except httpx.HTTPStatusError as e:
        logger.error(f"Error fetching MCSP token: {e}")
        raise RuntimeError(f"MCSP token exchange failed ({e.response.status_code}): {e.response.text}") from e
    except httpx.RequestError as e:
        logger.error(f"Request error fetching MCSP token: {e}")
        raise RuntimeError(f"Network error during MCSP token exchange: {e}") from e


async def fetch_cp4d_token(username: str, password: str, auth_url: str, ssl_verify: bool = True) -> str:
    """
    Exchange credentials for CP4D token.

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
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    json_data = {
        'username': username,
        'password': password
    }

    try:
        async with httpx.AsyncClient(verify=ssl_verify) as client:
            logger.info(f"Fetching CP4D token from {auth_url}")
            if not ssl_verify:
                logger.warning("SSL verification is disabled for CP4D authentication")
            response = await client.post(auth_url, headers=headers, json=json_data, timeout=30.0)
            response.raise_for_status()
            token_data = response.json()

            if 'token' in token_data:
                logger.info("Successfully obtained CP4D token")
                return token_data['token']
            else:
                raise RuntimeError("'token' not found in CP4D response")

    except httpx.HTTPStatusError as e:
        logger.error(f"Error fetching CP4D token: {e}")
        raise RuntimeError(f"CP4D token exchange failed ({e.response.status_code}): {e.response.text}") from e
    except httpx.RequestError as e:
        logger.error(f"Request error fetching CP4D token: {e}")
        raise RuntimeError(f"Network error during CP4D token exchange: {e}") from e
