"""
Test Context Variables Implementation

This module tests the context variable functionality in the MCP server,
ensuring that context variables are properly extracted, validated, and
passed through to tool handlers.
"""

import pytest
from src.app.mcp.context import (
    ContextVariables,
    extract_context_from_arguments,
    build_context_schema,
    ALLOWED_CONTEXT_VARIABLES
)


class TestContextVariables:
    """Test the ContextVariables class"""
    
    def test_init_empty(self):
        """Test initialization with no data"""
        context = ContextVariables()
        assert context.to_dict() == {}
    
    def test_init_with_valid_data(self):
        """Test initialization with valid context data"""
        data = {
            "op_username": "testuser",
            "op_user_profile_id": "12345",
            "op_base_url": "https://openpages.example.com"
        }
        context = ContextVariables(data)
        assert context.op_username == "testuser"
        assert context.op_user_profile_id == "12345"
        assert context.op_base_url == "https://openpages.example.com"
    
    def test_init_with_invalid_data(self):
        """Test initialization with invalid context variables"""
        data = {
            "op_username": "testuser",
            "invalid_key": "should_be_ignored",
            "op_base_url": "https://openpages.example.com"
        }
        context = ContextVariables(data)
        assert context.op_username == "testuser"
        assert context.op_base_url == "https://openpages.example.com"
        assert context.get("invalid_key") is None
    
    def test_get_method(self):
        """Test the get method"""
        context = ContextVariables({"op_username": "testuser"})
        assert context.get("op_username") == "testuser"
        assert context.get("nonexistent") is None
        assert context.get("nonexistent", "default") == "default"
    
    def test_set_method_valid(self):
        """Test setting a valid context variable"""
        context = ContextVariables()
        context.set("op_username", "newuser")
        assert context.op_username == "newuser"
    
    def test_set_method_invalid(self):
        """Test setting an invalid context variable raises error"""
        context = ContextVariables()
        with pytest.raises(ValueError, match="Invalid context variable"):
            context.set("invalid_key", "value")
    
    def test_properties(self):
        """Test all property accessors"""
        data = {
            "op_username": "user1",
            "op_user_profile_id": "123",
            "op_user_locale": "en_US",
            "op_user_profile_name": "Admin",
            "op_base_url": "https://example.com",
            "op_view_type": "task",
            "op_view_name": "My View",
            "op_object_type_name": "SOXIssue",
            "op_object_id": "456",
            "op_object_name": "Test Issue",
            "op_workflow_stage": "Draft"
        }
        context = ContextVariables(data)
        
        assert context.op_username == "user1"
        assert context.op_user_profile_id == "123"
        assert context.op_user_locale == "en_US"
        assert context.op_user_profile_name == "Admin"
        assert context.op_base_url == "https://example.com"
        assert context.op_view_type == "task"
        assert context.op_view_name == "My View"
        assert context.op_object_type_name == "SOXIssue"
        assert context.op_object_id == "456"
        assert context.op_object_name == "Test Issue"
        assert context.op_workflow_stage == "Draft"


class TestExtractContextFromArguments:
    """Test the extract_context_from_arguments function"""
    
    def test_no_context_variables(self):
        """Test extraction when no context variables present"""
        arguments = {
            "name": "Test",
            "description": "A test object"
        }
        cleaned_args, context = extract_context_from_arguments(arguments)
        
        assert cleaned_args == arguments
        assert context.to_dict() == {}
    
    def test_only_context_variables(self):
        """Test extraction when only context variables present"""
        arguments = {
            "op_username": "testuser",
            "op_base_url": "https://example.com"
        }
        cleaned_args, context = extract_context_from_arguments(arguments)
        
        assert cleaned_args == {}
        assert context.op_username == "testuser"
        assert context.op_base_url == "https://example.com"
    
    def test_mixed_arguments(self):
        """Test extraction with both regular and context variables"""
        arguments = {
            "name": "Test Issue",
            "op_username": "testuser",
            "description": "Test description",
            "op_object_id": "12345",
            "status": "Active"
        }
        cleaned_args, context = extract_context_from_arguments(arguments)
        
        assert cleaned_args == {
            "name": "Test Issue",
            "description": "Test description",
            "status": "Active"
        }
        assert context.op_username == "testuser"
        assert context.op_object_id == "12345"
    
    def test_invalid_context_variables_ignored(self):
        """Test that invalid context variables are kept in cleaned_args"""
        arguments = {
            "name": "Test",
            "invalid_context": "should_stay",
            "op_username": "testuser"
        }
        cleaned_args, context = extract_context_from_arguments(arguments)
        
        assert cleaned_args == {
            "name": "Test",
            "invalid_context": "should_stay"
        }
        assert context.op_username == "testuser"


class TestBuildContextSchema:
    """Test the build_context_schema function"""
    
    def test_schema_structure(self):
        """Test that schema has correct structure"""
        schema = build_context_schema()
        
        assert isinstance(schema, dict)
        assert len(schema) == len(ALLOWED_CONTEXT_VARIABLES)
        
        # Check all allowed variables are in schema
        for var in ALLOWED_CONTEXT_VARIABLES:
            assert var in schema
            assert "type" in schema[var]
            assert "description" in schema[var]
            assert schema[var]["type"] == "string"
    
    def test_schema_descriptions(self):
        """Test that all schema entries have meaningful descriptions"""
        schema = build_context_schema()
        
        for var, props in schema.items():
            assert len(props["description"]) > 10  # Meaningful description
            assert var.replace("_", " ") in props["description"].lower() or \
                   "user" in props["description"].lower() or \
                   "object" in props["description"].lower() or \
                   "view" in props["description"].lower() or \
                   "url" in props["description"].lower() or \
                   "workflow" in props["description"].lower() or \
                   "auth" in props["description"].lower()


class TestAllowedContextVariables:
    """Test the ALLOWED_CONTEXT_VARIABLES constant"""
    
    def test_all_required_variables_present(self):
        """Test that all required context variables are defined"""
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

        assert ALLOWED_CONTEXT_VARIABLES == required_vars

    def test_no_extra_variables(self):
        """Test that no extra variables are defined"""
        assert len(ALLOWED_CONTEXT_VARIABLES) == 12


# Made with Bob