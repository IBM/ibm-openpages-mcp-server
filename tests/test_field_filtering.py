"""
Test to verify that fields are filtered based on configuration
"""


def test_field_filtering():
    """Test that fields are filtered based on resource_fields configuration"""
    
    # Simulate field definitions from OpenPages
    field_definitions = [
        {"name": "Resource ID", "data_type": "STRING_TYPE", "required": False},
        {"name": "Name", "data_type": "STRING_TYPE", "required": True},
        {"name": "Description", "data_type": "STRING_TYPE", "required": False},
        {"name": "OPSS-Iss:Status", "data_type": "ENUM_TYPE", "required": True},
        {"name": "OPSS-Iss:Priority", "data_type": "ENUM_TYPE", "required": False},
        {"name": "OPSS-Iss:Severity", "data_type": "ENUM_TYPE", "required": False},
        {"name": "OPSS-Iss:Owner", "data_type": "STRING_TYPE", "required": False},
        {"name": "OPSS-Iss:DueDate", "data_type": "DATE_TYPE", "required": False},
        {"name": "OPSS-Iss:Category", "data_type": "STRING_TYPE", "required": False},
    ]
    
    # Test Case 1: include_all_fields = True
    print("=" * 80)
    print("TEST CASE 1: include_all_fields = True")
    print("=" * 80)
    
    config1 = {
        "include_all_fields": True,
        "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
    }
    
    filtered_fields1 = filter_fields(field_definitions, config1)
    print(f"Configuration: include_all_fields=True")
    print(f"Configured fields: {config1['fields']}")
    print(f"Result: {len(filtered_fields1)} fields included")
    for f in filtered_fields1:
        print(f"  - {f}")
    print()
    
    # Test Case 2: include_all_fields = False with specific fields
    print("=" * 80)
    print("TEST CASE 2: include_all_fields = False with specific fields")
    print("=" * 80)
    
    config2 = {
        "include_all_fields": False,
        "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority", "OPSS-Iss:Severity", "OPSS-Iss:Owner"]
    }
    
    filtered_fields2 = filter_fields(field_definitions, config2)
    print(f"Configuration: include_all_fields=False")
    print(f"Configured fields: {config2['fields']}")
    print(f"Result: {len(filtered_fields2)} fields included")
    for f in filtered_fields2:
        marker = "[SYSTEM]" if f in ["Resource ID", "Name", "Description"] else \
                 "[REQUIRED]" if f == "OPSS-Iss:Status" else "[CONFIGURED]"
        print(f"  {marker} {f}")
    print()
    
    # Verification
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    # Case 1: Should include all fields
    if len(filtered_fields1) == len(field_definitions):
        print("[PASS] Case 1: All fields included when include_all_fields=True")
    else:
        print(f"[FAIL] Case 1: Expected {len(field_definitions)} fields, got {len(filtered_fields1)}")
    
    # Case 2: Should include system fields + required fields + configured fields
    expected_fields_2 = [
        "Resource ID",  # System field
        "Name",  # System field + Required
        "Description",  # System field
        "OPSS-Iss:Status",  # Required field
        "OPSS-Iss:Priority",  # Configured field
        "OPSS-Iss:Severity",  # Configured field
        "OPSS-Iss:Owner"  # Configured field
    ]
    
    if set(filtered_fields2) == set(expected_fields_2):
        print(f"[PASS] Case 2: Correct fields included ({len(expected_fields_2)} fields)")
    else:
        print(f"[FAIL] Case 2: Field mismatch")
        print(f"  Expected: {sorted(expected_fields_2)}")
        print(f"  Got: {sorted(filtered_fields2)}")
    
    # Should NOT include unconfigured fields
    unconfigured_fields = ["OPSS-Iss:DueDate", "OPSS-Iss:Category"]
    if not any(f in filtered_fields2 for f in unconfigured_fields):
        print(f"[PASS] Case 2: Unconfigured fields excluded: {unconfigured_fields}")
    else:
        print(f"[FAIL] Case 2: Unconfigured fields should be excluded")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


def filter_fields(field_definitions, config):
    """
    Simulate the field filtering logic from resource_handlers.py
    """
    include_all_fields = config.get("include_all_fields", True)
    configured_field_names = config.get("fields", [])
    
    # System fields that are always included
    system_fields = ["Resource ID", "Name", "Description", "Title", "Location",
                    "Created By", "Creation Date", "Last Modified By", "Last Modification Date"]
    
    # Build a set of configured field names (case-insensitive) for quick lookup
    configured_field_names_lower = {f.lower() for f in configured_field_names}
    
    filtered_fields = []
    
    for field in field_definitions:
        field_name = field.get("name")
        if not field_name:
            continue
        
        # Check if field should be included based on configuration
        is_system_field = field_name in system_fields
        is_required_field = field.get("required", False)
        is_configured_field = field_name.lower() in configured_field_names_lower
        
        # Determine if this field should be included in the schema
        should_include = False
        if is_system_field:
            # Always include system fields
            should_include = True
        elif is_required_field:
            # Always include required fields
            should_include = True
        elif include_all_fields:
            # Include all fields if configured to do so
            should_include = True
        elif is_configured_field:
            # Include if explicitly configured
            should_include = True
        
        # Skip fields that shouldn't be included
        if not should_include:
            print(f"  [FILTERED] Skipping unconfigured field: {field_name}")
            continue
        
        filtered_fields.append(field_name)
    
    return filtered_fields


if __name__ == "__main__":
    test_field_filtering()

# Made with Bob
