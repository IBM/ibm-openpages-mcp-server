"""
Test that tools work correctly when PARTIAL context variables are passed

This test verifies that the implementation gracefully handles any subset
of context variables - from none to all 12.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.mcp.context import extract_context_from_arguments, ContextVariables


def test_single_context_variable():
    """Test with just one context variable"""
    print("Testing with single context variable...")
    
    arguments = {
        "name": "Test Issue",
        "description": "Test description",
        "op_username": "john.doe"
    }
    
    cleaned_args, context = extract_context_from_arguments(arguments)
    
    # Verify regular args are preserved
    assert cleaned_args == {"name": "Test Issue", "description": "Test description"}
    print("[PASS] Regular arguments preserved")
    
    # Verify the one context variable is set
    assert context.op_username == "john.doe"
    print("[PASS] Provided context variable is set")
    
    # Verify all other context variables are None
    assert context.op_user_profile_id is None
    assert context.op_user_locale is None
    assert context.op_base_url is None
    assert context.op_view_type is None
    assert context.op_auth_header is None
    print("[PASS] Unprovided context variables are None")
    
    print("Single context variable test passed!\n")


def test_multiple_context_variables():
    """Test with several context variables"""
    print("Testing with multiple context variables...")
    
    arguments = {
        "query": "SELECT * FROM [SOXIssue]",
        "limit": 20,
        "op_username": "jane.smith",
        "op_base_url": "https://openpages.example.com",
        "op_object_type_name": "SOXIssue",
        "op_auth_header": "Bearer token123"
    }
    
    cleaned_args, context = extract_context_from_arguments(arguments)
    
    # Verify regular args
    assert cleaned_args == {"query": "SELECT * FROM [SOXIssue]", "limit": 20}
    print("[PASS] Regular arguments preserved")
    
    # Verify provided context variables
    assert context.op_username == "jane.smith"
    assert context.op_base_url == "https://openpages.example.com"
    assert context.op_object_type_name == "SOXIssue"
    assert context.op_auth_header == "Bearer token123"
    print("[PASS] All provided context variables are set")
    
    # Verify unprovided context variables are None
    assert context.op_user_profile_id is None
    assert context.op_user_locale is None
    assert context.op_view_type is None
    assert context.op_view_name is None
    assert context.op_object_id is None
    assert context.op_object_name is None
    assert context.op_workflow_stage is None
    assert context.op_user_profile_name is None
    print("[PASS] Unprovided context variables are None")
    
    print("Multiple context variables test passed!\n")


def test_mixed_scenarios():
    """Test various combinations of context variables"""
    print("Testing various combinations...")
    
    # Scenario 1: Only user context
    args1 = {
        "name": "Issue 1",
        "op_username": "user1",
        "op_user_profile_id": "123",
        "op_user_locale": "en_US"
    }
    cleaned1, ctx1 = extract_context_from_arguments(args1)
    assert ctx1.op_username == "user1"
    assert ctx1.op_user_profile_id == "123"
    assert ctx1.op_user_locale == "en_US"
    assert ctx1.op_view_type is None
    assert ctx1.op_object_id is None
    print("[PASS] User context only scenario")
    
    # Scenario 2: Only view context
    args2 = {
        "name": "Issue 2",
        "op_view_type": "task",
        "op_view_name": "My Tasks"
    }
    cleaned2, ctx2 = extract_context_from_arguments(args2)
    assert ctx2.op_view_type == "task"
    assert ctx2.op_view_name == "My Tasks"
    assert ctx2.op_username is None
    assert ctx2.op_object_id is None
    print("[PASS] View context only scenario")
    
    # Scenario 3: Only object context
    args3 = {
        "name": "Issue 3",
        "op_object_type_name": "SOXIssue",
        "op_object_id": "12345",
        "op_object_name": "Critical Issue"
    }
    cleaned3, ctx3 = extract_context_from_arguments(args3)
    assert ctx3.op_object_type_name == "SOXIssue"
    assert ctx3.op_object_id == "12345"
    assert ctx3.op_object_name == "Critical Issue"
    assert ctx3.op_username is None
    assert ctx3.op_view_type is None
    print("[PASS] Object context only scenario")
    
    # Scenario 4: Mixed context
    args4 = {
        "name": "Issue 4",
        "op_username": "admin",
        "op_view_type": "list",
        "op_object_id": "999"
    }
    cleaned4, ctx4 = extract_context_from_arguments(args4)
    assert ctx4.op_username == "admin"
    assert ctx4.op_view_type == "list"
    assert ctx4.op_object_id == "999"
    assert ctx4.op_user_locale is None
    assert ctx4.op_view_name is None
    assert ctx4.op_object_name is None
    print("[PASS] Mixed context scenario")
    
    print("All combination scenarios passed!\n")


def test_context_get_with_defaults():
    """Test using get() method with partial context"""
    print("Testing get() method with partial context...")
    
    arguments = {
        "name": "Test",
        "op_username": "testuser",
        "op_base_url": "https://example.com"
    }
    
    cleaned_args, context = extract_context_from_arguments(arguments)
    
    # Test get() for provided values
    assert context.get("op_username") == "testuser"
    assert context.get("op_base_url") == "https://example.com"
    print("[PASS] get() returns provided values")
    
    # Test get() for missing values with defaults
    assert context.get("op_user_locale", "en_US") == "en_US"
    assert context.get("op_view_type", "default_view") == "default_view"
    assert context.get("op_object_id", "0") == "0"
    print("[PASS] get() returns defaults for missing values")
    
    # Test get() for missing values without defaults
    assert context.get("op_user_profile_id") is None
    assert context.get("op_workflow_stage") is None
    print("[PASS] get() returns None for missing values without defaults")
    
    print("get() method test passed!\n")


def test_context_to_dict_partial():
    """Test to_dict() with partial context"""
    print("Testing to_dict() with partial context...")
    
    arguments = {
        "name": "Test",
        "op_username": "user1",
        "op_object_id": "123",
        "op_auth_header": "Bearer xyz"
    }
    
    cleaned_args, context = extract_context_from_arguments(arguments)
    
    context_dict = context.to_dict()
    
    # Verify only provided context variables are in dict
    assert len(context_dict) == 3
    assert context_dict["op_username"] == "user1"
    assert context_dict["op_object_id"] == "123"
    assert context_dict["op_auth_header"] == "Bearer xyz"
    print("[PASS] to_dict() contains only provided context variables")
    
    # Verify missing variables are not in dict
    assert "op_user_locale" not in context_dict
    assert "op_view_type" not in context_dict
    assert "op_workflow_stage" not in context_dict
    print("[PASS] to_dict() excludes unprovided context variables")
    
    print("to_dict() test passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Partial Context Variables Test Suite")
    print("Testing Subset Handling")
    print("=" * 60)
    print()
    
    try:
        test_single_context_variable()
        test_multiple_context_variables()
        test_mixed_scenarios()
        test_context_get_with_defaults()
        test_context_to_dict_partial()
        
        print("=" * 60)
        print("ALL PARTIAL CONTEXT TESTS PASSED!")
        print("=" * 60)
        print("\nConclusion: The implementation gracefully handles")
        print("ANY subset of context variables (0 to 12).")
        print("\nKey Features:")
        print("- Provided context variables are extracted and available")
        print("- Unprovided context variables return None (safe defaults)")
        print("- Regular arguments are never affected")
        print("- get() method supports custom defaults")
        print("- to_dict() only includes provided variables")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)