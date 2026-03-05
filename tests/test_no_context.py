"""
Test that tools work correctly when NO context variables are passed

This test verifies backward compatibility - tools should work exactly
as before when no context variables are provided.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.mcp.context import extract_context_from_arguments, ContextVariables


def test_no_context_variables():
    """Test that tools work when no context variables are provided"""
    print("Testing backward compatibility - no context variables...")
    
    # Test 1: Simple tool arguments with no context
    arguments = {
        "name": "Test Issue",
        "description": "A test issue",
        "status": "Active"
    }
    
    cleaned_args, context = extract_context_from_arguments(arguments)
    
    # Verify cleaned args are unchanged
    assert cleaned_args == arguments, "Arguments should remain unchanged when no context provided"
    print("[PASS] Arguments unchanged when no context")
    
    # Verify context is empty but valid
    assert isinstance(context, ContextVariables), "Context should be ContextVariables instance"
    assert context.to_dict() == {}, "Context should be empty dict"
    print("[PASS] Empty context is valid ContextVariables instance")
    
    # Verify all context properties return None
    assert context.op_username is None, "op_username should be None"
    assert context.op_user_profile_id is None, "op_user_profile_id should be None"
    assert context.op_user_locale is None, "op_user_locale should be None"
    assert context.op_user_profile_name is None, "op_user_profile_name should be None"
    assert context.op_base_url is None, "op_base_url should be None"
    assert context.op_view_type is None, "op_view_type should be None"
    assert context.op_view_name is None, "op_view_name should be None"
    assert context.op_object_type_name is None, "op_object_type_name should be None"
    assert context.op_object_id is None, "op_object_id should be None"
    assert context.op_object_name is None, "op_object_name should be None"
    assert context.op_workflow_stage is None, "op_workflow_stage should be None"
    assert context.op_auth_header is None, "op_auth_header should be None"
    print("[PASS] All context properties return None when empty")
    
    # Test 2: Empty arguments
    empty_args = {}
    cleaned_args, context = extract_context_from_arguments(empty_args)
    
    assert cleaned_args == {}, "Empty args should remain empty"
    assert context.to_dict() == {}, "Context should be empty"
    print("[PASS] Empty arguments handled correctly")
    
    # Test 3: Using get() with defaults on empty context
    assert context.get("op_username", "default_user") == "default_user", "get() should return default"
    assert context.get("op_base_url", "https://default.com") == "https://default.com", "get() should return default"
    print("[PASS] get() with defaults works on empty context")
    
    print("\nBackward compatibility verified!")
    print("Tools work correctly when NO context variables are provided.")


def test_tool_simulation():
    """Simulate a tool call with no context variables"""
    print("\nSimulating tool call without context variables...")
    
    # Simulate a typical tool call
    tool_arguments = {
        "query": "SELECT [Resource ID], [Name] FROM [SOXIssue]",
        "limit": 20,
        "format": "table"
    }
    
    # Extract context (simulating what tool handlers do)
    cleaned_args, context = extract_context_from_arguments(tool_arguments)
    
    # Verify the tool would receive correct arguments
    assert "query" in cleaned_args, "Tool should receive query parameter"
    assert "limit" in cleaned_args, "Tool should receive limit parameter"
    assert "format" in cleaned_args, "Tool should receive format parameter"
    assert len(cleaned_args) == 3, "Tool should receive exactly 3 parameters"
    print("[PASS] Tool receives correct arguments")
    
    # Verify context is empty but doesn't break anything
    assert context.to_dict() == {}, "Context should be empty"
    print("[PASS] Empty context doesn't interfere with tool execution")
    
    print("\nTool simulation successful!")


if __name__ == "__main__":
    print("=" * 60)
    print("No Context Variables Test Suite")
    print("Verifying Backward Compatibility")
    print("=" * 60)
    print()
    
    try:
        test_no_context_variables()
        test_tool_simulation()
        
        print("\n" + "=" * 60)
        print("ALL BACKWARD COMPATIBILITY TESTS PASSED!")
        print("=" * 60)
        print("\nConclusion: Tools work perfectly when NO context")
        print("variables are provided. Full backward compatibility!")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)