"""
Documentation Resources Module

Provides reusable documentation content that AI agents can read once
and cache for the session, significantly reducing token consumption.
"""

import json
from typing import Dict, Any


class DocumentationResources:
    """
    Manages documentation resources for the MCP server
    
    These resources contain instructions and examples that are identical
    across multiple schemas or tools. By providing them as separate resources,
    AI agents can read them once and reference them many times.
    """
    
    @staticmethod
    def get_schema_usage_guide() -> Dict[str, Any]:
        """
        Get comprehensive schema usage instructions
        
        This replaces the usage_instructions object that was previously
        embedded in every schema response (150 tokens per schema).
        
        Returns:
            Dict containing complete usage instructions with examples
        """
        return {
            "title": "OpenPages Schema Usage Guide",
            "version": "1.0",
            "description": "Essential instructions for working with OpenPages object schemas",
            
            "field_usage": {
                "field_names": {
                    "rule": "Always use exact field names as shown in the 'name' property",
                    "query_format": "Enclose field names in square brackets for queries",
                    "example": "SELECT [Resource ID], [Name], [Status] FROM [SOXIssue]"
                },
                "field_types": {
                    "rule": "Respect data_type constraints when creating or updating objects",
                    "types": {
                        "STRING_TYPE": "Text values",
                        "INTEGER_TYPE": "Whole numbers",
                        "DECIMAL_TYPE": "Decimal numbers",
                        "BOOLEAN_TYPE": "true or false",
                        "DATE_TYPE": "ISO 8601 date format (YYYY-MM-DD)",
                        "ENUM_TYPE": "Must use exact values from enum_values array",
                        "MULTI_VALUE_ENUM": "Array of values from enum_values array"
                    }
                },
                "required_fields": {
                    "rule": "Fields with required=true must be provided when creating objects",
                    "example": "If 'Name' has required=true, you must include it in create operations"
                },
                "read_only_fields": {
                    "rule": "Fields with read_only=true cannot be set during create or update",
                    "examples": ["Resource ID", "Created By", "Creation Date", "Last Modified By", "Last Modification Date"]
                },
                "enum_fields": {
                    "rule": "For ENUM_TYPE fields, use exact values from the enum_values array",
                    "example": "If Status enum_values are ['Draft', 'Active', 'Closed'], you must use one of these exact values"
                }
            },
            
            "operation_examples": {
                "query": {
                    "description": "Querying objects with field filters",
                    "example": "SELECT [Resource ID], [Name], [Status] FROM [SOXIssue] WHERE [Status] = 'Active'"
                },
                "create": {
                    "description": "Creating a new object with required fields",
                    "example": {
                        "name": "New Issue",
                        "title": "Security Issue",
                        "Status": "Draft"
                    }
                },
                "update": {
                    "description": "Updating an existing object",
                    "example": {
                        "id": "12345",
                        "Status": "Active",
                        "Priority": "High"
                    }
                }
            },
            
            "best_practices": [
                "Always check required=true fields before creating objects",
                "Use exact enum values - case sensitive",
                "Enclose all field and type names in [square brackets] for queries",
                "Read-only fields are automatically set by the system",
                "Date fields use ISO 8601 format (YYYY-MM-DD)",
                "For relationships, use Resource ID or full path"
            ],
            
            "common_mistakes": [
                {
                    "mistake": "Using field names without square brackets in queries",
                    "correct": "SELECT [Name] FROM [SOXIssue]",
                    "incorrect": "SELECT Name FROM SOXIssue"
                },
                {
                    "mistake": "Using wrong enum value case",
                    "correct": "Status: 'Active'",
                    "incorrect": "Status: 'active'"
                },
                {
                    "mistake": "Trying to set read-only fields",
                    "correct": "Only set editable fields",
                    "incorrect": "Setting 'Created By' or 'Resource ID'"
                }
            ]
        }
    
    @staticmethod
    def get_query_syntax_guide() -> Dict[str, Any]:
        """
        Get comprehensive query syntax documentation
        
        This replaces the extensive inline documentation in the
        execute_openpages_query tool description (500+ tokens).
        
        Returns:
            Dict containing complete query syntax with examples
        """
        return {
            "title": "OpenPages Query Syntax Guide",
            "version": "1.0",
            "description": "Complete guide to OpenPages query language syntax and patterns",
            
            "basic_syntax": {
                "structure": "SELECT [fields] FROM [ObjectType] WHERE [conditions] ORDER BY [fields]",
                "required_rules": [
                    "Enclose all names in square brackets: [ObjectType], [FieldName]",
                    "Field names are case-sensitive",
                    "Use single quotes for string values: 'Active'",
                    "Multiple conditions with AND/OR"
                ]
            },
            
            "select_clause": {
                "description": "Specify which fields to retrieve",
                "examples": [
                    "SELECT [Resource ID], [Name] FROM [SOXIssue]",
                    "SELECT * FROM [SOXRisk]",
                    "SELECT [Name], [Status], [Priority] FROM [SOXControl]"
                ]
            },
            
            "where_clause": {
                "description": "Filter results with conditions",
                "operators": {
                    "=": "Equal to",
                    "<>": "Not equal to",
                    "<": "Less than",
                    ">": "Greater than",
                    "<=": "Less than or equal",
                    ">=": "Greater than or equal",
                    "LIKE": "Pattern matching with % wildcard",
                    "IN": "Match any value in list",
                    "IS NULL": "Field has no value",
                    "IS NOT NULL": "Field has a value"
                },
                "examples": [
                    "WHERE [Status] = 'Active'",
                    "WHERE [Priority] IN ('High', 'Critical')",
                    "WHERE [Name] LIKE '%Security%'",
                    "WHERE [Creation Date] >= '2024-01-01'",
                    "WHERE [Status] = 'Active' AND [Priority] = 'High'"
                ]
            },
            
            "join_clause": {
                "description": "Query related objects using hierarchical relationships",
                "functions": {
                    "PARENT": "Navigate to direct parent (one level up)",
                    "CHILD": "Navigate to direct children (one level down)",
                    "ANCESTOR": "Navigate to any ancestor (multiple levels up)",
                    "DESCENDANT": "Navigate to any descendant (multiple levels down)"
                },
                "syntax": "JOIN [TargetType] ON FUNCTION([SourceType])",
                "critical_rule": "The argument to PARENT/CHILD/ANCESTOR/DESCENDANT must be the FROM type, never the JOIN target",
                "examples": [
                    "FROM [SOXIssue] JOIN [SOXControl] ON PARENT([SOXIssue])",
                    "FROM [SOXRisk] JOIN [SOXControl] ON CHILD([SOXRisk])",
                    "FROM [SOXIssue] JOIN [SOXBusEntity] ON ANCESTOR([SOXIssue])"
                ]
            },
            
            "order_by_clause": {
                "description": "Sort results by one or more fields",
                "syntax": "ORDER BY [Field1] ASC, [Field2] DESC",
                "examples": [
                    "ORDER BY [Name] ASC",
                    "ORDER BY [Creation Date] DESC",
                    "ORDER BY [Priority] DESC, [Name] ASC"
                ]
            },
            
            "limit_clause": {
                "description": "Limit number of results returned",
                "syntax": "LIMIT number",
                "examples": [
                    "LIMIT 10",
                    "LIMIT 100"
                ],
                "note": "Maximum limit is typically 1000 rows"
            },
            
            "common_patterns": [
                {
                    "pattern": "Find all active objects",
                    "query": "SELECT [Resource ID], [Name] FROM [SOXIssue] WHERE [Status] = 'Active'"
                },
                {
                    "pattern": "Find objects created in date range",
                    "query": "SELECT [Name], [Creation Date] FROM [SOXRisk] WHERE [Creation Date] >= '2024-01-01' AND [Creation Date] <= '2024-12-31'"
                },
                {
                    "pattern": "Find objects with specific parent",
                    "query": "SELECT [SOXIssue].[Name], [SOXControl].[Name] FROM [SOXIssue] JOIN [SOXControl] ON PARENT([SOXIssue]) WHERE [SOXControl].[Name] = 'Access Control'"
                },
                {
                    "pattern": "Find high priority items sorted by date",
                    "query": "SELECT [Name], [Priority], [Creation Date] FROM [SOXIssue] WHERE [Priority] = 'High' ORDER BY [Creation Date] DESC LIMIT 20"
                },
                {
                    "pattern": "Search by name pattern",
                    "query": "SELECT [Resource ID], [Name] FROM [SOXControl] WHERE [Name] LIKE '%Security%'"
                }
            ],
            
            "best_practices": [
                "Always use square brackets around field and type names",
                "Use LIMIT to prevent large result sets",
                "For hierarchical queries, read the schema to find correct relationship direction",
                "Test queries with small limits first",
                "Use specific field names instead of SELECT * for better performance"
            ],
            
            "troubleshooting": {
                "no_results": [
                    "Check field name spelling and case",
                    "Verify enum values are exact matches",
                    "Ensure date format is YYYY-MM-DD",
                    "Try broader WHERE conditions"
                ],
                "syntax_error": [
                    "Verify all names are in [square brackets]",
                    "Check for missing quotes around string values",
                    "Ensure JOIN function argument is the FROM type",
                    "Validate operator syntax (=, <>, LIKE, etc.)"
                ]
            }
        }
    
    @staticmethod
    def get_schema_usage_quick_rules() -> Dict[str, str]:
        """
        Get minimal inline usage rules for hybrid mode
        
        This provides 15 tokens of essential guidance inline while
        referencing the full documentation resource.
        
        Returns:
            Dict with minimal quick reference rules
        """
        return {
            "field_names": "Use [brackets]",
            "required": "Check required=true",
            "enums": "Use exact values",
            "read_only": "Cannot set system fields"
        }
    
    @staticmethod
    def format_as_minified_json(content: Dict[str, Any]) -> str:
        """
        Format documentation as minified JSON for AI consumption
        
        Args:
            content: Documentation content dictionary
            
        Returns:
            Minified JSON string (no whitespace)
        """
        return json.dumps(content, separators=(',', ':'))