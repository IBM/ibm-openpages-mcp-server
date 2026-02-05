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
async def test_tool_call_triggers_schema_load_after_restart():
    """
    Test that tool calls trigger schema loading if schemas are not loaded
    This simulates the server restart scenario
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
        
        # Verify initial state
        assert server.dynamic_schemas_loaded == False, "Schemas should not be loaded initially"
        
        # Simulate tool call with schemas not loaded
        params = {
            "name": "echo",
            "arguments": {"text": "test"}
        }
        
        # Mock the load_dynamic_schemas method to track if it's called
        load_called = False
        
        async def mock_load_dynamic_schemas(force_reload=False):
            nonlocal load_called
            load_called = True
            server.dynamic_schemas_loaded = True
        
        server.load_dynamic_schemas = mock_load_dynamic_schemas
        
        # Execute tool call
        result = await server.tool_handlers.handle_call_tool(params)
        
        # Verify schema loading was triggered
        assert load_called, "Schema loading should be triggered on tool call when schemas not loaded"
        assert "Echo: test" in str(result), "Tool should execute successfully after schema load"


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
async def test_schema_load_failure_returns_error():
    """
    Test that schema loading failures are handled gracefully
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
    
    # Mock the OpenPages client initialization
    with patch('src.app.mcp.mcp_server.OpenPagesClient') as mock_client_class:
        mock_client = Mock()
        mock_client.initialize_auth = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Create server instance
        server = MCPServer(custom_settings=mock_settings)
        
        # Mock load_dynamic_schemas to raise an exception
        async def mock_load_dynamic_schemas_error(force_reload=False):
            raise Exception("Failed to connect to OpenPages")
        
        server.load_dynamic_schemas = mock_load_dynamic_schemas_error
        
        # Execute tool call
        params = {
            "name": "echo",
            "arguments": {"text": "test"}
        }
        result = await server.tool_handlers.handle_call_tool(params)
        
        # Verify error is returned gracefully
        assert "Error" in str(result), "Should return error message"
        assert "Failed to initialize tool schemas" in str(result), "Should indicate schema initialization failure"