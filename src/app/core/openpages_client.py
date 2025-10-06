"""
OpenPages API Client
Provides functionality to interact with IBM OpenPages REST API
"""

import logging
import base64
from typing import Any, Dict, List, Optional
import httpx
from src.app.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class OpenPagesClient:
    """Client for interacting with IBM OpenPages API"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize the OpenPages client
        
        Args:
            base_url: Base URL of the OpenPages API
            username: OpenPages username
            password: OpenPages password
        """
        self.base_url = base_url.rstrip('/')
        self.auth_header = self._create_auth_header(username, password)
        self.headers = {
            'Authorization': self.auth_header,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _create_auth_header(self, username: str, password: str) -> str:
        """
        Create Basic Auth header
        
        Args:
            username: OpenPages username
            password: OpenPages password
            
        Returns:
            Basic auth header string
        """
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
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
        async with httpx.AsyncClient(verify=False) as client:  # Disable SSL verification for self-signed certificates
            try:
                response = await client.post(
                    f"{self.base_url}/opgrc/api/v2/query",
                    headers=self.headers,
                    json={
                        "statement": statement,
                        "offset": offset,
                        "max_rows": 500,
                        "limit": limit,
                        "case_insensitive": False,
                        "honor_primary": False
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error during query: {e}")
                raise
    
    async def get_content(self, resource_id: str) -> Dict[str, Any]:
        """
        Get content by resource ID
        
        Args:
            resource_id: Resource ID of the content
            
        Returns:
            Content data
        """
        async with httpx.AsyncClient(verify=False) as client:  # Disable SSL verification for self-signed certificates
            try:
                response = await client.get(
                    f"{self.base_url}/opgrc/api/v2/contents/{resource_id}",
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error getting content: {e}")
                raise
    
    async def create_content(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new content in OpenPages
        
        Args:
            content_data: Content data to create
            
        Returns:
            Created content data
        """
        async with httpx.AsyncClient(verify=False) as client:  # Disable SSL verification for self-signed certificates
            try:
                response = await client.post(
                    f"{self.base_url}/opgrc/api/v2/contents",
                    headers=self.headers,
                    json=content_data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error creating content: {e}")
                raise
    
    async def update_content(self, resource_id: str, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing content in OpenPages
        
        Args:
            resource_id: Resource ID of the content to update
            content_data: Updated content data
            
        Returns:
            Updated content data
        """
        async with httpx.AsyncClient(verify=False) as client:  # Disable SSL verification for self-signed certificates
            try:
                response = await client.put(
                    f"{self.base_url}/opgrc/api/v2/contents/{resource_id}",
                    headers=self.headers,
                    json=content_data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error updating content: {e}")
                raise
    
    async def get_current_user(self) -> Optional[str]:
        """
        Get the current authenticated user's information
        
        Returns:
            Username of the current user
        """
        try:
            # Query for current user
            result = await self.query("SELECT [Name] FROM [User] WHERE [Name] IS NOT NULL LIMIT 1")
            if result.get('rows'):
                return result['rows'][0]['fields'][0]['value']
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
        return None

# Made with Bob
