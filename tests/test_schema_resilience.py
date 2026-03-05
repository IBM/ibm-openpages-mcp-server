"""
Test Schema Resilience
Tests for schema loading resilience after server restart scenarios
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.app.mcp.mcp_server import MCPServer
from src.app.mcp.tool_handlers import ToolHandlers
from src.app.config.settings import Settings


@pytest.mark.asyncio
async def test_server_initializes_with_schemas_not_loaded():
    """
    Test that server initializes with dynamic_schemas_loaded = False
    and that tool calls work even before schemas are loaded
    """
    # Create a mock settings object
    mock_settings = Mock(spec=Settings)
    mock_settings.OPENPAGES_BASE_URL = "https://test.openpages.com"
    mock_settings.OPENPAGES_AUTHENTICATION_TYPE = "basic"
    mock_settings.OPENPAGES_USERNAME = "test_user"
    mock_settings.OPENPAGES_PASSWORD = "test_pass"
    mock_settings.OPENPAGES_APIKEY = None
    mock_settings.OPENPAGES_AUTHENTICATION_URL = None
    mock_settings.OPENPAGES_INSTANCE_NAME = "test_instance"
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "tool_prefix": "issue",
            "display_name": "Issue",
            "namespace": ""
        }
    ]
    mock_settings.NAMESPACE = ""
    mock_settings.SCHEMA_CACHE_MAX_SIZE = 10
    mock_settings.SCHEMA_CACHE_TTL = 300
    
    # Mock the OpenPages client initialization
    with patch('src.app.mcp.mcp_server.OpenPagesClient') as mock_client_class:
        mock_client = Mock()
        mock_client.initialize_auth = AsyncMock()
        mock_client.get_type_definition = AsyncMock(return_value={
            "field_definitions": []
        })
        mock_client_class.return_value = mock_client
        
        # Create server instance
        server = MCPServer(custom_settings=mock_settings)
        
        # Verify initial state - schemas not loaded yet
        assert server.dynamic_schemas_loaded == False, "Schemas should not be loaded initially"
        
        # Tool calls should still work (echo is a built-in tool)
        params = {
            "name": "echo",
            "arguments": {"text": "test"}
        }
        result = await server.tool_handlers.handle_call_tool(params)
        assert "Echo: test" in str(result), "Echo tool should work before schema load"


@pytest.mark.asyncio
async def test_tool_call_skips_schema_load_when_already_loaded():
    """
    Test that tool calls don't reload schemas if already loaded
    """
    # Create a mock settings object
    mock_settings = Mock(spec=Settings)
    mock_settings.OPENPAGES_BASE_URL = "https://test.openpages.com"
    mock_settings.OPENPAGES_AUTHENTICATION_TYPE = "basic"
    mock_settings.OPENPAGES_USERNAME = "test_user"
    mock_settings.OPENPAGES_PASSWORD = "test_pass"
    mock_settings.OPENPAGES_APIKEY = None
    mock_settings.OPENPAGES_AUTHENTICATION_URL = None
    mock_settings.OPENPAGES_INSTANCE_NAME = "test_instance"
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "tool_prefix": "issue",
            "display_name": "Issue",
            "namespace": ""
        }
    ]
    mock_settings.NAMESPACE = ""
    mock_settings.SCHEMA_CACHE_MAX_SIZE = 10
    mock_settings.SCHEMA_CACHE_TTL = 300
    
    # Mock the OpenPages client initialization
    with patch('src.app.mcp.mcp_server.OpenPagesClient') as mock_client_class:
        mock_client = Mock()
        mock_client.initialize_auth = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Create server instance
        server = MCPServer(custom_settings=mock_settings)
        
        # Set schemas as already loaded
        server.dynamic_schemas_loaded = True
        
        # Mock the load_dynamic_schemas method to track if it's called
        load_called = False
        
        async def mock_load_dynamic_schemas(force_reload=False):
            nonlocal load_called
            load_called = True
        
        server.load_dynamic_schemas = mock_load_dynamic_schemas
        
        # Execute tool call
        params = {
            "name": "echo",
            "arguments": {"text": "test"}
        }
        result = await server.tool_handlers.handle_call_tool(params)
        
        # Verify schema loading was NOT triggered
        assert not load_called, "Schema loading should not be triggered when schemas already loaded"
        assert "Echo: test" in str(result), "Tool should execute successfully"


@pytest.mark.asyncio
async def test_schema_load_can_be_triggered_explicitly():
    """
    Test that load_dynamic_schemas can be called explicitly and updates state
    """
    # Create a mock settings object
    mock_settings = Mock(spec=Settings)
    mock_settings.OPENPAGES_BASE_URL = "https://test.openpages.com"
    mock_settings.OPENPAGES_AUTHENTICATION_TYPE = "basic"
    mock_settings.OPENPAGES_USERNAME = "test_user"
    mock_settings.OPENPAGES_PASSWORD = "test_pass"
    mock_settings.OPENPAGES_APIKEY = None
    mock_settings.OPENPAGES_AUTHENTICATION_URL = None
    mock_settings.OPENPAGES_INSTANCE_NAME = "test_instance"
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "tool_prefix": "issue",
            "display_name": "Issue",
            "namespace": ""
        }
    ]
    mock_settings.NAMESPACE = ""
    mock_settings.SCHEMA_CACHE_MAX_SIZE = 10
    mock_settings.SCHEMA_CACHE_TTL = 300
    
    # Mock the OpenPages client initialization
    with patch('src.app.mcp.mcp_server.OpenPagesClient') as mock_client_class:
        mock_client = Mock()
        mock_client.initialize_auth = AsyncMock()
        mock_client.get_type_definition = AsyncMock(return_value={
            "localizedLabel": "Issue",
            "field_definitions": [],
            "associations": []
        })
        mock_client.get_type_associations = AsyncMock(return_value=[])
        mock_client_class.return_value = mock_client
        
        # Create server instance
        server = MCPServer(custom_settings=mock_settings)
        assert server.dynamic_schemas_loaded == False
        
        # Explicitly trigger schema load
        await server.load_dynamic_schemas()
        
        # Verify schemas are now marked as loaded
        assert server.dynamic_schemas_loaded == True, "Schemas should be marked as loaded after explicit load"