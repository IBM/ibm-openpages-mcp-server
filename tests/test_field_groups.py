"""
Test field group support in object_types.json configuration
"""

import pytest
import json
from pathlib import Path


def test_field_group_expansion_logic():
    """Test the field group expansion logic"""
    
    # Simulate field definitions from OpenPages API
    mock_field_definitions = [
        {"name": "OPSS-Ctl:Status", "data_type": "ENUM_TYPE"},
        {"name": "OPSS-Ctl:Type", "data_type": "STRING_TYPE"},
        {"name": "OPSS-Ctl:Frequency", "data_type": "STRING_TYPE"},
        {"name": "OPSS-Ctl:Owner", "data_type": "STRING_TYPE"},
        {"name": "OPSS-Ctl:Domain", "data_type": "STRING_TYPE"},
        {"name": "OPSS-Iss:Status", "data_type": "ENUM_TYPE"},
        {"name": "OPSS-Iss:Priority", "data_type": "STRING_TYPE"},
        {"name": "Other:Field", "data_type": "STRING_TYPE"},
    ]
    
    # Build field groups map (simulating schema_builder logic)
    field_groups_map = {}
    valid_fields_map = {}
    
    for field in mock_field_definitions:
        field_name = field.get("name")
        if field_name:
            valid_fields_map[field_name.lower()] = field
            
            if ':' in field_name:
                group_prefix = field_name.split(':', 1)[0]
                if group_prefix not in field_groups_map:
                    field_groups_map[group_prefix] = []
                field_groups_map[group_prefix].append(field)
    
    # Test 1: Expand a single field group
    configured_fields = ["@OPSS-Ctl"]
    validated_fields = []
    
    for config_field in configured_fields:
        if config_field.startswith('@'):
            group_name = config_field[1:]
            if group_name in field_groups_map:
                group_fields = field_groups_map[group_name]
                for field in group_fields:
                    field_name = field.get("name")
                    if field_name:
                        validated_fields.append(field_name)
    
    assert len(validated_fields) == 5, f"Expected 5 OPSS-Ctl fields, got {len(validated_fields)}"
    assert "OPSS-Ctl:Status" in validated_fields
    assert "OPSS-Ctl:Type" in validated_fields
    assert "OPSS-Ctl:Frequency" in validated_fields
    assert "OPSS-Ctl:Owner" in validated_fields
    assert "OPSS-Ctl:Domain" in validated_fields
    
    # Test 2: Mix field groups and individual fields
    configured_fields = ["@OPSS-Iss", "Other:Field"]
    validated_fields = []
    
    for config_field in configured_fields:
        if config_field.startswith('@'):
            group_name = config_field[1:]
            if group_name in field_groups_map:
                group_fields = field_groups_map[group_name]
                for field in group_fields:
                    field_name = field.get("name")
                    if field_name:
                        validated_fields.append(field_name)
        else:
            if config_field.lower() in valid_fields_map:
                validated_fields.append(config_field)
    
    assert len(validated_fields) == 3, f"Expected 3 fields (2 from OPSS-Iss + 1 individual), got {len(validated_fields)}"
    assert "OPSS-Iss:Status" in validated_fields
    assert "OPSS-Iss:Priority" in validated_fields
    assert "Other:Field" in validated_fields
    
    # Test 3: Invalid field group should be ignored
    configured_fields = ["@NonExistent", "OPSS-Ctl:Status"]
    validated_fields = []
    
    for config_field in configured_fields:
        if config_field.startswith('@'):
            group_name = config_field[1:]
            if group_name in field_groups_map:
                group_fields = field_groups_map[group_name]
                for field in group_fields:
                    field_name = field.get("name")
                    if field_name:
                        validated_fields.append(field_name)
        else:
            if config_field.lower() in valid_fields_map:
                validated_fields.append(config_field)
    
    assert len(validated_fields) == 1, f"Expected 1 field (invalid group ignored), got {len(validated_fields)}"
    assert "OPSS-Ctl:Status" in validated_fields


def test_object_types_json_structure():
    """Test that object_types.json has valid structure with field groups"""
    
    config_path = Path(__file__).parent.parent / "src" / "app" / "config" / "object_types.json"
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Verify structure
    assert "global_settings" in config
    assert "object_types" in config
    
    # Check that at least one object type uses field groups
    found_field_group = False
    
    for obj_type in config["object_types"]:
        resource_fields = obj_type.get("resource_fields", {})
        type_based_query_filters = obj_type.get("type_based_query_filters", {})
        
        # Check resource_fields
        if "fields" in resource_fields:
            for field in resource_fields["fields"]:
                if isinstance(field, str) and field.startswith('@'):
                    found_field_group = True
                    # Verify format
                    assert len(field) > 1, f"Field group '{field}' should have a name after @"
                    assert ':' not in field, f"Field group '{field}' should not contain ':' (that's for individual fields)"
        
        # Check type_based_query_filters
        if "fields" in type_based_query_filters:
            for field in type_based_query_filters["fields"]:
                if isinstance(field, str) and field.startswith('@'):
                    found_field_group = True
                    assert len(field) > 1, f"Field group '{field}' should have a name after @"
                    assert ':' not in field, f"Field group '{field}' should not contain ':' (that's for individual fields)"
    
    assert found_field_group, "At least one object type should demonstrate field group usage with @ prefix"


def test_field_group_naming_convention():
    """Test that field group references follow the correct naming convention"""
    
    # Valid field group references
    valid_groups = ["@OPSS-Ctl", "@OPSS-Iss", "@OPSS-Rsk", "@MyGroup"]
    
    for group in valid_groups:
        assert group.startswith('@'), f"Field group '{group}' should start with @"
        assert len(group) > 1, f"Field group '{group}' should have a name after @"
        assert ':' not in group, f"Field group '{group}' should not contain ':'"
    
    # Invalid field group references (these should be treated as individual fields)
    invalid_groups = ["OPSS-Ctl:Status", "OPSS-Iss:Priority", "SomeField"]
    
    for field in invalid_groups:
        assert not field.startswith('@'), f"Individual field '{field}' should not start with @"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
