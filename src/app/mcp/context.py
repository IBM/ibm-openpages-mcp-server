"""
Context Variables Module

This module handles context variables for MCP tools in the OpenPages MCP Server.
Context variables provide additional information about the user, environment, and
current view/object being worked with.

Supported context variables:
- op_username: OpenPages username
- op_user_profile_id: User profile ID
- op_user_locale: User locale (e.g., "en_US")
- op_user_profile_name: User profile name
- op_base_url: OpenPages base URL
- op_view_type: Current view type (e.g., "task", "list")
- op_view_name: Current view name
- op_object_type_name: Current object type name
- op_object_id: Current object ID
- op_object_name: Current object name
- op_workflow_stage: Current workflow stage
"""

import logging
from typing import Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# Define allowed context variable names
ALLOWED_CONTEXT_VARIABLES: Set[str] = {
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


class ContextVariables:
    """
    Container for context variables with validation
    
    This class provides a type-safe way to work with context variables,
    ensuring only allowed variables are accepted and providing convenient
    access methods.
    """
    
    def __init__(self, context_data: Optional[Dict[str, Any]] = None):
        """
        Initialize context variables
        
        Args:
            context_data: Dictionary of context variable names to values
        """
        self._data: Dict[str, Any] = {}
        
        if context_data:
            self._validate_and_set(context_data)
    
    def _validate_and_set(self, context_data: Dict[str, Any]) -> None:
        """
        Validate and set context variables
        
        Args:
            context_data: Dictionary of context variable names to values
        """
        for key, value in context_data.items():
            if key in ALLOWED_CONTEXT_VARIABLES:
                self._data[key] = value
            else:
                logger.warning(f"Ignoring invalid context variable: {key}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a context variable value
        
        Args:
            key: Context variable name
            default: Default value if key not found
            
        Returns:
            Context variable value or default
        """
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a context variable value
        
        Args:
            key: Context variable name
            value: Context variable value
            
        Raises:
            ValueError: If key is not an allowed context variable
        """
        if key not in ALLOWED_CONTEXT_VARIABLES:
            raise ValueError(f"Invalid context variable: {key}. Allowed variables: {', '.join(sorted(ALLOWED_CONTEXT_VARIABLES))}")
        self._data[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context variables to dictionary
        
        Returns:
            Dictionary of context variable names to values
        """
        return self._data.copy()
    
    def __repr__(self) -> str:
        """String representation of context variables with sensitive data obfuscated"""
        sanitized_data = self._get_sanitized_data()
        return f"ContextVariables({sanitized_data})"
    
    def _get_sanitized_data(self) -> Dict[str, Any]:
        """
        Get sanitized copy of context data with sensitive values obfuscated
        
        Returns:
            Dictionary with op_auth_header obfuscated
        """
        sanitized = self._data.copy()
        if "op_auth_header" in sanitized:
            # Show None if value is None, otherwise show *******
            auth_value = sanitized["op_auth_header"]
            sanitized["op_auth_header"] = None if auth_value is None else "*******"
        return sanitized
    
    @property
    def op_username(self) -> Optional[str]:
        """Get OpenPages username"""
        return self._data.get("op_username")
    
    @property
    def op_user_profile_id(self) -> Optional[str]:
        """Get user profile ID"""
        return self._data.get("op_user_profile_id")
    
    @property
    def op_user_locale(self) -> Optional[str]:
        """Get user locale"""
        return self._data.get("op_user_locale")
    
    @property
    def op_user_profile_name(self) -> Optional[str]:
        """Get user profile name"""
        return self._data.get("op_user_profile_name")
    
    @property
    def op_base_url(self) -> Optional[str]:
        """Get OpenPages base URL"""
        return self._data.get("op_base_url")
    
    @property
    def op_view_type(self) -> Optional[str]:
        """Get current view type"""
        return self._data.get("op_view_type")
    
    @property
    def op_view_name(self) -> Optional[str]:
        """Get current view name"""
        return self._data.get("op_view_name")
    
    @property
    def op_object_type_name(self) -> Optional[str]:
        """Get current object type name"""
        return self._data.get("op_object_type_name")
    
    @property
    def op_object_id(self) -> Optional[str]:
        """Get current object ID"""
        return self._data.get("op_object_id")
    
    @property
    def op_object_name(self) -> Optional[str]:
        """Get current object name"""
        return self._data.get("op_object_name")
    
    @property
    def op_workflow_stage(self) -> Optional[str]:
        """Get current workflow stage"""
        return self._data.get("op_workflow_stage")
    
    @property
    def op_auth_header(self) -> Optional[str]:
        """Get authentication header"""
        return self._data.get("op_auth_header")

    @property
    def has_op_auth_header(self) -> bool:
        """Check if op_auth_header key was present in the original arguments."""
        return "op_auth_header" in self._data


def extract_context_from_arguments(arguments: Dict[str, Any]) -> tuple[Dict[str, Any], ContextVariables]:
    """
    Extract context variables from tool arguments
    
    This function separates context variables from regular tool arguments,
    returning both the cleaned arguments and the context variables.
    
    Args:
        arguments: Tool arguments dictionary
        
    Returns:
        Tuple of (cleaned_arguments, context_variables)
    """
    context_data = {}
    cleaned_arguments = {}
    
    for key, value in arguments.items():
        if key in ALLOWED_CONTEXT_VARIABLES:
            context_data[key] = value
        else:
            cleaned_arguments[key] = value
    
    context = ContextVariables(context_data)
    
    if context_data:
        logger.debug(f"Extracted context variables: {list(context_data.keys())}")
    
    return cleaned_arguments, context


def build_context_schema() -> Dict[str, Any]:
    """
    Build JSON schema for context variables
    
    Returns:
        Dictionary containing the JSON schema properties for context variables
    """
    return {
        "op_username": {
            "type": "string",
            "description": "OpenPages username of the current user"
        },
        "op_user_profile_id": {
            "type": "string",
            "description": "User profile ID of the current user"
        },
        "op_user_locale": {
            "type": "string",
            "description": "User locale (e.g., 'en_US', 'fr_FR')"
        },
        "op_user_profile_name": {
            "type": "string",
            "description": "User profile name of the current user"
        },
        "op_base_url": {
            "type": "string",
            "description": "OpenPages base URL"
        },
        "op_view_type": {
            "type": "string",
            "description": "Current view type (e.g., 'task', 'list', 'report')"
        },
        "op_view_name": {
            "type": "string",
            "description": "Current view name"
        },
        "op_object_type_name": {
            "type": "string",
            "description": "Current object type name (e.g., 'ObjectTypeA', 'ObjectTypeB')"
        },
        "op_object_id": {
            "type": "string",
            "description": "Current object ID"
        },
        "op_object_name": {
            "type": "string",
            "description": "Current object name"
        },
        "op_workflow_stage": {
            "type": "string",
            "description": "Current workflow stage"
        },
        "op_auth_header": {
            "type": "string",
            "description": "Authentication header for API requests"
        }
    }


# Made with Bob