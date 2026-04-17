"""
OpenPages API Client
Provides functionality to interact with IBM OpenPages REST API
"""

import asyncio
import logging
import base64
import time
import ssl
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import httpx  # type: ignore
from src.app.config.settings import Settings, settings
from src.app.observability.logger import StructuredLogger, get_logger, log_method_call
from src.app.observability.tracing import (
    start_async_span, set_span_ok, set_span_error, is_tracing_enabled
)
from src.app.observability import metrics as metrics_module

# Type annotation for better error handling
HTTPXError = httpx.HTTPError

def is_ssl_error(error: Exception) -> bool:
    """
    Check if an error is SSL/certificate related
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is SSL-related
    """
    error_str = str(error).lower()
    ssl_indicators = [
        'certificate',
        'ssl',
        'tls',
        'verify failed',
        'certificate_verify_failed',
        'self-signed',
        'hostname mismatch',
        'unable to get local issuer certificate'
    ]
    return any(indicator in error_str for indicator in ssl_indicators)

def get_ssl_error_message(error: Exception, base_url: str) -> str:
    """
    Generate a helpful error message for SSL certificate errors
    
    Args:
        error: The SSL error
        base_url: The OpenPages base URL
        
    Returns:
        Formatted error message with solution
    """
    return (
        f"\n{'='*80}\n"
        f"SSL CERTIFICATE ERROR\n"
        f"{'='*80}\n"
        f"Failed to connect to OpenPages at: {base_url}\n"
        f"Error: {error}\n"
        f"\n"
        f"This typically occurs when:\n"
        f"  1. The server uses a self-signed certificate\n"
        f"  2. The certificate is expired or invalid\n"
        f"  3. The certificate hostname doesn't match the URL\n"
        f"\n"
        f"SOLUTION:\n"
        f"  For development/test environments, you can disable SSL verification:\n"
        f"  1. Add to your .env file: SSL_VERIFY=false\n"
        f"  2. Restart the server\n"
        f"\n"
        f"  WARNING: Only disable SSL verification in non-production environments!\n"
        f"  For production, obtain a valid SSL certificate for your OpenPages server.\n"
        f"{'='*80}\n"
    )

# Configure logging
logger: StructuredLogger = get_logger(__name__)

class OpenPagesClient:
    """Client for interacting with IBM OpenPages API"""
    
    def __init__(self, base_url: str, auth_type: str = "basic", username: Optional[str] = None,
                 password: Optional[str] = None, api_key: Optional[str] = None, authentication_url: Optional[str] = None,
                 custom_settings: Optional[Settings] = None, instance_name: Optional[str] = None):
        """
        Initialize the OpenPages client
        
        Args:
            base_url: Base URL of the OpenPages API
            auth_type: Authentication type, either "basic" or "bearer"
            username: OpenPages username (required if auth_type is "basic" or for CP4D)
            password: OpenPages password (required if auth_type is "basic" or for CP4D)
            api_key: API key for bearer authentication (required if auth_type is "bearer" for IBM Cloud/MCSP)
            authentication_url: Authentication URL for bearer authentication
            custom_settings: Optional custom settings object to use instead of global settings
            instance_name: OpenPages instance name for CP4D deployments (e.g., 'openpagesinstance-with-25')
        """
        # Use provided settings or fall back to global settings
        self.settings = custom_settings if custom_settings else settings
        
        # Validate authentication parameters
        if auth_type.lower() == "basic":
            if not username or not password:
                raise ValueError("Username and password are required for basic authentication")
        elif auth_type.lower() == "bearer":
            if not authentication_url:
                raise ValueError("Authentication URL is required for bearer authentication")
            # Detect if this is CP4D authentication by checking URL pattern
            is_cp4d = '/icp4d-api/v1/authorize' in authentication_url in authentication_url
            if is_cp4d:
                # CP4D uses username/password
                if not username or not password:
                    raise ValueError("Username and password are required for CP4D authentication")
            else:
                # IBM Cloud IAM and MCSP use API key
                if not api_key:
                    raise ValueError("API key is required for bearer authentication (IBM Cloud/MCSP)")
        else:
            raise ValueError("Authentication type must be either 'basic' or 'bearer'")
            
        # Ensure the base URL has the correct protocol
        if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
            base_url = 'https://' + base_url
            logger.info(f"Added https:// protocol to base URL: {base_url}")
            
        self.base_url = base_url.rstrip('/')
        logger.info(f"OpenPagesClient initialized with base URL: {self.base_url}")
        
        # Store authentication parameters for later use
        self.auth_type = auth_type.lower()
        self.username = username
        self.password = password
        self.api_key = api_key
        self.authentication_url = authentication_url
        
        # Set initial headers without Authorization
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Detect if this is CP4D based on authentication URL
        self.is_cp4d = False
        if self.auth_type == "bearer" and authentication_url:
            self.is_cp4d = '/icp4d-api/v1/authorize' in authentication_url in authentication_url
        
        # Set instance name for CP4D
        self.instance_name = None
        if self.is_cp4d:
            # Use provided instance name, or try to extract from base URL, or use from settings
            if instance_name:
                self.instance_name = instance_name
            elif self.settings.OPENPAGES_INSTANCE_NAME:
                self.instance_name = self.settings.OPENPAGES_INSTANCE_NAME
            else:
                self.instance_name = self._extract_instance_name(base_url)
            logger.info(f"Detected CP4D deployment with instance name: {self.instance_name}")
        
        # Async lock for bearer token operations (prevents concurrent token fetches/refreshes)
        self._auth_lock = asyncio.Lock()

        # Shared httpx client for connection pooling (lazily initialized)
        self._http_client: Optional[httpx.AsyncClient] = None
        self._http_client_lock = asyncio.Lock()

        # For basic auth, we can set the auth header immediately
        if self.auth_type == "basic":
            self.auth_header = self._create_basic_auth_header(username, password)
            self.headers['Authorization'] = self.auth_header
        # For bearer auth, we'll set it later in an async method
    
    def _extract_instance_name(self, base_url: str) -> str:
        """
        Extract OpenPages instance name from the base URL for CP4D deployments.
        
        For CP4D, the base URL typically contains the instance name.
        Example: https://cpd-cpd-instance.apps.example.com
        
        Args:
            base_url: Base URL of the OpenPages API
            
        Returns:
            Instance name extracted from URL, or 'instance' as default
        """
        try:
            # Remove protocol
            url_without_protocol = base_url.replace('https://', '').replace('http://', '')
            
            # Split by dots and hyphens to find instance identifier
            # For CP4D URLs like cpd-cpd-instance.apps.example.com
            # We look for patterns after 'cpd-'
            parts = url_without_protocol.split('.')
            if parts:
                first_part = parts[0]  # e.g., 'cpd-cpd-instance'
                # Remove 'cpd-' prefix if present
                if first_part.startswith('cpd-'):
                    instance_part = first_part[4:]  # Remove 'cpd-' prefix
                    # If it starts with 'cpd-' again, remove that too
                    if instance_part.startswith('cpd-'):
                        instance_part = instance_part[4:]
                    if instance_part:
                        logger.info(f"Extracted instance name: {instance_part}")
                        return instance_part
            
            # Default fallback
            logger.warning(f"Could not extract instance name from URL: {base_url}, using 'instance' as default")
            return 'instance'
        except Exception as e:
            logger.error(f"Error extracting instance name: {e}, using 'instance' as default")
            return 'instance'
    
    def _get_api_path(self, endpoint: str) -> str:
        """
        Get the correct API path based on deployment type (CP4D vs standard).
        
        Args:
            endpoint: The API endpoint (e.g., '/api/v2/query')
            
        Returns:
            Full API path with correct prefix
        """
        if self.is_cp4d:
            # CP4D: Just append -opgrc to base URL, then add the endpoint
            # Base URL already contains the instance path (e.g., /openpages-xxx)
            return f"-opgrc{endpoint}"
        else:
            # Standard OpenPages uses: /opgrc/api/v2/...
            return f"/opgrc{endpoint}"
    
    def _create_basic_auth_header(self, username: Optional[str], password: Optional[str]) -> str:
        """
        Create Basic Auth header
        
        Args:
            username: OpenPages username
            password: OpenPages password
            
        Returns:
            Basic auth header string
        """
        if username is None or password is None:
            raise ValueError("Username and password cannot be None for basic authentication")
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
        
    async def _create_bearer_auth_header(self, api_key: Optional[str], authentication_url: Optional[str]) -> str:
        """
        Create Bearer Auth header by fetching a token from IBM Cloud IAM, MCSP, or CP4D
        
        Args:
            api_key: API key for bearer authentication (not used for CP4D)
            authentication_url: URL to use for authentication

        Returns:
            Bearer auth header string
        """
        if authentication_url is None:
            raise ValueError("Authentication URL cannot be None for bearer authentication")

        # Detect if this is CP4D authentication
        auth_type = self._detect_auth_type(authentication_url)
        
        if auth_type == 'cp4d':
            # For CP4D, we use username/password instead of API key
            if not self.username or not self.password:
                raise ValueError("Username and password are required for CP4D authentication")
            # Pass empty string as api_key for CP4D (not used)
            token = await self.fetch_token("", authentication_url)
        else:
            # For IBM Cloud and MCSP, we need an API key
            if api_key is None:
                raise ValueError("API key cannot be None for bearer authentication")
            token = await self.fetch_token(api_key, authentication_url)
            
        if token is None:
            raise ValueError("Failed to obtain token from authentication service")
        return f"Bearer {token}"
    
    def _detect_auth_type(self, authentication_url: str) -> str:
        """
        Detect authentication type based on the authentication URL.
        Delegates to standalone function in token_exchange module.

        Args:
            authentication_url (str): The authentication URL

        Returns:
            str: Either 'ibm_cloud', 'mcsp', or 'cp4d'
        """
        from src.app.auth.token_exchange import detect_auth_type
        return detect_auth_type(authentication_url)
    
    async def fetch_token(self, api_key: str, authentication_url: str) -> Optional[str]:
        """
        Fetch authentication token from IBM Cloud IAM, MCSP, or CP4D service.
        Automatically detects the authentication type based on the URL.
        Delegates to standalone functions in token_exchange module.

        Args:
            api_key (str): The API key to use for authentication (or username:password for CP4D)
            authentication_url (str): The URL to use for authentication

        Returns:
            Optional[str]: The access token if successful, None otherwise
        """
        from src.app.auth.token_exchange import (
            detect_auth_type, fetch_ibm_cloud_token, fetch_mcsp_token, fetch_cp4d_token
        )

        auth_type = detect_auth_type(authentication_url)

        try:
            if auth_type == 'cp4d':
                return await fetch_cp4d_token(
                    self.username, self.password, authentication_url, self.settings.SSL_VERIFY
                )
            elif auth_type == 'ibm_cloud':
                return await fetch_ibm_cloud_token(api_key, authentication_url)
            else:  # mcsp
                return await fetch_mcsp_token(api_key, authentication_url)
        except (RuntimeError, Exception) as e:
            logger.error(f"Error fetching token: {e}")
            return None
    
    @log_method_call(level=logging.DEBUG)
    async def initialize_auth(self):
        """
        Initialize authentication asynchronously.
        This must be called before making any API requests when using bearer authentication.
        Uses double-checked locking to prevent concurrent token fetches.
        """
        if self.auth_type == "bearer" and 'Authorization' not in self.headers:
            async with self._auth_lock:
                # Re-check after acquiring lock — another coroutine may have already initialized
                if 'Authorization' not in self.headers:
                    logger.info("Initializing bearer authentication")
                    self.auth_header = await self._create_bearer_auth_header(self.api_key, self.authentication_url)
                    self.headers['Authorization'] = self.auth_header
                    logger.info("Bearer authentication initialized successfully")
                else:
                    logger.debug("Auth was initialized by another coroutine while waiting for lock")
        else:
            logger.debug(f"Auth already initialized or using basic auth (type: {self.auth_type})")

    async def _get_request_headers(self, auth_override: Optional[str] = None) -> Dict[str, str]:
        """
        Get headers for an API request, optionally overriding the Authorization header.

        Args:
            auth_override: If provided, replaces the Authorization header for this request.
                          If None, uses the server's configured credentials.

        Returns:
            Headers dict for the request
        """
        if auth_override:
            headers = self.headers.copy()
            headers['Authorization'] = auth_override
            return headers
        else:
            await self.initialize_auth()
            return self.headers.copy()

    def _clear_bearer_token(self):
        """
        Remove the cached bearer token from headers, forcing re-authentication
        on the next request via initialize_auth().
        """
        if 'Authorization' in self.headers and self.auth_type == "bearer":
            del self.headers['Authorization']
            logger.info("Cleared cached bearer token for re-authentication")

    async def _get_http_client(self) -> httpx.AsyncClient:
        """
        Get or lazily create a shared httpx.AsyncClient for connection pooling.
        Uses double-checked locking to avoid creating multiple clients.
        """
        if self._http_client is None:
            async with self._http_client_lock:
                if self._http_client is None:
                    max_connections = getattr(self.settings, 'HTTP_MAX_CONNECTIONS', 20)
                    pool_limits = httpx.Limits(
                        max_connections=max_connections,
                        max_keepalive_connections=max_connections,
                    )
                    self._http_client = httpx.AsyncClient(
                        verify=self.settings.SSL_VERIFY,
                        limits=pool_limits,
                    )
                    logger.debug(f"Created shared httpx.AsyncClient (max_connections={max_connections})")
        return self._http_client

    async def close(self):
        """
        Close the shared httpx client and release resources.
        Should be called during application shutdown.
        """
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
            logger.info("Closed shared httpx.AsyncClient")

    async def _request_with_auth_retry(self, method: str, url: str, auth_override: Optional[str] = None, **kwargs) -> httpx.Response:
        """
        Make an HTTP request with automatic 401 retry for server credentials.

        On a 401 HTTPStatusError when using server credentials (auth_override is None),
        clears the cached bearer token, re-authenticates, and retries once.
        Uses double-checked locking so concurrent 401s collapse into a single token refresh.
        Passthrough tokens (auth_override set) are NOT retried — the caller owns that token.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full request URL
            auth_override: Optional auth header override for per-request auth
            **kwargs: Additional arguments passed to httpx (json, timeout, params, etc.)

        Returns:
            httpx.Response object
        """
        # Extract operation name from URL for span naming
        # e.g., "/api/v2/query" -> "query", "/api/v2/contents/123" -> "contents"
        path_parts = url.split('/')
        operation = "api_call"
        for i, part in enumerate(path_parts):
            if part == "v2" and i + 1 < len(path_parts):
                operation = path_parts[i + 1].split('?')[0]  # Remove query params
                break
        
        # Build span attributes
        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "http.method": method,
                "http.url": url,
                "openpages.operation": operation,
            }
            # Add request body size if present
            if "json" in kwargs:
                import json as json_module
                body_str = json_module.dumps(kwargs["json"])
                span_attrs["http.request.body.size"] = len(body_str)
        
        t_start = time.monotonic()
        async with start_async_span(f"openpages.api.{operation}", attributes=span_attrs) as span:
            try:
                request_headers = await self._get_request_headers(auth_override)
                client = await self._get_http_client()

                # Capture the token used for this attempt so we can detect if another
                # coroutine already refreshed it while we wait on the lock.
                token_before_request = self.headers.get('Authorization')

                try:
                    response = await client.request(method, url, headers=request_headers, **kwargs)
                    response.raise_for_status()
                    
                    # Add response attributes
                    duration_ms = (time.monotonic() - t_start) * 1000
                    if span and is_tracing_enabled():
                        span.set_attribute("http.status_code", response.status_code)
                        span.set_attribute("http.response.body.size", len(response.content))
                        # For query operations, try to extract row count
                        if operation == "query" and response.text:
                            try:
                                response_json = response.json()
                                row_count = len(response_json.get("rows", []))
                                span.set_attribute("openpages.row_count", row_count)
                            except Exception:
                                pass  # Ignore JSON parsing errors
                    
                    set_span_ok(span, duration_ms=duration_ms)
                    
                    # Record metrics
                    if metrics_module.is_metrics_enabled():
                        metrics_module.openpages_api_calls_total.labels(
                            method=method,
                            endpoint=operation,
                            status="success"
                        ).inc()
                        metrics_module.openpages_api_duration_seconds.labels(
                            method=method,
                            endpoint=operation
                        ).observe(duration_ms / 1000.0)
                    
                    return response
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401 and auth_override is None and self.auth_type == "bearer":
                        logger.warning(f"Received 401 for {method} {url}, attempting token refresh and retry")
                        
                        # Add retry event to span
                        if span and is_tracing_enabled():
                            span.add_event("auth_retry", {
                                "reason": "401_unauthorized",
                                "retry_attempt": 1
                            })
                        
                        async with self._auth_lock:
                            # Double-check: only refresh if the token hasn't already been
                            # refreshed by another coroutine that held the lock before us.
                            if self.headers.get('Authorization') == token_before_request:
                                self._clear_bearer_token()
                                # Inline token fetch instead of calling initialize_auth() to
                                # avoid reentrant lock (asyncio.Lock is not reentrant).
                                self.auth_header = await self._create_bearer_auth_header(
                                    self.api_key, self.authentication_url
                                )
                                self.headers['Authorization'] = self.auth_header
                                logger.info("Bearer token refreshed after 401")
                            else:
                                logger.debug("Token already refreshed by another coroutine, skipping re-auth")
                        
                        retry_headers = await self._get_request_headers(auth_override)
                        response = await client.request(method, url, headers=retry_headers, **kwargs)
                        response.raise_for_status()
                        
                        # Add response attributes after retry
                        duration_ms = (time.monotonic() - t_start) * 1000
                        if span and is_tracing_enabled():
                            span.set_attribute("http.status_code", response.status_code)
                            span.set_attribute("http.response.body.size", len(response.content))
                            span.set_attribute("http.retry_count", 1)
                        
                        set_span_ok(span, duration_ms=duration_ms)
                        
                        # Record metrics after retry
                        if metrics_module.is_metrics_enabled():
                            metrics_module.openpages_api_calls_total.labels(
                                method=method,
                                endpoint=operation,
                                status="success"
                            ).inc()
                            metrics_module.openpages_api_duration_seconds.labels(
                                method=method,
                                endpoint=operation
                            ).observe(duration_ms / 1000.0)
                        
                        return response
                    raise
                    
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                if span and is_tracing_enabled():
                    if isinstance(e, httpx.HTTPStatusError):
                        span.set_attribute("http.status_code", e.response.status_code)
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.openpages_api_calls_total.labels(
                        method=method,
                        endpoint=operation,
                        status="error"
                    ).inc()
                    metrics_module.openpages_api_duration_seconds.labels(
                        method=method,
                        endpoint=operation
                    ).observe(duration_ms / 1000.0)
                    error_type = type(e).__name__
                    metrics_module.openpages_api_errors_total.labels(
                        method=method,
                        endpoint=operation,
                        error_type=error_type
                    ).inc()
                
                # Check if this is an SSL certificate error and provide helpful guidance
                if is_ssl_error(e):
                    error_msg = get_ssl_error_message(e, self.base_url)
                    logger.error(error_msg)
                    # Re-raise with the helpful message
                    raise RuntimeError(error_msg) from e
                
                raise

    @log_method_call(log_args=True, level=logging.DEBUG)
    async def query(self, statement: str, offset: int = 0, limit: int = 100, auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a query against OpenPages
        
        Args:
            statement: OpenPages query statement
            offset: Result offset
            limit: Maximum number of results
            
        Returns:
            Query results
        """
        logger.info(f"Executing OpenPages query (limit={limit}, offset={offset})")
        logger.debug(f"Query statement: {statement[:100]}..." if len(statement) > 100 else f"Query statement: {statement}")


        # Check if the base URL has a valid protocol
        if not (self.base_url.startswith('http://') or self.base_url.startswith('https://')):
            logger.error(f"Invalid base URL (missing protocol): {self.base_url}")
            # Return a mock empty result instead of raising an error
            return {"rows": []}

        request_body = {
            "statement": statement,
            "offset": offset,
            "max_rows": 500,
            "limit": limit,
            "case_insensitive": False,
            "honor_primary": False
        }

        api_path = self._get_api_path("/api/v2/query")
        full_url = f"{self.base_url}{api_path}"
        logger.info(f"OpenPages API Query Request: {full_url}")
        logger.info(f"Request Body: {request_body}")

        # Use _request_with_auth_retry for reactive 401 handling and auth_override support
        try:
            response = await self._request_with_auth_retry(
                "POST", full_url, auth_override=auth_override, json=request_body, timeout=30.0
            )
            response_json = response.json()

            # Log the response, but truncate if too large
            if settings.DEBUG:
                logger.info(f"OpenPages API Query Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")

            logger.debug(f"query() completed successfully, returned {len(response_json.get('rows', []))} rows")
            return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error during query: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            error_message = f"OpenPages API error ({e.response.status_code}): {e.response.text}"
            raise RuntimeError(error_message) from e
        except httpx.RequestError as e:
            logger.error(f"Request error during query: {e}")
            raise RuntimeError(f"Network error during query: {str(e)}") from e
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def get_content(self, resource_id: str, auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Get content by resource ID

        Args:
            resource_id: Resource ID of the content
            auth_override: Optional auth header override for per-request auth

        Returns:
            Content data
        """
        logger.info(f"Getting content for resource ID: {resource_id}")


        api_path = self._get_api_path(f"/api/v2/contents/{resource_id}")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages API Get Content Request: {url}")

        try:
            response = await self._request_with_auth_retry(
                "GET", url, auth_override=auth_override, timeout=30.0
            )
            response_json = response.json()

            # Log the response, but truncate if too large
            if settings.DEBUG:
                logger.info(f"OpenPages API Get Content Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")

            return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error getting content: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error getting content: {e}")
            raise
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def create_content(self, content_data: Dict[str, Any], auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Create new content in OpenPages

        Args:
            content_data: Content data to create
            auth_override: Optional auth header override for per-request auth

        Returns:
            Created content data
        """
        logger.info(f"Creating content of type: {content_data.get('type_definition_id', 'unknown')}")


        api_path = self._get_api_path("/api/v2/contents")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages API Create Content Request: {url}")
        logger.debug(f"Request Body: {content_data}")
        try:
            response = await self._request_with_auth_retry(
                "POST", url, auth_override=auth_override, json=content_data, timeout=30.0
            )
            response_json = response.json()

            # Log the response, but truncate if too large
            if settings.DEBUG:
                logger.info(f"OpenPages API Create Content Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")

            return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error creating content: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error creating content: {e}")
            raise
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def update_content(self, resource_id: str, content_data: Dict[str, Any], auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Update existing content in OpenPages

        Args:
            resource_id: Resource ID of the content to update
            content_data: Updated content data
            auth_override: Optional auth header override for per-request auth

        Returns:
            Updated content data
        """
        logger.info(f"Updating content: {resource_id} (type: {content_data.get('type_definition_id', 'unknown')})")


        api_path = self._get_api_path(f"/api/v2/contents/{resource_id}")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages API Update Content Request: {url}")
        logger.debug(f"Request Body: {content_data}")

        try:
            response = await self._request_with_auth_retry(
                "PUT", url, auth_override=auth_override, json=content_data, timeout=30.0
            )
            response_json = response.json()

            # Log the response, but truncate if too large
            if settings.DEBUG:
                logger.info(f"OpenPages API Update Content Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")

            return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error updating content: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error updating content: {e}")
            raise
    
    async def get_current_user(self, auth_override: Optional[str] = None) -> Optional[str]:
        """
        Get the current authenticated user's information

        Args:
            auth_override: Optional auth header override for per-request auth

        Returns:
            Username of the current user
        """
        logger.info("Getting current user from OpenPages")
        try:
            # Double-check that the base URL has the correct protocol
            if not (self.base_url.startswith('http://') or self.base_url.startswith('https://')):
                logger.error(f"Base URL missing protocol: {self.base_url}")
                return "admin"  # Return a default user if URL is invalid

            # Query for current user
            query = "SELECT [Name] FROM [User] WHERE [Name] IS NOT NULL LIMIT 1"
            logger.info(f"Current user query: {query}")

            result = await self.query(query, auth_override=auth_override)
            
            if result.get('rows'):
                username = result['rows'][0]['fields'][0]['value']
                logger.info(f"Current user: {username}")
                return username
            else:
                logger.warning("No user found in query result")
                return "admin"  # Return a default user if no user found
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            return "admin"  # Return a default user on error
    
    async def get_type_definition(self, type_name: str, auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Get type definition information from OpenPages

        Args:
            type_name: Name of the type to retrieve (e.g., 'SOXIssue')
            auth_override: Optional auth header override for per-request auth

        Returns:
            Type definition data including field definitions
        """
        
        api_path = self._get_api_path(f"/api/v2/types/{type_name}")
        url = f"{self.base_url}{api_path}"
        logger.info(f"OpenPages API Get Type Definition Request: {url}")

        try:
            response = await self._request_with_auth_retry(
                "GET", url, auth_override=auth_override, timeout=30.0
            )
            response_json = response.json()

            # Log the response, but truncate if too large
            if settings.DEBUG:
                logger.info(f"OpenPages API Get Type Definition Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")

            return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error getting type definition: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error getting type definition: {e}")
            raise
    
    async def get_type_associations(self, type_name: str, auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Get type association information from OpenPages

        Args:
            type_name: Name of the type to retrieve associations for (e.g., 'SOXIssue')
            auth_override: Optional auth header override for per-request auth

        Returns:
            Type association data including parent and child relationships
        """
        
        api_path = self._get_api_path(f"/api/v2/types/{type_name}/associations?includeLocalizedLabels=false")
        url = f"{self.base_url}{api_path}"
        logger.info(f"OpenPages API Get Type Associations Request: {url}")

        try:
            response = await self._request_with_auth_retry(
                "GET", url, auth_override=auth_override, timeout=30.0
            )
            response_json = response.json()
            
            # Log the response, but truncate if too large
            if settings.DEBUG:
                logger.info(f"OpenPages API Get Type Associations Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")
            
            return response_json
        except httpx.HTTPStatusError as e:
            # This exception has response attribute
            logger.error(f"HTTP status error getting type associations: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            # Return empty dict on error rather than raising
            return {}
        except httpx.RequestError as e:
            # Network-related errors
            logger.error(f"Request error getting type associations: {e}")
            # Return empty dict on error rather than raising
            return {}
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def get_username_by_email(self, email: str, auth_override: Optional[str] = None) -> Optional[str]:
        """
        Get username by email using SCIM Users API

        Args:
            email: Email address of the user
            auth_override: Optional auth header override for per-request auth

        Returns:
            Username if found, None otherwise
        """
        logger.info(f"Getting username for email: {email}")


        # URL encode the filter parameter
        import urllib.parse
        filter_param = f'emails eq "{email}"'
        encoded_filter = urllib.parse.quote(filter_param)

        api_path = self._get_api_path(f"/api/v2/scim/Users?filter={encoded_filter}")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages SCIM Users API Request: {url}")

        try:
            response = await self._request_with_auth_retry(
                "GET", url, auth_override=auth_override, timeout=30.0
            )
            response_json = response.json()

            # Log the response
            if settings.DEBUG:
                logger.info(f"OpenPages SCIM Users API Response Status: {response.status_code}")
                response_str = str(response_json)
                if len(response_str) > 1000:
                    logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                else:
                    logger.info(f"Response Body: {response_json}")

            # Extract username from response
            resources = response_json.get('Resources', [])
            if resources and len(resources) > 0:
                user = resources[0]
                username = user.get('userName')
                logger.info(f"Resolved email {email} to username: {username}")
                return username
            else:
                logger.warning(f"No user found with email: {email}")
                return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error getting username by email: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error getting username by email: {e}")
            return None

    @log_method_call(log_args=True, level=logging.DEBUG)
    async def delete_content(self, resource_id: str, auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete content from OpenPages

        Args:
            resource_id: Resource ID of the content to delete
            auth_override: Optional auth header override for per-request auth

        Returns:
            Response data from the delete operation
        """
        logger.info(f"Deleting content: {resource_id}")
        
        api_path = self._get_api_path(f"/api/v2/contents/{resource_id}")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages API Delete Content Request: {url}")

        try:
            response = await self._request_with_auth_retry(
                "DELETE", url, auth_override=auth_override, timeout=30.0
            )

            # For DELETE operations, the response might be empty
            if response.text:
                response_json = response.json()
            else:
                response_json = {"status": "success", "message": "Content deleted successfully"}

            # Log the response
            if self.settings.DEBUG:
                logger.info(f"OpenPages API Delete Content Response Status: {response.status_code}")
                if response.text:
                    response_str = str(response_json)
                    if len(response_str) > 1000:
                        logger.info(f"Response Body (truncated): {response_str[:1000]}...")
                    else:
                        logger.info(f"Response Body: {response_json}")
                else:
                    logger.info("Response Body: Empty (successful deletion)")

            return response_json
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error deleting content: {e}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error deleting content: {e}")
            raise
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def add_associations(self, resource_id: str, associations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Add associations to an object in OpenPages using the dedicated associations API
        
        Uses: POST /v2/contents/{id}/associations
        
        Args:
            resource_id: Resource ID of the source object
            associations: List of association dictionaries, each containing:
                - relationship_type: Type of relationship (e.g., "Parent", "Child", "Sibling", "Peer")
                - target_id: Resource ID of the target object
                
        Returns:
            Response data from the association operation
        """
        logger.info(f"Adding {len(associations)} association(s) to resource: {resource_id}")
        
        
        api_path = self._get_api_path(f"/api/v2/contents/{resource_id}/associations")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages API Add Associations Request: {url}")
        
        # Validate associations
        valid_associations = []
        for assoc in associations:
            relationship_type = assoc.get("relationship_type", "")
            target_id = assoc.get("target_id", "")
            
            if not target_id:
                logger.warning(f"Skipping association without target_id: {assoc}")
                continue
            
            if not relationship_type:
                logger.warning(f"Skipping association without relationship_type: {assoc}")
                continue
            
            valid_associations.append({
                "relationship_type": relationship_type,
                "target_id": target_id
            })
        
        if not valid_associations:
            logger.warning("No valid associations to add")
            return {"status": "no_associations", "message": "No valid associations provided"}
        
        logger.info(f"Adding {len(valid_associations)} association(s) to object {resource_id}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
        
        # Prepare all associations in a single payload
        # API accepts multiple associations in one request
        associations_array = []
        for assoc in valid_associations:
            relationship_type = assoc["relationship_type"]
            target_id = assoc["target_id"]
            associations_array.append({
                "id": target_id,
                "type": relationship_type.lower()  # Convert to lowercase (parent, child, etc.)
            })
            logger.debug(f"Preparing {relationship_type} association to {target_id}")
        
        # Create payload with all associations
        association_payload = {
            "associations": associations_array
        }
        
        if self.settings.DEBUG:
            logger.debug(f"Association payload: {association_payload}")
        
        # Send all associations in a single API call using retry mechanism
        try:
            response = await self._request_with_auth_retry(
                "POST", url, auth_override=None, json=association_payload, timeout=30.0
            )
            
            # The response might be empty for successful association creation
            if response.text:
                response_json = response.json()
            else:
                response_json = {
                    "status": "success",
                    "message": f"Added {len(associations_array)} association(s)",
                    "associations": associations_array
                }
            
            logger.info(f"Successfully added {len(associations_array)} association(s) to {resource_id}")
            
            return {
                "status": "success",
                "total": len(associations_array),
                "successful": len(associations_array),
                "failed": 0,
                "result": response_json
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to add associations: {e.response.text}"
            logger.error(error_msg)
            return {
                "status": "error",
                "total": len(associations_array),
                "successful": 0,
                "failed": len(associations_array),
                "error": e.response.text
            }
        except httpx.RequestError as e:
            error_msg = f"Request error adding associations: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "total": len(associations_array),
                "successful": 0,
                "failed": len(associations_array),
                "error": str(e)
            }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def remove_associations(self, resource_id: str, associations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Remove associations from an object in OpenPages using the dedicated associations API
        
        Uses: DELETE /v2/contents/{id}/associations?parents=...&children=...
        
        The API uses query parameters to specify which associations to remove:
        - parents: Comma-separated list of parent object IDs
        - children: Comma-separated list of child object IDs
        - siblings: Comma-separated list of sibling object IDs
        - peers: Comma-separated list of peer object IDs
        
        Args:
            resource_id: Resource ID of the source object
            associations: List of association dictionaries, each containing:
                - relationship_type: Type of relationship (e.g., "Parent", "Child", "Sibling", "Peer")
                - target_id: Resource ID of the target object to remove
                
        Returns:
            Response data from the association operation
        """
        logger.info(f"Removing {len(associations)} association(s) from resource: {resource_id}")
        
        
        # Group associations by relationship type
        grouped_associations = {}
        for assoc in associations:
            target_id = assoc.get("target_id", "")
            relationship_type = assoc.get("relationship_type", "").lower()  # Convert to lowercase
            
            if not target_id:
                logger.warning(f"Skipping association without target_id: {assoc}")
                continue
            
            if relationship_type not in grouped_associations:
                grouped_associations[relationship_type] = []
            grouped_associations[relationship_type].append(target_id)
        
        if not grouped_associations:
            logger.warning("No valid associations to remove")
            return {"status": "no_associations", "message": "No valid associations provided"}
        
        # Build query parameters
        # API expects: parents=id1,id2&children=id3,id4
        query_params = {}
        for rel_type, ids in grouped_associations.items():
            # Convert relationship type to plural form for query param
            # Parent -> parents, Child -> children, Sibling -> siblings, Peer -> peers
            if rel_type == "parent":
                param_name = "parents"
            elif rel_type == "child":
                param_name = "children"
            elif rel_type == "sibling":
                param_name = "siblings"
            elif rel_type == "peer":
                param_name = "peers"
            else:
                param_name = f"{rel_type}s"  # Generic pluralization
            
            query_params[param_name] = ",".join(ids)
            logger.debug(f"Removing {len(ids)} {rel_type} association(s): {ids}")
        
        api_path = self._get_api_path(f"/api/v2/contents/{resource_id}/associations")
        url = f"{self.base_url}{api_path}"
        logger.debug(f"OpenPages API Remove Associations Request: {url}")
        if self.settings.DEBUG:
            logger.debug(f"Query parameters: {query_params}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
        
        # Use retry mechanism for DELETE request
        try:
            response = await self._request_with_auth_retry(
                "DELETE", url, auth_override=None, params=query_params, timeout=30.0
            )
            
            # The response might be empty for successful removal
            if response.text:
                response_json = response.json()
            else:
                response_json = {
                    "status": "success",
                    "message": f"Removed {len(associations)} association(s)",
                    "removed": grouped_associations
                }
            
            logger.info(f"Successfully removed {len(associations)} association(s) from {resource_id}")
            
            return {
                "status": "success",
                "total": len(associations),
                "successful": len(associations),
                "failed": 0,
                "result": response_json
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to remove associations: {e.response.text}"
            logger.error(error_msg)
            return {
                "status": "error",
                "total": len(associations),
                "successful": 0,
                "failed": len(associations),
                "error": e.response.text
            }
        except httpx.RequestError as e:
            error_msg = f"Request error removing associations: {e}"
            logger.error(error_msg)
            return {
                "status": "error",
                "total": len(associations),
                "successful": 0,
                "failed": len(associations),
                "error": str(e)
            }

# Made with Bob
