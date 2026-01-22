"""
OpenPages API Client
Provides functionality to interact with IBM OpenPages REST API
"""

import logging
import base64
from typing import Any, Dict, List, Optional
import httpx  # type: ignore
from src.app.config.settings import Settings, settings
from src.app.observability.logger import get_logger, log_method_call

# Type annotation for better error handling
HTTPXError = httpx.HTTPError

# Configure logging
logger = get_logger(__name__)

class OpenPagesClient:
    """Client for interacting with IBM OpenPages API"""
    
    def __init__(self, base_url: str, auth_type: str = "basic", username: Optional[str] = None,
                 password: Optional[str] = None, api_key: Optional[str] = None, authentication_url: Optional[str] = None,
                 custom_settings: Optional[Settings] = None):
        """
        Initialize the OpenPages client
        
        Args:
            base_url: Base URL of the OpenPages API
            auth_type: Authentication type, either "basic" or "bearer"
            username: OpenPages username (required if auth_type is "basic")
            password: OpenPages password (required if auth_type is "basic")
            api_key: API key for bearer authentication (required if auth_type is "bearer")
            authentication_url: Authentication URL for bearer authentication (required if auth_type is "bearer")
            custom_settings: Optional custom settings object to use instead of global settings
        """
        # Use provided settings or fall back to global settings
        self.settings = custom_settings if custom_settings else settings
        
        # Validate authentication parameters
        if auth_type.lower() == "basic":
            if not username or not password:
                raise ValueError("Username and password are required for basic authentication")
        elif auth_type.lower() == "bearer":
            if not api_key:
                raise ValueError("API key is required for bearer authentication")
            if not authentication_url:
                raise ValueError("Authentication Url is required for bearer authentication")
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
        
        # For basic auth, we can set the auth header immediately
        if self.auth_type == "basic":
            self.auth_header = self._create_basic_auth_header(username, password)
            self.headers['Authorization'] = self.auth_header
        # For bearer auth, we'll set it later in an async method
    
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
        Create Bearer Auth header by fetching a token from IBM Cloud IAM
        
        Args:
            api_key: API key for bearer authentication
            authentication_url: URL to use for authentication

        Returns:
            Bearer auth header string
        """
        if api_key is None:
            raise ValueError("API key cannot be None for bearer authentication")

        if authentication_url is None:
            raise ValueError("Authentication Url cannot be None for bearer authentication")

        token = await self.fetch_token(api_key, authentication_url)
        if token is None:
            raise ValueError("Failed to obtain token from IAM service")
        return f"Bearer {token}"
    
    def _detect_auth_type(self, authentication_url: str) -> str:
        """
        Detect authentication type based on the authentication URL.
        
        Args:
            authentication_url (str): The authentication URL
            
        Returns:
            str: Either 'ibm_cloud' or 'mcsp'
        """
        # Check if URL contains IBM Cloud IAM patterns
        if 'iam.cloud.ibm.com' in authentication_url or 'iam.test.cloud.ibm.com' in authentication_url:
            logger.info("Detected IBM Cloud OAuth2 authentication")
            return 'ibm_cloud'
        # Check if URL contains MCSP patterns
        elif 'account-iam.platform' in authentication_url or 'saas.ibm.com' in authentication_url:
            logger.info("Detected MCSP OAuth2 authentication")
            return 'mcsp'
        else:
            # Default to IBM Cloud if pattern is not recognized
            logger.warning(f"Could not detect auth type from URL: {authentication_url}. Defaulting to IBM Cloud.")
            return 'ibm_cloud'
    
    async def fetch_token(self, api_key: str, authentication_url: str) -> Optional[str]:
        """
        Fetch authentication token from IBM Cloud IAM or MCSP service.
        Automatically detects the authentication type based on the URL.
        
        Args:
            api_key (str): The API key to use for authentication
            authentication_url (str): The URL to use for authentication

        Returns:
            Optional[str]: The access token if successful, None otherwise
        """
        # Detect authentication type
        auth_type = self._detect_auth_type(authentication_url)
        
        if auth_type == 'ibm_cloud':
            # IBM Cloud OAuth2
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
                    logger.info(f"Fetching IBM Cloud token from {authentication_url}")
                    response = await client.post(authentication_url, headers=headers, data=data, timeout=30.0)
                    response.raise_for_status()
                    
                    token_data = response.json()
                    
                    if 'access_token' in token_data:
                        logger.info("Successfully obtained IBM Cloud access token")
                        return token_data['access_token']
                    else:
                        logger.error("Error: 'access_token' not found in IBM Cloud response")
                        logger.error(f"Response: {token_data}")
                        return None
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"Error fetching IBM Cloud token: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Request error fetching IBM Cloud token: {e}")
                return None
                
        else:  # mcsp
            # MCSP OAuth2
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # MCSP expects JSON body with apikey
            json_data = {
                'apikey': api_key
            }
            
            try:
                async with httpx.AsyncClient(verify=True) as client:
                    logger.info(f"Fetching MCSP token from {authentication_url}")
                    response = await client.post(authentication_url, headers=headers, json=json_data, timeout=30.0)
                    response.raise_for_status()
                    
                    token_data = response.json()
                    
                    # MCSP returns 'token' instead of 'access_token'
                    if 'token' in token_data:
                        logger.info("Successfully obtained MCSP token")
                        return token_data['token']
                    else:
                        logger.error("Error: 'token' not found in MCSP response")
                        logger.error(f"Response: {token_data}")
                        return None
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"Error fetching MCSP token: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Request error fetching MCSP token: {e}")
                return None
    
    @log_method_call(level=logging.DEBUG)
    async def initialize_auth(self):
        """
        Initialize authentication asynchronously.
        This must be called before making any API requests when using bearer authentication.
        """
        if self.auth_type == "bearer" and 'Authorization' not in self.headers:
            logger.info("Initializing bearer authentication")
            self.auth_header = await self._create_bearer_auth_header(self.api_key, self.authentication_url)
            self.headers['Authorization'] = self.auth_header
            logger.info("Bearer authentication initialized successfully")
        else:
            logger.debug(f"Auth already initialized or using basic auth (type: {self.auth_type})")
            
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def query(self, statement: str, offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Execute a query against OpenPages
        
        Args:
            statement: SQL-like query statement
            offset: Result offset
            limit: Maximum number of results
            
        Returns:
            Query results
        """
        logger.info(f"Executing OpenPages query (limit={limit}, offset={offset})")
        logger.debug(f"Query statement: {statement[:100]}..." if len(statement) > 100 else f"Query statement: {statement}")
        
        # Ensure authentication is initialized
        await self.initialize_auth()
        
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
        
        logger.info(f"OpenPages API Query Request: {self.base_url}/opgrc/api/v2/query")
        logger.info(f"Request Body: {request_body}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/opgrc/api/v2/query",
                    headers=self.headers,
                    json=request_body,
                    timeout=30.0
                )
                response.raise_for_status()
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
                # This exception has response attribute
                logger.error(f"HTTP status error during query: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                # Re-raise the error with a more descriptive message
                error_message = f"OpenPages API error ({e.response.status_code}): {e.response.text}"
                raise RuntimeError(error_message) from e
            except httpx.RequestError as e:
                # Network-related errors
                logger.error(f"Request error during query: {e}")
                # Re-raise the error with a more descriptive message
                raise RuntimeError(f"Network error during query: {str(e)}") from e
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def get_content(self, resource_id: str) -> Dict[str, Any]:
        """
        Get content by resource ID
        
        Args:
            resource_id: Resource ID of the content
            
        Returns:
            Content data
        """
        logger.info(f"Getting content for resource ID: {resource_id}")
        
        # Ensure authentication is initialized
        await self.initialize_auth()
        
        url = f"{self.base_url}/opgrc/api/v2/contents/{resource_id}"
        logger.debug(f"OpenPages API Get Content Request: {url}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
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
                # This exception has response attribute
                logger.error(f"HTTP status error getting content: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except httpx.RequestError as e:
                # Network-related errors
                logger.error(f"Request error getting content: {e}")
                raise
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def create_content(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new content in OpenPages
        
        Args:
            content_data: Content data to create
            
        Returns:
            Created content data
        """
        logger.info(f"Creating content of type: {content_data.get('type_definition_id', 'unknown')}")
        
        # Ensure authentication is initialized
        await self.initialize_auth()
        
        url = f"{self.base_url}/opgrc/api/v2/contents"
        logger.debug(f"OpenPages API Create Content Request: {url}")
        logger.debug(f"Request Body: {content_data}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=content_data,
                    timeout=30.0
                )
                response.raise_for_status()
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
                # This exception has response attribute
                logger.error(f"HTTP status error creating content: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except httpx.RequestError as e:
                # Network-related errors
                logger.error(f"Request error creating content: {e}")
                raise
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def update_content(self, resource_id: str, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing content in OpenPages
        
        Args:
            resource_id: Resource ID of the content to update
            content_data: Updated content data
            
        Returns:
            Updated content data
        """
        logger.info(f"Updating content: {resource_id} (type: {content_data.get('type_definition_id', 'unknown')})")
        
        # Ensure authentication is initialized
        await self.initialize_auth()
        
        url = f"{self.base_url}/opgrc/api/v2/contents/{resource_id}"
        logger.debug(f"OpenPages API Update Content Request: {url}")
        logger.debug(f"Request Body: {content_data}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.put(
                    url,
                    headers=self.headers,
                    json=content_data,
                    timeout=30.0
                )
                response.raise_for_status()
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
                # This exception has response attribute
                logger.error(f"HTTP status error updating content: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except httpx.RequestError as e:
                # Network-related errors
                logger.error(f"Request error updating content: {e}")
                raise
    
    async def get_current_user(self) -> Optional[str]:
        """
        Get the current authenticated user's information
        
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
            
            result = await self.query(query)
            
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
    
    async def get_type_definition(self, type_name: str) -> Dict[str, Any]:
        """
        Get type definition information from OpenPages
        
        Args:
            type_name: Name of the type to retrieve (e.g., 'SOXIssue')
            
        Returns:
            Type definition data including field definitions
        """
        # Ensure authentication is initialized
        await self.initialize_auth()
        
        url = f"{self.base_url}/opgrc/api/v2/types/{type_name}"
        logger.info(f"OpenPages API Get Type Definition Request: {url}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
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
                # This exception has response attribute
                logger.error(f"HTTP status error getting type definition: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except httpx.RequestError as e:
                # Network-related errors
                logger.error(f"Request error getting type definition: {e}")
                raise
    
    async def get_type_associations(self, type_name: str) -> Dict[str, Any]:
        """
        Get type association information from OpenPages
        
        Args:
            type_name: Name of the type to retrieve associations for (e.g., 'SOXIssue')
            
        Returns:
            Type association data including parent and child relationships
        """
        # Ensure authentication is initialized
        await self.initialize_auth()
        
        url = f"{self.base_url}/opgrc/api/v2/types/{type_name}/associations?includeLocalizedLabels=false"
        logger.info(f"OpenPages API Get Type Associations Request: {url}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
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
    async def delete_content(self, resource_id: str) -> Dict[str, Any]:
        """
        Delete content from OpenPages
        
        Args:
            resource_id: Resource ID of the content to delete
            
        Returns:
            Response data from the delete operation
        """
        logger.info(f"Deleting content: {resource_id}")
        
        # Ensure authentication is initialized
        await self.initialize_auth()
        
        url = f"{self.base_url}/opgrc/api/v2/contents/{resource_id}"
        logger.debug(f"OpenPages API Delete Content Request: {url}")
        
        # Use SSL verification setting from config
        if not self.settings.SSL_VERIFY:
            logger.warning("SSL verification is disabled. This is not recommended for production environments.")
            
        async with httpx.AsyncClient(verify=self.settings.SSL_VERIFY) as client:
            try:
                response = await client.delete(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                
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
                # This exception has response attribute
                logger.error(f"HTTP status error deleting content: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                raise
            except httpx.RequestError as e:
                # Network-related errors
                logger.error(f"Request error deleting content: {e}")
                raise

# Made with Bob
