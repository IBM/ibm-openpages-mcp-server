"""
Simple test for MCP Prompts Implementation

This test verifies that the MCP prompts functionality works correctly.
"""

import asyncio
import sys
import os
import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import Settings


def create_mock_settings():
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
            "resource_fields": {
                "include_all_fields": False,
                "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
            }
        },
        {
            "type_id": "SOXControl",
            "tool_prefix": "control",
            "display_name": "Control",
            "resource_fields": {
                "include_all_fields": False,
                "fields": ["OPSS-Ctl:Status"]
            }
        }
    ]
    return settings


@pytest.mark.asyncio
async def test_initialize_advertises_prompts_capability():
    """Test that initialize response advertises prompts capability"""
    print("\n1. Testing initialize advertises prompts capability...")
    
    settings = create_mock_settings()
    server = MCPServer(custom_settings=settings)
    
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
    assert "capabilities" in result, "Missing capabilities in initialize response"
    assert "prompts" in result["capabilities"], "Missing prompts in capabilities"
    # MCP spec: prompts capability advertises listChanged support
    assert "listChanged" in result["capabilities"]["prompts"], "prompts capability missing listChanged"
    
    print("   [PASS] Initialize advertises prompts capability correctly")
    return True


@pytest.mark.asyncio
async def test_prompts_list():
    """Test prompts/list returns available prompts"""
    print("\n2. Testing prompts/list...")
    
    settings = create_mock_settings()
    server = MCPServer(custom_settings=settings)
    
    # Call prompts/list via request processor
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "prompts/list",
        "params": {}
    }
    
    response, should_exit = await server.process_request(request)
    
    # Verify response
    assert response["jsonrpc"] == "2.0", "Invalid JSON-RPC version"
    assert response["id"] == 1, "Invalid response ID"
    assert "result" in response, "Missing result in response"
    assert "prompts" in response["result"], "Missing prompts in result"
    
    prompts = response["result"]["prompts"]
    assert len(prompts) > 0, "No prompts returned"
    
    # Verify the openpages-usage-guide prompt exists
    usage_guide = next((p for p in prompts if p["name"] == "openpages-usage-guide"), None)
    assert usage_guide is not None, "openpages-usage-guide prompt not found"
    assert "description" in usage_guide, "Missing description in prompt"
    assert "arguments" in usage_guide, "Missing arguments in prompt"
    
    print(f"   [PASS] prompts/list returned {len(prompts)} prompt(s)")
    print(f"     - Prompt: {usage_guide['name']}")
    print(f"     - Description: {usage_guide['description'][:80]}...")
    return True


@pytest.mark.asyncio
async def test_prompts_get_without_arguments():
    """Test prompts/get returns prompt content without arguments"""
    print("\n3. Testing prompts/get without arguments...")
    
    settings = create_mock_settings()
    server = MCPServer(custom_settings=settings)
    
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
    assert response["jsonrpc"] == "2.0", "Invalid JSON-RPC version"
    assert response["id"] == 2, "Invalid response ID"
    assert "result" in response, "Missing result in response"
    
    result = response["result"]
    assert "description" in result, "Missing description in result"
    assert "messages" in result, "Missing messages in result"
    assert len(result["messages"]) > 0, "No messages in result"
    
    # Verify message structure
    message = result["messages"][0]
    assert message["role"] == "user", "Invalid message role"
    assert "content" in message, "Missing content in message"
    assert message["content"]["type"] == "text", "Invalid content type"
    assert len(message["content"]["text"]) > 0, "Empty content text"
    
    # Verify content includes key sections
    content = message["content"]["text"]
    assert "OpenPages MCP Server" in content, "Missing server name in content"
    assert "schema" in content.lower(), "Missing schema guidance in content"
    
    print("   [PASS] prompts/get returned prompt content successfully")
    print(f"     - Content length: {len(content)} characters")
    print(f"     - Includes schema guidance: {'Schema' in content}")
    return True


@pytest.mark.asyncio
async def test_prompts_get_with_task_argument():
    """Test prompts/get returns prompt content with task-specific guidance"""
    print("\n4. Testing prompts/get with task argument...")
    
    settings = create_mock_settings()
    server = MCPServer(custom_settings=settings)
    
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
    assert response["jsonrpc"] == "2.0", "Invalid JSON-RPC version"
    assert response["id"] == 3, "Invalid response ID"
    assert "result" in response, "Missing result in response"
    
    result = response["result"]
    content = result["messages"][0]["content"]["text"]
    
    # Verify task-specific guidance is included
    has_task_guidance = "Task-Specific Guidance" in content or "create" in content.lower()
    assert has_task_guidance, "Missing task-specific guidance"
    
    print("   [PASS] prompts/get with task argument returned task-specific guidance")
    print(f"     - Task: create issue")
    print(f"     - Includes task guidance: {'Task-Specific Guidance' in content}")
    return True


@pytest.mark.asyncio
async def test_prompts_get_includes_configured_types():
    """Test prompts/get includes configured object types"""
    print("\n5. Testing prompts/get includes configured types...")
    
    settings = create_mock_settings()
    server = MCPServer(custom_settings=settings)
    
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
    has_issue = "SOXIssue" in content or "Issue" in content
    has_control = "SOXControl" in content or "Control" in content
    assert has_issue, "Missing SOXIssue/Issue in content"
    assert has_control, "Missing SOXControl/Control in content"
    
    print("   [PASS] prompts/get includes configured object types")
    print(f"     - Mentions SOXIssue: {'SOXIssue' in content}")
    print(f"     - Mentions SOXControl: {'SOXControl' in content}")
    return True


@pytest.mark.asyncio
async def test_prompts_get_unknown_prompt():
    """Test prompts/get with unknown prompt name returns error"""
    print("\n6. Testing prompts/get with unknown prompt...")
    
    settings = create_mock_settings()
    server = MCPServer(custom_settings=settings)
    
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
    assert response["jsonrpc"] == "2.0", "Invalid JSON-RPC version"
    assert response["id"] == 5, "Invalid response ID"
    assert "error" in response, "Missing error in response"
    assert "Unknown prompt" in response["error"]["message"], "Invalid error message"
    
    print("   [PASS] prompts/get with unknown prompt returns error correctly")
    return True


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("Testing MCP Prompts Implementation")
    print("="*70)
    
    tests = [
        test_initialize_advertises_prompts_capability,
        test_prompts_list,
        test_prompts_get_without_arguments,
        test_prompts_get_with_task_argument,
        test_prompts_get_includes_configured_types,
        test_prompts_get_unknown_prompt
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
        except Exception as e:
            print(f"   [FAIL] Test failed: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"Test Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All prompts tests passed!")
    print("="*70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

# Made with Bob
