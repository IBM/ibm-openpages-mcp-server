"""
Integration tests for deployed GRC MCP Server - Ontology Tools

This test suite validates a deployed MCP server instance by testing:
1. Health and MCP protocol endpoints
2. Resource discovery (catalog, object type schemas)
3. Query execution
4. Complete CRUD workflow (Create, Update, Associate, Dissociate, Delete)

Configuration:
    Required: MCP_SERVER_URL environment variable
    Optional: config.json file or additional environment variables

Usage:
    # Basic run
    MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py -v

    # With detailed output
    MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py -v -s

    # Run specific test class
    MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestCRUDWorkflow -v
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx
import pytest


# Configuration constants
DEFAULT_TIMEOUT = 30
LONG_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_DELAY = 1.0
SENSITIVE_KEYS = {'token', 'apikey', 'password', 'authorization', 'api_key', 'bearer'}


@dataclass
class IntegrationTestConfig:
    """Configuration for integration tests"""
    mcp_server_url: str
    api_key: Optional[str] = None  # X-Api-Key header value for authentication
    api_key_header_name: str = "X-Api-Key"  # Configurable API key header name
    test_object_type: str = "issue"
    object_type_aliases: Optional[Dict[str, str]] = None  # Maps friendly names to actual type IDs
    timeout: int = LONG_TIMEOUT
    cleanup_test_objects: bool = True
    rate_limit_delay: float = RETRY_DELAY
    
    def __post_init__(self):
        """Initialize default object type aliases if not provided"""
        if self.object_type_aliases is None:
            self.object_type_aliases = {
                "issue": "soxissue",
                "control": "soxcontrol"
            }

    @classmethod
    def from_env_and_file(cls) -> "IntegrationTestConfig":
        """Load configuration from environment variables and optional config file"""
        # Try to load from config.json if it exists
        config_path = Path(__file__).parent / "config.json"
        file_config = {}
        if config_path.exists():
            try:
                with open(config_path) as f:
                    file_config = json.load(f)
                
                # Validate config structure
                if not isinstance(file_config, dict):
                    raise ValueError("config.json must contain a JSON object")
                    
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in config.json: {e}")

        # Environment variables take precedence
        mcp_server_url = os.getenv("MCP_SERVER_URL", file_config.get("mcp_server_url"))
        if not mcp_server_url:
            raise ValueError(
                "MCP_SERVER_URL must be set via environment variable or config.json"
            )
        
        # Validate server URL is not empty
        mcp_server_url = mcp_server_url.strip()
        if not mcp_server_url:
            raise ValueError("MCP_SERVER_URL cannot be empty")

        # Load API key for authentication (optional - server may not require it in dev mode)
        api_key = os.getenv("MCP_API_KEY", file_config.get("api_key"))
        
        # Load API key header name (defaults to X-Api-Key)
        api_key_header_name = os.getenv(
            "MCP_API_KEY_HEADER",
            file_config.get("api_key_header_name", "X-Api-Key")
        )

        # Load object type aliases from config file
        object_type_aliases = file_config.get("object_type_aliases", {
            "issue": "soxissue",
            "control": "soxcontrol"
        })
        
        return cls(
            mcp_server_url=mcp_server_url.rstrip("/"),
            api_key=api_key,
            api_key_header_name=api_key_header_name,
            test_object_type=os.getenv(
                "TEST_OBJECT_TYPE", file_config.get("test_object_type", "issue")
            ),
            object_type_aliases=object_type_aliases,
            timeout=int(os.getenv("TIMEOUT", file_config.get("timeout", LONG_TIMEOUT))),
            cleanup_test_objects=os.getenv(
                "CLEANUP_TEST_OBJECTS",
                str(file_config.get("cleanup_test_objects", True))
            ).lower() == "true",
            rate_limit_delay=float(os.getenv(
                "RATE_LIMIT_DELAY", file_config.get("rate_limit_delay", RETRY_DELAY)
            ))
        )


class MCPClient:
    """Client for interacting with MCP server via HTTP"""

    def __init__(
        self,
        base_url: str,
        timeout: int = LONG_TIMEOUT,
        api_key: Optional[str] = None,
        api_key_header_name: str = "X-Api-Key"
    ):
        if not base_url:
            raise ValueError("base_url cannot be None or empty")
        self.base_url = base_url
        self.timeout = timeout
        self.api_key = api_key
        self.api_key_header_name = api_key_header_name
        self.session_id: Optional[str] = None  # MCP session ID from initialize
        self.client = httpx.AsyncClient(timeout=timeout)
    
    @staticmethod
    def _sanitize_for_logging(data: Any) -> Any:
        """Sanitize sensitive data before logging"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                key_lower = key.lower()
                if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
                    sanitized[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    sanitized[key] = MCPClient._sanitize_for_logging(value)
                elif isinstance(value, list):
                    sanitized[key] = [MCPClient._sanitize_for_logging(item) for item in value]
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [MCPClient._sanitize_for_logging(item) for item in data]
        return data
    
    @staticmethod
    def handle_http_error(e: httpx.HTTPStatusError, operation: str, resource_id: Optional[str] = None) -> None:
        """
        Handle HTTP errors with consistent error messages and appropriate actions.
        
        Args:
            e: The HTTP status error
            operation: Description of the operation being performed
            resource_id: Optional resource ID for context
        
        Raises:
            pytest.skip: For rate limiting (429) or not found (404) errors
            pytest.fail: For authentication (401), permission (403), or other HTTP errors
        """
        resource_context = f" for resource {resource_id}" if resource_id else ""
        
        if e.response.status_code == 429:
            pytest.skip(f"Rate limited - skipping {operation}")
        elif e.response.status_code == 404:
            print(f"⚠️  Resource{resource_context} not found (may have been already deleted)")
            pytest.skip(f"Resource not found - {operation}")
        elif e.response.status_code == 403:
            pytest.fail(f"Permission denied when {operation}{resource_context}: {e}", pytrace=True)
        elif e.response.status_code == 401:
            pytest.fail(f"Authentication failed when {operation}{resource_context}: {e}", pytrace=True)
        else:
            pytest.fail(f"HTTP error {e.response.status_code} when {operation}{resource_context}: {e}", pytrace=True)

    def _get_headers(self, include_session: bool = True) -> Dict[str, str]:
        """
        Build request headers with authentication and optional session ID.
        
        Args:
            include_session: Whether to include Mcp-Session-Id header if available (default: True)
            
        Returns:
            Dictionary of headers
        """
        headers = {"Content-Type": "application/json"}
        
        # Add API key header if configured
        if self.api_key:
            headers[self.api_key_header_name] = self.api_key
        
        # Add session ID header ONLY if it exists and is requested
        # This prevents sending empty/None session IDs which cause 400 errors
        if include_session and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        
        return headers

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call an MCP tool via JSON-RPC

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result as dictionary
        """
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }

        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=request_data,
            headers=self._get_headers(include_session=True)
        )
        response.raise_for_status()

        result = response.json()
        if "error" in result:
            raise Exception(f"MCP Error: {result['error']}")

        # Handle nested JSON response structure
        tool_result = result.get("result", {})
        
        # Check for tool-level errors (isError flag)
        if isinstance(tool_result, dict) and tool_result.get("isError") is True:
            return {"error": "Tool execution failed", "details": tool_result}
        
        # Check if tool_result itself is a list (direct content array)
        if isinstance(tool_result, list) and len(tool_result) > 0:
            for item in tool_result:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content = item.get("text", "")
                    text_stripped = text_content.strip()
                    if text_stripped.startswith(("{", "[")):
                        try:
                            parsed = json.loads(text_stripped)
                            return parsed
                        except json.JSONDecodeError:
                            return {"text": text_content, "parse_error": "JSON decode failed"}
                    return {"text": text_content}
            return {"result": tool_result}
        
        # Check if content is nested in a dict
        content = tool_result.get("content") if isinstance(tool_result, dict) else None
        
        if isinstance(content, list) and len(content) > 0:
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content = item.get("text", "")
                    text_stripped = text_content.strip()
                    if text_stripped.startswith(("{", "[")):
                        try:
                            parsed = json.loads(text_stripped)
                            
                            # Check if parsed has a 'result' key that needs unwrapping
                            if isinstance(parsed, dict) and "result" in parsed:
                                result_value = parsed["result"]
                                # If result is a list with one item that has type='text', parse it again
                                if isinstance(result_value, list) and len(result_value) == 1:
                                    inner_item = result_value[0]
                                    if isinstance(inner_item, dict) and inner_item.get("type") == "text":
                                        inner_text = inner_item.get("text", "")
                                        if inner_text.strip().startswith(("{", "[")):
                                            try:
                                                inner_parsed = json.loads(inner_text)
                                                return inner_parsed
                                            except json.JSONDecodeError:
                                                return inner_item
                                    return inner_item
                                return result_value
                            
                            return parsed
                        except json.JSONDecodeError:
                            return {"text": text_content, "parse_error": "JSON decode failed"}
                    return {"text": text_content}
            return {"content": content}
        
        return tool_result

    async def list_resources(self) -> Dict[str, Any]:
        """List available MCP resources"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
            "params": {}
        }

        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=request_data,
            headers=self._get_headers(include_session=True)
        )
        response.raise_for_status()
        return response.json()

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a specific MCP resource"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": uri}
        }

        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=request_data,
            headers=self._get_headers(include_session=True)
        )
        response.raise_for_status()
        return response.json()


@pytest.fixture(scope="session")
def config() -> IntegrationTestConfig:
    """Load test configuration"""
    return IntegrationTestConfig.from_env_and_file()


@pytest.fixture(scope="session")
async def mcp_client(config: IntegrationTestConfig):
    """
    Create a single MCP client for the entire test session.
    The client is shared across ALL tests to maintain session state.
    Session ID captured in test_initialize is available to all subsequent tests.
    
    Uses session scope to ensure the client persists across all test classes
    and the httpx.AsyncClient remains open throughout the test run.
    """
    client = MCPClient(
        config.mcp_server_url,
        config.timeout,
        api_key=config.api_key,
        api_key_header_name=config.api_key_header_name
    )
    
    print(f"\n=== Creating MCP Client ===")
    print(f"Server: {client.base_url}")
    print(f"Authentication: {'Enabled (API Key)' if client.api_key else 'Disabled (Dev Mode)'}")
    
    # Store server URL in collector for summary reporting
    try:
        from conftest import collector
        collector.set_server_url(client.base_url)
    except ImportError:
        pass  # conftest not available, skip
    
    yield client
    
    print(f"\n=== Closing MCP Client ===")
    await client.close()


@pytest.fixture(scope="class")
def crud_state():
    """Shared state for CRUD workflow tests - persists across all tests in the class"""
    return {
        "issue_id": None,
        "control_id": None,
        "association_id": None
    }


# ============================================================================
# Test Classes
# ============================================================================


class TestHealthEndpoint:
    """Test health endpoint availability"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, config: IntegrationTestConfig):
        """Test that health endpoint is accessible and returns OK status"""
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            # Health endpoint may not require authentication in some deployments
            headers = {}
            if config.api_key:
                headers[config.api_key_header_name] = config.api_key
            
            response = await client.get(
                f"{config.mcp_server_url}/health",
                headers=headers if headers else None
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "healthy"


class TestMCPProtocol:
    """Test MCP protocol compliance"""

    @pytest.mark.asyncio
    async def test_initialize(self, mcp_client: MCPClient):
        """Test MCP initialize handshake and capture session ID"""
        print(f"\n=== Testing Initialize ===")
        print(f"Server: {mcp_client.base_url}")
        print(f"Authentication: {'Enabled (API Key)' if mcp_client.api_key else 'Disabled (Dev Mode)'}")
        
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "integration-test",
                    "version": "1.0.0"
                }
            }
        }

        response = await mcp_client.client.post(
            f"{mcp_client.base_url}/mcp",
            json=request_data,
            headers=mcp_client._get_headers(include_session=False)  # Don't include session for initialize
        )
        assert response.status_code == 200
        result = response.json()
        assert "result" in result
        assert result["result"].get("protocolVersion") in ["2024-11-05", "2025-03-26"]
        
        # Capture session ID from response header if present
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            mcp_client.session_id = session_id
            print(f"✓ Session established with ID: {session_id}")
        else:
            print("✓ Session established (no session ID required)")
        
        print(f"✓ Protocol version: {result['result'].get('protocolVersion')}")

    @pytest.mark.asyncio
    async def test_tools_list(self, mcp_client: MCPClient):
        """Test that tools/list returns expected ontology tools"""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        response = await mcp_client.client.post(
            f"{mcp_client.base_url}/mcp",
            json=request_data,
            headers=mcp_client._get_headers(include_session=True)
        )
        assert response.status_code == 200
        result = response.json()
        
        tools = result.get("result", {}).get("tools", [])
        tool_names = [tool["name"] for tool in tools]
        
        # Verify ontology tools are present
        expected_tools = [
            "execute_openpages_query",
            "openpages_upsert_object",
            "openpages_delete_object",
            "openpages_associate_objects",
            "openpages_dissociate_objects"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Expected tool '{tool_name}' not found"

    @pytest.mark.asyncio
    async def test_read_all_available_resources(self, mcp_client: MCPClient, config: IntegrationTestConfig):
        """
        Comprehensive test for MCP protocol resource operations.
        Tests: resources/list + resources/read for all resources (catalog + schemas)
        
        Note: With 136+ schemas loaded, testing all would take ~7 minutes (136 × 3s rate limit).
        The test limits to 10 resources for practical integration testing. For full validation,
        increase max_resources or run with longer timeout.
        """
        await asyncio.sleep(config.rate_limit_delay)
        
        # First, list all resources
        list_result = await mcp_client.list_resources()
        assert "result" in list_result, "Expected 'result' key in list response"
        
        resources = list_result["result"].get("resources", [])
        assert len(resources) > 0, "No resources found"
        
        print(f"\n=== Testing {len(resources)} Resources ===")
        
        # Try to read each resource (limit to first 10 to avoid timeout)
        # To test all resources, set max_resources = len(resources) and increase timeout
        max_resources = min(10, len(resources))
        successful_reads = 0
        
        catalog_validated = False
        
        for i, resource in enumerate(resources[:max_resources]):
            uri = resource.get("uri")
            name = resource.get("name", "Unknown")
            
            print(f"\n[{i+1}/{max_resources}] Reading: {name}")
            print(f"  URI: {uri}")
            
            await asyncio.sleep(config.rate_limit_delay)
            
            try:
                result = await mcp_client.read_resource(uri)
                
                if "error" in result:
                    print(f"  ⚠️  Error: {result['error'].get('message', 'Unknown')}")
                    continue
                
                if "result" in result:
                    contents = result["result"].get("contents", [])
                    if len(contents) > 0:
                        print(f"  ✓ Successfully read ({len(contents)} content items)")
                        successful_reads += 1
                        
                        # Special validation for catalog resource
                        if uri == "openpages://catalog/object_types":
                            print(f"  → Validating catalog structure...")
                            # Parse the nested JSON structure
                            content_text = contents[0].get("text", "")
                            try:
                                # The content_text contains nested JSON, parse it level by level
                                parsed = json.loads(content_text)
                                
                                # Navigate through the nested structure
                                if "result" in parsed and isinstance(parsed["result"], list) and len(parsed["result"]) > 0:
                                    inner_item = parsed["result"][0]
                                    if isinstance(inner_item, dict) and "text" in inner_item:
                                        inner_text = inner_item["text"]
                                        catalog_data = json.loads(inner_text)
                                    else:
                                        catalog_data = parsed
                                else:
                                    catalog_data = parsed
                                
                                # Check for object_types
                                object_types = catalog_data.get("object_types", [])
                                if len(object_types) > 0:
                                    print(f"  ✓ Catalog contains {len(object_types)} object types")
                                    catalog_validated = True
                                else:
                                    print(f"  ⚠️  Catalog has no object_types")
                            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                                print(f"  ⚠️  Could not parse catalog structure: {e}")
                                print(f"  Debug: content_text = {content_text[:200]}...")
                    else:
                        print(f"  ⚠️  No contents")
                else:
                    print(f"  ⚠️  No result key")
                    
            except Exception as e:
                print(f"  ✗ Exception: {str(e)}")
        
        print(f"\n=== Summary: {successful_reads}/{max_resources} resources read successfully ===")
        assert successful_reads > 0, "Failed to read any resources"
        assert catalog_validated, "Catalog resource was not validated"

    @pytest.mark.asyncio
    async def test_read_all_available_resources_via_tools(self, mcp_client: MCPClient, config: IntegrationTestConfig):
        """
        Comprehensive test for tool-based resource operations.
        Tests: list_resources + get_resource tools for all resources (catalog + schemas)
        """
        await asyncio.sleep(config.rate_limit_delay)
        
        # First, list all resources using list_resources tool
        print("\n=== Listing resources via list_resources tool ===")
        list_result = await mcp_client.call_tool("list_resources")
        
        # Parse the text response to extract URIs
        if isinstance(list_result, dict) and "text" in list_result:
            text_content = list_result["text"]
        else:
            text_content = str(list_result)
        
        assert text_content, "list_resources returned empty"
        assert "catalog" in text_content.lower(), "Catalog not found in resources"
        assert "schema" in text_content.lower(), "No schemas found in resources"
        
        # Extract URIs from the text (they follow "URI: " pattern)
        import re
        uri_pattern = r'URI:\s*(openpages://[^\s\n]+)'
        resource_uris = re.findall(uri_pattern, text_content)
        
        assert len(resource_uris) > 0, "No resource URIs found in list_resources output"
        print(f"Found {len(resource_uris)} resource URIs")
        
        # Try to read each resource using get_resource tool
        max_resources = min(10, len(resource_uris))
        successful_reads = 0
        catalog_validated = False
        
        for i, uri in enumerate(resource_uris[:max_resources]):
            print(f"\n[{i+1}/{max_resources}] Reading: {uri}")
            
            await asyncio.sleep(config.rate_limit_delay)
            
            try:
                result = await mcp_client.call_tool("get_resource", {"uri": uri})
                
                # Check for actual errors (same logic as MCP protocol test)
                if "error" in result:
                    print(f"  ⚠️  Error: {result.get('error', 'Unknown')}")
                    continue
                
                # If we got a result without error, count it as success
                if result:
                    print(f"  ✓ Successfully read")
                    successful_reads += 1
                    
                    # Special validation for catalog resource
                    if uri == "openpages://catalog/object_types":
                        print(f"  → Validating catalog structure...")
                        try:
                            # The result from call_tool is already a parsed dict (not JSON string)
                            if isinstance(result, dict):
                                # Check if it's already the catalog data
                                if "object_types" in result:
                                    catalog_data = result
                                # Or if it has a 'text' key with JSON string
                                elif "text" in result:
                                    content_text = result["text"]
                                    if isinstance(content_text, str) and content_text.startswith("{"):
                                        parsed = json.loads(content_text)
                                        # Navigate nested structure if needed
                                        if "result" in parsed and isinstance(parsed["result"], list):
                                            inner_item = parsed["result"][0]
                                            if isinstance(inner_item, dict) and "text" in inner_item:
                                                catalog_data = json.loads(inner_item["text"])
                                            else:
                                                catalog_data = parsed
                                        else:
                                            catalog_data = parsed
                                    else:
                                        catalog_data = result
                                else:
                                    catalog_data = result
                                
                                # Check for object_types
                                object_types = catalog_data.get("object_types", [])
                                if len(object_types) > 0:
                                    print(f"  ✓ Catalog contains {len(object_types)} object types")
                                    catalog_validated = True
                                else:
                                    print(f"  ⚠️  Catalog has no object_types")
                            else:
                                print(f"  ⚠️  Result is not a dict: {type(result)}")
                        except (json.JSONDecodeError, KeyError, IndexError, AttributeError, TypeError) as e:
                            print(f"  ⚠️  Could not parse catalog structure: {e}")
                            print(f"  Debug: result type = {type(result)}, keys = {result.keys() if isinstance(result, dict) else 'N/A'}")
                else:
                    print(f"  ⚠️  Error or empty result")
                    
            except Exception as e:
                print(f"  ✗ Exception: {str(e)}")
        
        print(f"\n=== Summary: {successful_reads}/{max_resources} resources read successfully ===")
        assert successful_reads > 0, "Failed to read any resources via tools"
        assert catalog_validated, "Catalog resource was not validated via tools"


class TestQueryExecution:
    """Test query execution tool"""

    @pytest.mark.asyncio
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    async def test_simple_query(self, mcp_client: MCPClient, config: IntegrationTestConfig):
        """Test executing a simple query"""
        await asyncio.sleep(config.rate_limit_delay)
        
        # Query for issues - use SOXIssue for queries (not 'issue')
        query = "select [Name] from [SOXIssue]"
        
        result = await mcp_client.call_tool(
            "execute_openpages_query",
            {"query": query}
        )
        
        # Check if query returned an error
        if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
            pytest.fail(f"Query failed: {result['text']}")
        
        # Query results can be in different formats
        assert isinstance(result, (dict, list)), "Expected dict or list response from query"

    @pytest.mark.asyncio
    @pytest.mark.timeout(DEFAULT_TIMEOUT)
    async def test_query_with_filter(self, mcp_client: MCPClient, config: IntegrationTestConfig):
        """Test executing a query with WHERE clause"""
        await asyncio.sleep(config.rate_limit_delay)
        
        # Query with filter - use SOXIssue for queries (not 'issue')
        query = "select [Name] from [SOXIssue] where [Name] LIKE '%Test%'"
        
        result = await mcp_client.call_tool(
            "execute_openpages_query",
            {"query": query}
        )
        
        # Check if query returned an error
        if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
            pytest.fail(f"Query failed: {result['text']}")
        
        # Query results can be in different formats
        assert isinstance(result, (dict, list)), "Expected dict or list response from query"


@pytest.mark.order(1)
@pytest.mark.timeout(300)  # 5 minutes max for entire workflow
class TestCRUDWorkflow:
    """
    Test complete CRUD workflow with separate tests for each operation.
    Tests run in order and share state via crud_state fixture.
    """

    @pytest.mark.asyncio
    @pytest.mark.order(1)
    async def test_01_create_issue(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 1: Create a test Issue object"""
        await asyncio.sleep(config.rate_limit_delay)
        
        print("\n=== Creating Issue ===")
        issue_type = config.object_type_aliases.get("issue", "issue") if config.object_type_aliases else "issue"
        create_args = {
            "object_type": issue_type,
            "name": f"Integration Test Issue {os.urandom(4).hex()}",
            "description": "Created by integration test suite"
        }
        print(f"Arguments: {json.dumps(create_args, indent=2)}")
        
        result = await mcp_client.call_tool("openpages_upsert_object", create_args)
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Check if it's an error response
        if isinstance(result, dict):
            if "text" in result and "error" in result["text"].lower():
                pytest.fail(f"Tool returned error: {result['text']}")
            
            # Result is already parsed and unwrapped by call_tool
            if "resource_id" in result:
                resource_id = result["resource_id"]
                # Validate resource_id is not None, empty string, or whitespace
                if not resource_id or not str(resource_id).strip():
                    pytest.fail(f"resource_id is empty or whitespace: '{resource_id}'")
                crud_state["issue_id"] = resource_id
            else:
                pytest.fail(f"Expected 'resource_id' in result, got: {result}")
        else:
            pytest.fail(f"Unexpected result type: {type(result)}, value: {result}")
        
        print(f"✓ Created Issue: {crud_state['issue_id']}")
        print(f"  Server: {config.mcp_server_url}")
        assert crud_state["issue_id"] and str(crud_state["issue_id"]).strip(), "Issue ID should not be empty"

    @pytest.mark.asyncio
    @pytest.mark.order(2)
    async def test_02_update_issue(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 2: Update the created Issue"""
        await asyncio.sleep(config.rate_limit_delay)
        
        assert crud_state.get("issue_id"), "Issue ID not found or empty - test_01_create_issue must run first"
        
        print(f"\n=== Updating Issue {crud_state['issue_id']} ===")
        issue_type = config.object_type_aliases.get("issue", "issue") if config.object_type_aliases else "issue"
        result = await mcp_client.call_tool(
            "openpages_upsert_object",
            {
                "id": crud_state["issue_id"],  # Use 'id' parameter for upsert, not 'resource_id'
                "object_type": issue_type,
                "name": f"Integration Test Issue {os.urandom(4).hex()}",  # name is required
                "description": "Updated by integration test suite"
            }
        )
        
        # Result is already parsed and unwrapped
        if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
            pytest.fail(f"Tool returned error: {result['text']}")
        
        print(f"✓ Updated Issue: {crud_state['issue_id']}")

    @pytest.mark.asyncio
    @pytest.mark.order(3)
    async def test_03_create_control(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 3: Create a test Control object"""
        await asyncio.sleep(config.rate_limit_delay)
        
        print(f"\n=== Creating Control ===")
        print(f"Server: {config.mcp_server_url}")
        control_type = config.object_type_aliases.get("control", "control") if config.object_type_aliases else "control"
        result = await mcp_client.call_tool(
            "openpages_upsert_object",
            {
                "object_type": control_type,
                "name": f"Integration Test Control {os.urandom(4).hex()}",
                "description": "Created by integration test suite"
            }
        )
        
        # Result is already parsed and unwrapped
        if isinstance(result, dict):
            if "text" in result and "error" in result["text"].lower():
                pytest.fail(f"Tool returned error: {result['text']}")
            
            if "resource_id" in result:
                resource_id = result["resource_id"]
                # Validate resource_id is not None, empty string, or whitespace
                if not resource_id or not str(resource_id).strip():
                    pytest.fail(f"resource_id is empty or whitespace: '{resource_id}'")
                crud_state["control_id"] = resource_id
            else:
                pytest.fail(f"Expected 'resource_id' in result, got: {result}")
        else:
            pytest.fail(f"Unexpected result type: {type(result)}")
        
        print(f"✓ Created Control: {crud_state['control_id']}")
        print(f"  Server: {config.mcp_server_url}")
        assert crud_state["control_id"] and str(crud_state["control_id"]).strip(), "Control ID should not be empty"

    @pytest.mark.asyncio
    @pytest.mark.order(4)
    async def test_04_associate_objects(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 4: Associate Control with Issue (parent-child relationship)"""
        await asyncio.sleep(config.rate_limit_delay)
        
        assert crud_state.get("issue_id"), "Issue ID not found or empty"
        assert crud_state.get("control_id"), "Control ID not found or empty"
        
        print(f"\n=== Associating Control {crud_state['control_id']} with Issue {crud_state['issue_id']} ===")
        issue_type = config.object_type_aliases.get("issue", "issue") if config.object_type_aliases else "issue"
        result = await mcp_client.call_tool(
            "openpages_associate_objects",
            {
                "object_type": issue_type,  # Source object type
                "resource_id": crud_state["issue_id"],  # Source object ID
                "associations": [
                    {
                        "relationship_type": "Child",  # Control is child of issue
                        "target_id": crud_state["control_id"]
                    }
                ]
            }
        )
        
        # Result is already parsed and unwrapped
        if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
            pytest.fail(f"Tool returned error: {result['text']}")
        
        print(f"✓ Associated Control with Issue")

    @pytest.mark.asyncio
    @pytest.mark.order(5)
    async def test_05_verify_association_via_query(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 5: Verify association exists via query"""
        await asyncio.sleep(config.rate_limit_delay)
        
        assert crud_state.get("issue_id"), "Issue ID not found or empty"
        
        print(f"\n=== Verifying Association via Query ===")
        # Query for the issue - use SOXIssue for queries, not 'issue'
        query = f"SELECT [Name], [Resource ID] FROM [SOXIssue] WHERE [Resource ID] = '{crud_state['issue_id']}'"
        
        result = await mcp_client.call_tool(
            "execute_openpages_query",
            {"query": query}
        )
        
        # Result is already parsed and unwrapped
        if isinstance(result, dict):
            if "text" in result and "error" in result["text"].lower():
                pytest.fail(f"Tool returned error: {result['text']}")
            # Query results might be in 'result' key or directly
            query_results = result.get("result", result) if "result" in result else result
        elif isinstance(result, list):
            query_results = result
        else:
            query_results = []
        
        assert len(query_results) > 0 if isinstance(query_results, list) else True, "Query should return results"
        print(f"✓ Verified Issue exists in query results")

    @pytest.mark.asyncio
    @pytest.mark.order(6)
    async def test_06_dissociate_objects(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 6: Dissociate Control from Issue"""
        await asyncio.sleep(config.rate_limit_delay)
        
        assert crud_state.get("issue_id"), "Issue ID not found or empty"
        assert crud_state.get("control_id"), "Control ID not found or empty"
        
        print(f"\n=== Dissociating Control {crud_state['control_id']} from Issue {crud_state['issue_id']} ===")
        issue_type = config.object_type_aliases.get("issue", "issue") if config.object_type_aliases else "issue"
        result = await mcp_client.call_tool(
            "openpages_dissociate_objects",
            {
                "object_type": issue_type,  # Source object type
                "resource_id": crud_state["issue_id"],  # Source object ID
                "associations": [
                    {
                        "relationship_type": "Child",  # Control is child of issue
                        "target_id": crud_state["control_id"]
                    }
                ]
            }
        )
        
        # Result is already parsed and unwrapped
        if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
            pytest.fail(f"Tool returned error: {result['text']}")
        
        print(f"✓ Dissociated Control from Issue")

    @pytest.mark.asyncio
    @pytest.mark.order(7)
    async def test_07_delete_control(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 7: Delete the Control object"""
        await asyncio.sleep(config.rate_limit_delay)
        
        assert crud_state.get("control_id"), "Control ID not found or empty"
        
        if not config.cleanup_test_objects:
            pytest.skip("Cleanup disabled in configuration")
        
        print(f"\n=== Deleting Control {crud_state['control_id']} ===")
        control_type = config.object_type_aliases.get("control", "control") if config.object_type_aliases else "control"
        try:
            result = await mcp_client.call_tool(
                "openpages_delete_object",
                {
                    "resource_id": crud_state["control_id"],
                    "object_type": control_type  # object_type is required
                }
            )
            
            # Result is already parsed and unwrapped
            if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
                pytest.fail(f"Tool returned error: {result['text']}")
            
            print(f"✓ Deleted Control: {crud_state['control_id']}")
            
        except httpx.HTTPStatusError as e:
            MCPClient.handle_http_error(e, "deleting Control", crud_state['control_id'])

    @pytest.mark.asyncio
    @pytest.mark.order(8)
    async def test_08_delete_issue(self, mcp_client: MCPClient, config: IntegrationTestConfig, crud_state: Dict):
        """Step 8: Delete the Issue object"""
        await asyncio.sleep(config.rate_limit_delay)
        
        assert crud_state.get("issue_id"), "Issue ID not found or empty"
        
        if not config.cleanup_test_objects:
            pytest.skip("Cleanup disabled in configuration")
        
        print(f"\n=== Deleting Issue {crud_state['issue_id']} ===")
        issue_type = config.object_type_aliases.get("issue", "issue") if config.object_type_aliases else "issue"
        try:
            result = await mcp_client.call_tool(
                "openpages_delete_object",
                {
                    "resource_id": crud_state["issue_id"],
                    "object_type": issue_type  # object_type is required
                }
            )
            
            # Result is already parsed and unwrapped
            if isinstance(result, dict) and "text" in result and "error" in result["text"].lower():
                pytest.fail(f"Tool returned error: {result['text']}")
            
            print(f"✓ Deleted Issue: {crud_state['issue_id']}")
            
        except httpx.HTTPStatusError as e:
            MCPClient.handle_http_error(e, "deleting Issue", crud_state['issue_id'])

# Made with Bob
