"""
Test MCP Prompts Implementation

This test verifies that the MCP prompts functionality works correctly,
including prompts/list and prompts/get methods.
"""

import pytest
import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing"""
    settings = Settings()
    # Override with test values
    settings.OPENPAGES_BASE_URL = "https://test.openpages.com"
    settings.OPENPAGES_USERNAME = "test_user"
    settings.OPENPAGES_PASSWORD = "test_pass"
    settings.OPENPAGES_AUTHENTICATION_TYPE = "basic"
    settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "tool_prefix": "issue",
            "display_name": "Issue",
            "create_fields": {
                "include_all_fields": False,
                "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
            }
        },
        {
            "type_id": "SOXControl",
            "tool_prefix": "control",
            "display_name": "Control",
            "create_fields": {
                "include_all_fields": False,
                "fields": ["OPSS-Ctl:Status"]
            }
        }
    ]
    return settings


@pytest.mark.asyncio
async def test_initialize_advertises_prompts_capability(mock_settings):
    """Test that initialize response advertises prompts capability"""
    server = MCPServer(custom_settings=mock_settings)
    
    # Call initialize
    result = await server.handle_initialize({
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    })
    
    # Verify prompts capability is advertised
    assert "capabilities" in result
    assert "prompts" in result["capabilities"]
    assert result["capabilities"]["prompts"]["list"]["enabled"] is True
    assert result["capabilities"]["prompts"]["get"]["enabled"] is True
    print("✓ Initialize advertises prompts capability correctly")


@pytest.mark.asyncio
async def test_prompts_list(mock_settings):
    """Test prompts/list returns available prompts"""
    server = MCPServer(custom_settings=mock_settings)
    
    # Call prompts/list via request processor
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "prompts/list",
        "params": {}
    }
    
    response, should_exit = await server.process_request(request)
    
    # Verify response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "prompts" in response["result"]
    
    prompts = response["result"]["prompts"]
    assert len(prompts) > 0
    
    # Verify the openpages-usage-guide prompt exists
    usage_guide = next((p for p in prompts if p["name"] == "openpages-usage-guide"), None)
    assert usage_guide is not None
    assert "description" in usage_guide
    assert "arguments" in usage_guide
    
    print(f"✓ prompts/list returned {len(prompts)} prompt(s)")
    print(f"  - Prompt: {usage_guide['name']}")
    print(f"  - Description: {usage_guide['description'][:80]}...")


@pytest.mark.asyncio
async def test_prompts_get_without_arguments(mock_settings):
    """Test prompts/get returns prompt content without arguments"""
    server = MCPServer(custom_settings=mock_settings)
    
    # Call prompts/get via request processor
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "prompts/get",
        "params": {
            "name": "openpages-usage-guide"
        }
    }
    
    response, should_exit = await server.process_request(request)
    
    # Verify response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    assert "result" in response
    
    result = response["result"]
    assert "description" in result
    assert "messages" in result
    assert len(result["messages"]) > 0
    
    # Verify message structure
    message = result["messages"][0]
    assert message["role"] == "user"
    assert "content" in message
    assert message["content"]["type"] == "text"
    assert len(message["content"]["text"]) > 0
    
    # Verify content includes key sections
    content = message["content"]["text"]
    assert "OpenPages MCP Server" in content
    assert "Schema-Driven Approach" in content or "schema" in content.lower()
    assert "Field Filtering" in content or "field" in content.lower()
    
    print("✓ prompts/get returned prompt content successfully")
    print(f"  - Content length: {len(content)} characters")
    print(f"  - Includes schema guidance: {'Schema' in content}")


@pytest.mark.asyncio
async def test_prompts_get_with_task_argument(mock_settings):
    """Test prompts/get returns prompt content with task-specific guidance"""
    server = MCPServer(custom_settings=mock_settings)
    
    # Call prompts/get with task argument
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "prompts/get",
        "params": {
            "name": "openpages-usage-guide",
            "arguments": {
                "task": "create issue"
            }
        }
    }
    
    response, should_exit = await server.process_request(request)
    
    # Verify response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 3
    assert "result" in response
    
    result = response["result"]
    content = result["messages"][0]["content"]["text"]
    
    # Verify task-specific guidance is included
    assert "Task-Specific Guidance" in content or "create" in content.lower()
    
    print("✓ prompts/get with task argument returned task-specific guidance")
    print(f"  - Task: create issue")
    print(f"  - Includes task guidance: {'Task-Specific Guidance' in content}")


@pytest.mark.asyncio
async def test_prompts_get_includes_configured_types(mock_settings):
    """Test prompts/get includes configured object types"""
    server = MCPServer(custom_settings=mock_settings)
    
    # Call prompts/get
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "prompts/get",
        "params": {
            "name": "openpages-usage-guide"
        }
    }
    
    response, should_exit = await server.process_request(request)
    
    # Verify response includes configured types
    content = response["result"]["messages"][0]["content"]["text"]
    
    # Should mention the configured types
    assert "SOXIssue" in content or "Issue" in content
    assert "SOXControl" in content or "Control" in content
    
    print("✓ prompts/get includes configured object types")
    print(f"  - Mentions SOXIssue: {'SOXIssue' in content}")
    print(f"  - Mentions SOXControl: {'SOXControl' in content}")


@pytest.mark.asyncio
async def test_prompts_get_unknown_prompt(mock_settings):
    """Test prompts/get with unknown prompt name returns error"""
    server = MCPServer(custom_settings=mock_settings)
    
    # Call prompts/get with unknown prompt
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "prompts/get",
        "params": {
            "name": "unknown-prompt"
        }
    }
    
    response, should_exit = await server.process_request(request)
    
    # Verify error response
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 5
    assert "error" in response
    assert "Unknown prompt" in response["error"]["message"]
    
    print("✓ prompts/get with unknown prompt returns error correctly")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Testing MCP Prompts Implementation")
    print("="*70 + "\n")
    
    # Run tests
    asyncio.run(test_initialize_advertises_prompts_capability(mock_settings()))
    asyncio.run(test_prompts_list(mock_settings()))
    asyncio.run(test_prompts_get_without_arguments(mock_settings()))
    asyncio.run(test_prompts_get_with_task_argument(mock_settings()))
    asyncio.run(test_prompts_get_includes_configured_types(mock_settings()))
    asyncio.run(test_prompts_get_unknown_prompt(mock_settings()))
    
    print("\n" + "="*70)
    print("All prompts tests passed! ✓")
    print("="*70 + "\n")

# Made with Bob
