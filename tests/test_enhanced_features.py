"""
Test enhanced features: currency handling, friendly names, associations, and multi-value enums

This test suite covers the new features added in the remote_server_base branch:
1. Currency field handling with validation
2. Friendly name conflict resolution in schemas
3. Association validation against schema
4. Multi-value enum handling
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.tools.base_tool import BaseTool
from src.app.tools.generic_object_tools import GenericObjectTools
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.core.openpages_client import OpenPagesClient


# ============================================================================
# Currency Field Handling Tests
# ============================================================================

class TestCurrencyFieldHandling:
    """Test currency field conversion and validation"""
    
    @pytest_asyncio.fixture
    async def base_tool(self):
        """Create a BaseTool instance with mocked client"""
        mock_client = AsyncMock(spec=OpenPagesClient)
        return BaseTool(mock_client)
    
    @pytest.mark.asyncio
    async def test_currency_simple_numeric(self, base_tool):
        """Test simple numeric value converts to currency object"""
        result = await base_tool.format_field_value(100.50, "CURRENCY_TYPE")
        
        assert result == {
            "local_amount": 100.50,
            "local_currency": {"iso_code": "USD"}
        }
    
    @pytest.mark.asyncio
    async def test_currency_with_amount_and_currency(self, base_tool):
        """Test currency object with amount and currency"""
        field_value = {
            "amount": 250.75,
            "currency": "EUR"
        }
        result = await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert result == {
            "local_amount": 250.75,
            "local_currency": {"iso_code": "EUR"}
        }
    
    @pytest.mark.asyncio
    async def test_currency_with_nested_currency_object(self, base_tool):
        """Test currency with nested currency object"""
        field_value = {
            "amount": 1000.00,
            "currency": {"iso_code": "GBP"}
        }
        result = await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert result == {
            "local_amount": 1000.00,
            "local_currency": {"iso_code": "GBP"}
        }
    
    @pytest.mark.asyncio
    async def test_currency_already_in_correct_format(self, base_tool):
        """Test currency already in OpenPages format"""
        field_value = {
            "local_amount": 500.00,
            "local_currency": {"iso_code": "INR"}
        }
        result = await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert result == field_value
    
    @pytest.mark.asyncio
    async def test_currency_missing_amount_raises_error(self, base_tool):
        """Test that missing amount raises ValueError"""
        field_value = {"currency": "USD"}
        
        with pytest.raises(ValueError) as exc_info:
            await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert "must have 'amount'" in str(exc_info.value)
        assert "Valid formats" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_currency_invalid_amount_raises_error(self, base_tool):
        """Test that non-numeric amount raises ValueError"""
        field_value = {"amount": "not-a-number", "currency": "USD"}
        
        with pytest.raises(ValueError) as exc_info:
            await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert "must be numeric" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_currency_invalid_code_length_raises_error(self, base_tool):
        """Test that invalid currency code length raises ValueError"""
        field_value = {"amount": 100, "currency": "US"}  # Only 2 chars
        
        with pytest.raises(ValueError) as exc_info:
            await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert "3-letter ISO 4217 code" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_currency_nested_missing_iso_code_raises_error(self, base_tool):
        """Test that nested currency without iso_code raises ValueError"""
        field_value = {
            "amount": 100,
            "currency": {"name": "US Dollar"}  # Missing iso_code
        }
        
        with pytest.raises(ValueError) as exc_info:
            await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert "must have 'iso_code'" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_currency_invalid_simple_value_raises_error(self, base_tool):
        """Test that invalid simple value raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            await base_tool.format_field_value("not-a-number", "CURRENCY_TYPE")
        
        assert "must be numeric or a currency object" in str(exc_info.value)
        assert "Valid formats" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_currency_code_case_normalization(self, base_tool):
        """Test that currency codes are normalized to uppercase"""
        field_value = {"amount": 100, "currency": "usd"}
        result = await base_tool.format_field_value(field_value, "CURRENCY_TYPE")
        
        assert result["local_currency"]["iso_code"] == "USD"


# ============================================================================
# Multi-Value Enum Handling Tests
# ============================================================================

class TestMultiValueEnumHandling:
    """Test multi-value enum field conversion"""
    
    @pytest_asyncio.fixture
    async def base_tool(self):
        """Create a BaseTool instance with mocked client"""
        mock_client = AsyncMock(spec=OpenPagesClient)
        return BaseTool(mock_client)
    
    @pytest.mark.asyncio
    async def test_multi_value_enum_from_list_of_strings(self, base_tool):
        """Test converting list of strings to enum objects"""
        field_value = ["Active", "Pending", "Closed"]
        result = await base_tool.format_field_value(field_value, "MULTI_VALUE_ENUM")
        
        expected = [
            {"name": "Active"},
            {"name": "Pending"},
            {"name": "Closed"}
        ]
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_multi_value_enum_from_single_string(self, base_tool):
        """Test converting single string to enum object list"""
        field_value = "Active"
        result = await base_tool.format_field_value(field_value, "MULTI_VALUE_ENUM")
        
        assert result == [{"name": "Active"}]
    
    @pytest.mark.asyncio
    async def test_multi_value_enum_already_in_correct_format(self, base_tool):
        """Test enum values already in correct format"""
        field_value = [
            {"name": "Active"},
            {"name": "Pending"}
        ]
        result = await base_tool.format_field_value(field_value, "MULTI_VALUE_ENUM")
        
        assert result == field_value
    
    @pytest.mark.asyncio
    async def test_multi_value_enum_mixed_format(self, base_tool):
        """Test mixed format (some strings, some objects)"""
        field_value = [
            "Active",
            {"name": "Pending"},
            "Closed"
        ]
        result = await base_tool.format_field_value(field_value, "MULTI_VALUE_ENUM")
        
        expected = [
            {"name": "Active"},
            {"name": "Pending"},
            {"name": "Closed"}
        ]
        assert result == expected


# ============================================================================
# Friendly Name Conflict Resolution Tests
# ============================================================================

class TestFriendlyNameConflictResolution:
    """Test friendly name handling in schema builder"""
    
    @pytest_asyncio.fixture
    async def schema_builder(self):
        """Create a SchemaBuilder instance with mocked client"""
        mock_client = AsyncMock(spec=OpenPagesClient)
        
        # Mock type definition with conflicting labels
        mock_type_def = {
            "id": "TestType",
            "name": "TestType",
            "field_definitions": [
                {
                    "name": "OPSS-Test:Status",
                    "localized_label": "Status",
                    "data_type": "STRING_TYPE",
                    "required": False
                },
                {
                    "name": "OPSS-Test:StatusCode",
                    "localized_label": "Status",  # Duplicate label!
                    "data_type": "STRING_TYPE",
                    "required": False
                },
                {
                    "name": "OPSS-Test:Owner",
                    "localized_label": "Owner",  # Unique label
                    "data_type": "STRING_TYPE",
                    "required": False
                }
            ]
        }
        
        mock_client.get_type_definition = AsyncMock(return_value=mock_type_def)
        mock_client.get_type_associations = AsyncMock(return_value=[])
        
        return SchemaBuilder(mock_client)
    
    @pytest.mark.asyncio
    async def test_unique_label_uses_friendly_name(self, schema_builder):
        """Test that unique labels use friendly names"""
        schema = await schema_builder.build_dynamic_schema_for_object(
            object_type="TestType",
            object_label="test"
        )
        
        # Owner has unique label, should use friendly name
        assert "Owner" in schema["properties"]
        assert schema["properties"]["Owner"]["x-technical-name"] == "OPSS-Test:Owner"
        assert schema["properties"]["Owner"]["x-label"] == "Owner"
    
    @pytest.mark.asyncio
    async def test_conflicting_labels_use_technical_names(self, schema_builder):
        """Test that conflicting labels fall back to technical names"""
        schema = await schema_builder.build_dynamic_schema_for_object(
            object_type="TestType",
            object_label="test"
        )
        
        # Status has conflicting labels, should use technical names
        assert "OPSS-Test:Status" in schema["properties"]
        assert "OPSS-Test:StatusCode" in schema["properties"]
        
        # Both should have x-technical-name
        assert schema["properties"]["OPSS-Test:Status"]["x-technical-name"] == "OPSS-Test:Status"
        assert schema["properties"]["OPSS-Test:StatusCode"]["x-technical-name"] == "OPSS-Test:StatusCode"
    
    @pytest.mark.asyncio
    async def test_technical_name_in_description(self, schema_builder):
        """Test that technical name is included in description when using friendly name"""
        schema = await schema_builder.build_dynamic_schema_for_object(
            object_type="TestType",
            object_label="test"
        )
        
        # Owner uses friendly name, should have technical name in description
        owner_desc = schema["properties"]["Owner"]["description"]
        assert "OPSS-Test:Owner" in owner_desc


# ============================================================================
# Association Validation Tests
# ============================================================================

class TestAssociationValidation:
    """Test association validation against schema"""
    
    @pytest_asyncio.fixture
    async def generic_tools(self):
        """Create GenericObjectTools with mocked client and schema"""
        mock_client = AsyncMock(spec=OpenPagesClient)
        
        # Mock type definition with associations
        mock_type_def = {
            "id": "SOXIssue",
            "name": "SOXIssue",
            "field_definitions": [],
            "associations": [
                {
                    "name": "SOXControl",
                    "relationship": "Parent",
                    "localizedLabel": "Controls",
                    "enabled": True
                },
                {
                    "name": "SOXRisk",
                    "relationship": "Child",
                    "localizedLabel": "Risks",
                    "enabled": True
                },
                {
                    "name": "SOXBusEntity",
                    "relationship": "Sibling",  # Not supported by REST API
                    "localizedLabel": "Business Entities",
                    "enabled": True
                }
            ]
        }
        
        mock_client.get_type_definition = AsyncMock(return_value=mock_type_def)
        mock_client.get_type_associations = AsyncMock(return_value=mock_type_def["associations"])
        mock_client.add_associations = AsyncMock()
        mock_client.remove_associations = AsyncMock()
        
        # Mock schema builder
        mock_schema_builder = MagicMock()
        mock_schema_builder.get_type_definition = AsyncMock(return_value=mock_type_def)
        
        object_config = {
            "type_id": "SOXIssue",
            "display_name": "Issue",
            "path_prefix": "Issues"
        }
        
        return GenericObjectTools(mock_client, object_config, mock_schema_builder)
    
    @pytest.mark.asyncio
    async def test_valid_parent_association(self, generic_tools):
        """Test that valid Parent association is accepted"""
        arguments = {
            "resource_id": "12345",
            "associations": [
                {
                    "relationship_type": "Parent",
                    "target_id": "67890",
                    "target_type": "SOXControl"
                }
            ]
        }
        
        result = await generic_tools.associate_objects(arguments)
        
        # Should succeed without error
        assert generic_tools.client.add_associations.called
        assert "Successfully added" in result[0].text
    
    @pytest.mark.asyncio
    async def test_valid_child_association(self, generic_tools):
        """Test that valid Child association is accepted"""
        arguments = {
            "resource_id": "12345",
            "associations": [
                {
                    "relationship_type": "Child",
                    "target_id": "67890",
                    "target_type": "SOXRisk"
                }
            ]
        }
        
        result = await generic_tools.associate_objects(arguments)
        
        # Should succeed without error
        assert generic_tools.client.add_associations.called
        assert "Successfully added" in result[0].text
    
    @pytest.mark.asyncio
    async def test_invalid_association_type_rejected(self, generic_tools):
        """Test that invalid association type is rejected"""
        arguments = {
            "resource_id": "12345",
            "associations": [
                {
                    "relationship_type": "Parent",
                    "target_id": "67890",
                    "target_type": "SOXRisk"  # Invalid: SOXRisk is Child, not Parent
                }
            ]
        }
        
        result = await generic_tools.associate_objects(arguments)
        
        # Should fail with validation error
        assert "not valid" in result[0].text
        assert "Available associations" in result[0].text
        assert not generic_tools.client.add_associations.called
    
    @pytest.mark.asyncio
    async def test_sibling_relationship_rejected(self, generic_tools):
        """Test that Sibling relationship is rejected (REST API limitation)"""
        arguments = {
            "resource_id": "12345",
            "associations": [
                {
                    "relationship_type": "Sibling",
                    "target_id": "67890"
                }
            ]
        }
        
        result = await generic_tools.associate_objects(arguments)
        
        # Should fail - only Parent and Child are supported
        assert "Only 'Parent' and 'Child'" in result[0].text
        assert not generic_tools.client.add_associations.called
    
    @pytest.mark.asyncio
    async def test_peer_relationship_rejected(self, generic_tools):
        """Test that Peer relationship is rejected (REST API limitation)"""
        arguments = {
            "resource_id": "12345",
            "associations": [
                {
                    "relationship_type": "Peer",
                    "target_id": "67890"
                }
            ]
        }
        
        result = await generic_tools.associate_objects(arguments)
        
        # Should fail - only Parent and Child are supported
        assert "Only 'Parent' and 'Child'" in result[0].text
        assert not generic_tools.client.add_associations.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])