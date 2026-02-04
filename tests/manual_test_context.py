"""
Manual Test for Context Variables

This script manually tests the context variable functionality
without requiring pytest.
"""

import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.mcp.context import (
    ContextVariables,
    extract_context_from_arguments,
    build_context_schema,
    ALLOWED_CONTEXT_VARIABLES
)


def test_context_variables():
    """Test ContextVariables class"""
    print("Testing ContextVariables class...")
    
    # Test 1: Empty initialization
    context = ContextVariables()
    assert context.to_dict() == {}, "Empty context should have empty dict"
    print("[PASS] Empty initialization works")
    
    # Test 2: Valid data
    data = {
        "op_username": "testuser",
        "op_user_profile_id": "12345",
        "op_base_url": "https://openpages.example.com"
    }
    context = ContextVariables(data)
    assert context.op_username == "testuser", "Username should be set"
    assert context.op_user_profile_id == "12345", "Profile ID should be set"
    assert context.op_base_url == "https://openpages.example.com", "Base URL should be set"
    print("[PASS] Valid data initialization works")
    
    # Test 3: Invalid data filtered out
    data_with_invalid = {
        "op_username": "testuser",
        "invalid_key": "should_be_ignored",
        "op_base_url": "https://openpages.example.com"
    }
    context = ContextVariables(data_with_invalid)
    assert context.op_username == "testuser", "Valid data should be kept"
    assert context.get("invalid_key") is None, "Invalid data should be filtered"
    print("[PASS] Invalid data filtering works")
    
    # Test 4: Set method
    context = ContextVariables()
    context.set("op_username", "newuser")
    assert context.op_username == "newuser", "Set should work for valid keys"
    print("[PASS] Set method works for valid keys")
    
    # Test 5: Set invalid key
    try:
        context.set("invalid_key", "value")
        assert False, "Should raise ValueError for invalid key"
    except ValueError as e:
        assert "Invalid context variable" in str(e)
        print("[PASS] Set method raises error for invalid keys")
    
    print("\nContextVariables tests passed!\n")


def test_extract_context():
    """Test extract_context_from_arguments function"""
    print("Testing extract_context_from_arguments...")
    
    # Test 1: No context variables
    arguments = {
        "name": "Test",
        "description": "A test object"
    }
    cleaned_args, context = extract_context_from_arguments(arguments)
    assert cleaned_args == arguments, "Arguments without context should remain unchanged"
    assert context.to_dict() == {}, "Context should be empty"
    print("[PASS] No context variables case works")
    
    # Test 2: Only context variables
    arguments = {
        "op_username": "testuser",
        "op_base_url": "https://example.com"
    }
    cleaned_args, context = extract_context_from_arguments(arguments)
    assert cleaned_args == {}, "Cleaned args should be empty"
    assert context.op_username == "testuser", "Context should have username"
    assert context.op_base_url == "https://example.com", "Context should have base URL"
    print("[PASS] Only context variables case works")
    
    # Test 3: Mixed arguments
    arguments = {
        "name": "Test Issue",
        "op_username": "testuser",
        "description": "Test description",
        "op_object_id": "12345",
        "status": "Active"
    }
    cleaned_args, context = extract_context_from_arguments(arguments)
    assert "name" in cleaned_args, "Regular args should be in cleaned_args"
    assert "description" in cleaned_args, "Regular args should be in cleaned_args"
    assert "status" in cleaned_args, "Regular args should be in cleaned_args"
    assert "op_username" not in cleaned_args, "Context vars should not be in cleaned_args"
    assert context.op_username == "testuser", "Context should have username"
    assert context.op_object_id == "12345", "Context should have object ID"
    print("[PASS] Mixed arguments case works")
    
    print("\nextract_context_from_arguments tests passed!\n")


def test_build_schema():
    """Test build_context_schema function"""
    print("Testing build_context_schema...")
    
    schema = build_context_schema()
    
    # Test 1: Schema structure
    assert isinstance(schema, dict), "Schema should be a dict"
    assert len(schema) == len(ALLOWED_CONTEXT_VARIABLES), "Schema should have all allowed variables"
    print("[PASS] Schema has correct structure")
    
    # Test 2: All variables present
    for var in ALLOWED_CONTEXT_VARIABLES:
        assert var in schema, f"Variable {var} should be in schema"
        assert "type" in schema[var], f"Variable {var} should have type"
        assert "description" in schema[var], f"Variable {var} should have description"
        assert schema[var]["type"] == "string", f"Variable {var} should be string type"
    print("[PASS] All variables present with correct properties")
    
    # Test 3: Descriptions are meaningful
    for var, props in schema.items():
        assert len(props["description"]) > 10, f"Description for {var} should be meaningful"
    print("[PASS] All descriptions are meaningful")
    
    print("\nbuild_context_schema tests passed!\n")


def test_allowed_variables():
    """Test ALLOWED_CONTEXT_VARIABLES constant"""
    print("Testing ALLOWED_CONTEXT_VARIABLES...")
    
    required_vars = {
        "op_username",
        "op_user_profile_id",
        "op_user_locale",
        "op_user_profile_name",
        "op_base_url",
        "op_view_type",
        "op_view_name",
        "op_object_type_name",
        "op_object_id",
        "op_object_name",
        "op_workflow_stage",
        "op_auth_header"
    }
    
    assert ALLOWED_CONTEXT_VARIABLES == required_vars, "Should have exactly the required variables"
    assert len(ALLOWED_CONTEXT_VARIABLES) == 12, "Should have exactly 12 variables"
    print("[PASS] All required variables present")
    print("[PASS] No extra variables")
    
    print("\nALLOWED_CONTEXT_VARIABLES tests passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Context Variables Manual Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_context_variables()
        test_extract_context()
        test_build_schema()
        test_allowed_variables()
        
        print("=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)