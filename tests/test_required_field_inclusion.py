"""
Test to verify that required fields are ALWAYS included, even when not configured
"""


def test_required_field_always_included():
    """Test that required fields are included even when not in configuration"""
    
    # Simulate field definitions from OpenPages
    field_definitions = [
        {"name": "Resource ID", "data_type": "STRING_TYPE", "required": False},
        {"name": "Name", "data_type": "STRING_TYPE", "required": True},
        {"name": "Description", "data_type": "STRING_TYPE", "required": False},
        {"name": "OPSS-Iss:Status", "data_type": "ENUM_TYPE", "required": True},  # Required but NOT in config
        {"name": "OPSS-Iss:Priority", "data_type": "ENUM_TYPE", "required": False},
        {"name": "OPSS-Iss:Severity", "data_type": "ENUM_TYPE", "required": False},
        {"name": "OPSS-Iss:Owner", "data_type": "STRING_TYPE", "required": False},
        {"name": "OPSS-Iss:DueDate", "data_type": "DATE_TYPE", "required": False},
        {"name": "OPSS-Iss:MandatoryField", "data_type": "STRING_TYPE", "required": True},  # Required but NOT in config
    ]
    
    # Configuration: include_all_fields = False, and required fields NOT in the list
    config = {
        "include_all_fields": False,
        "fields": [
            "OPSS-Iss:Priority",  # Only this field is configured
            "OPSS-Iss:Severity"   # And this one
            # Note: OPSS-Iss:Status and OPSS-Iss:MandatoryField are NOT listed but are required
        ]
    }
    
    filtered_fields = filter_fields(field_definitions, config)
    
    print("=" * 80)
    print("TEST: Required Fields Always Included (Even When Not Configured)")
    print("=" * 80)
    print()
    print(f"Configuration: include_all_fields=False")
    print(f"Configured fields: {config['fields']}")
    print(f"Required fields NOT in config: OPSS-Iss:Status, OPSS-Iss:MandatoryField")
    print()
    print(f"Result: {len(filtered_fields)} fields included")
    for f in filtered_fields:
        # Find the field definition to check if it's required
        field_def = next((fd for fd in field_definitions if fd["name"] == f), None)
        is_required = field_def.get("required", False) if field_def else False
        is_system = f in ["Resource ID", "Name", "Description"]
        is_configured = f in config["fields"]
        
        marker = "[SYSTEM]" if is_system else \
                 "[REQUIRED]" if is_required else \
                 "[CONFIGURED]" if is_configured else "[OTHER]"
        print(f"  {marker} {f}")
    print()
    
    # Verification
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    # Check that required fields are included even though not configured
    if "OPSS-Iss:Status" in filtered_fields:
        print("[PASS] OPSS-Iss:Status included (required but not configured)")
    else:
        print("[FAIL] OPSS-Iss:Status missing (should be included as required)")
    
    if "OPSS-Iss:MandatoryField" in filtered_fields:
        print("[PASS] OPSS-Iss:MandatoryField included (required but not configured)")
    else:
        print("[FAIL] OPSS-Iss:MandatoryField missing (should be included as required)")
    
    # Check that configured fields are included
    if "OPSS-Iss:Priority" in filtered_fields:
        print("[PASS] OPSS-Iss:Priority included (configured)")
    else:
        print("[FAIL] OPSS-Iss:Priority missing")
    
    if "OPSS-Iss:Severity" in filtered_fields:
        print("[PASS] OPSS-Iss:Severity included (configured)")
    else:
        print("[FAIL] OPSS-Iss:Severity missing")
    
    # Check that unconfigured, non-required fields are excluded
    if "OPSS-Iss:DueDate" not in filtered_fields:
        print("[PASS] OPSS-Iss:DueDate excluded (not required, not configured)")
    else:
        print("[FAIL] OPSS-Iss:DueDate should be excluded")
    
    if "OPSS-Iss:Owner" not in filtered_fields:
        print("[PASS] OPSS-Iss:Owner excluded (not required, not configured)")
    else:
        print("[FAIL] OPSS-Iss:Owner should be excluded")
    
    # Expected fields: 3 system + 2 required (not configured) + 2 configured = 7 total
    expected_count = 7
    if len(filtered_fields) == expected_count:
        print(f"[PASS] Correct field count: {len(filtered_fields)} (expected {expected_count})")
    else:
        print(f"[FAIL] Wrong field count: {len(filtered_fields)} (expected {expected_count})")
    
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
            # Always include required fields (EVEN IF NOT CONFIGURED)
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
    test_required_field_always_included()

# Made with Bob
