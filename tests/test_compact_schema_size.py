"""Simple test to demonstrate compact vs full schema size difference."""
import json

# Sample full schema (typical Issue schema with all fields)
full_schema = {
    "type_id": "SOXIssue",
    "type_name": "Issue",
    "label": "Issue",
    "description": "Represents an issue in OpenPages",
    "fields": {
        "Resource ID": {
            "name": "Resource ID",
            "type": "ID_TYPE",
            "data_type": "STRING_TYPE",
            "required": True,
            "system_field": True
        },
        "Name": {
            "name": "Name",
            "type": "STRING_TYPE",
            "data_type": "STRING_TYPE",
            "required": True,
            "system_field": True
        },
        "Description": {
            "name": "Description",
            "type": "LARGE_STRING_TYPE",
            "data_type": "STRING_TYPE",
            "required": False,
            "system_field": True
        },
        "Status": {
            "name": "Status",
            "type": "ENUM_TYPE",
            "data_type": "STRING_TYPE",
            "required": True,
            "system_field": False,
            "enum_values": [
                {"value": "Draft", "label": "Draft"},
                {"value": "Active", "label": "Active"},
                {"value": "Closed", "label": "Closed"},
                {"value": "Cancelled", "label": "Cancelled"}
            ]
        },
        "Priority": {
            "name": "Priority",
            "type": "ENUM_TYPE",
            "data_type": "STRING_TYPE",
            "required": False,
            "system_field": False,
            "enum_values": [
                {"value": "Critical", "label": "Critical"},
                {"value": "High", "label": "High"},
                {"value": "Medium", "label": "Medium"},
                {"value": "Low", "label": "Low"}
            ]
        },
        "Severity": {
            "name": "Severity",
            "type": "ENUM_TYPE",
            "data_type": "STRING_TYPE",
            "required": False,
            "system_field": False,
            "enum_values": [
                {"value": "Critical", "label": "Critical"},
                {"value": "Major", "label": "Major"},
                {"value": "Minor", "label": "Minor"}
            ]
        },
        "Owner": {
            "name": "Owner",
            "type": "USER_TYPE",
            "data_type": "STRING_TYPE",
            "required": False,
            "system_field": False
        },
        "Due Date": {
            "name": "Due Date",
            "type": "DATE_TYPE",
            "data_type": "DATE_TYPE",
            "required": False,
            "system_field": False
        },
        # Add 20 more optional fields to simulate real schema
        **{f"Custom Field {i}": {
            "name": f"Custom Field {i}",
            "type": "STRING_TYPE",
            "data_type": "STRING_TYPE",
            "required": False,
            "system_field": False
        } for i in range(1, 21)}
    },
    "hierarchical_relationships": [
        {
            "direction": "parent",
            "type": "SOXControl",
            "label": "Controls",
            "join_syntax": "FROM [SOXIssue] JOIN [SOXControl] ON CHILD([SOXIssue])"
        }
    ]
}

# Compact schema (only required and system fields, no enum values)
compact_schema = {
    "type_id": "SOXIssue",
    "type_name": "Issue",
    "label": "Issue",
    "description": "Represents an issue in OpenPages",
    "mode": "compact",
    "note": "This is a compact schema with only required/system fields. Use mode='full' to get all fields with enum values.",
    "fields": {
        "Resource ID": {
            "name": "Resource ID",
            "type": "ID_TYPE",
            "data_type": "STRING_TYPE",
            "required": True,
            "system_field": True
        },
        "Name": {
            "name": "Name",
            "type": "STRING_TYPE",
            "data_type": "STRING_TYPE",
            "required": True,
            "system_field": True
        },
        "Description": {
            "name": "Description",
            "type": "LARGE_STRING_TYPE",
            "data_type": "STRING_TYPE",
            "required": False,
            "system_field": True
        },
        "Status": {
            "name": "Status",
            "type": "ENUM_TYPE",
            "data_type": "STRING_TYPE",
            "required": True,
            "system_field": False,
            "note": "Enum values omitted in compact mode"
        }
    },
    "hierarchical_relationships": [
        {
            "direction": "parent",
            "type": "SOXControl",
            "label": "Controls",
            "join_syntax": "FROM [SOXIssue] JOIN [SOXControl] ON CHILD([SOXIssue])"
        }
    ]
}

def analyze_schemas():
    """Compare full vs compact schema sizes."""
    
    full_json = json.dumps(full_schema, indent=2)
    compact_json = json.dumps(compact_schema, indent=2)
    
    full_size = len(full_json)
    compact_size = len(compact_json)
    
    full_lines = full_json.count('\n')
    compact_lines = compact_json.count('\n')
    
    full_fields = len(full_schema["fields"])
    compact_fields = len(compact_schema["fields"])
    
    print("=" * 80)
    print("SCHEMA SIZE COMPARISON")
    print("=" * 80)
    
    print("\n[FULL SCHEMA]")
    print(f"   Size:   {full_size:,} bytes")
    print(f"   Lines:  {full_lines:,}")
    print(f"   Fields: {full_fields}")
    
    print("\n[COMPACT SCHEMA]")
    print(f"   Size:   {compact_size:,} bytes")
    print(f"   Lines:  {compact_lines:,}")
    print(f"   Fields: {compact_fields}")
    
    size_reduction = ((full_size - compact_size) / full_size) * 100
    line_reduction = ((full_lines - compact_lines) / full_lines) * 100
    field_reduction = ((full_fields - compact_fields) / full_fields) * 100
    
    print("\n" + "=" * 80)
    print("REDUCTION ACHIEVED")
    print("=" * 80)
    print(f"\n[+] Size Reduction:  {size_reduction:.1f}%")
    print(f"[+] Line Reduction:  {line_reduction:.1f}%")
    print(f"[+] Field Reduction: {field_reduction:.1f}%")
    
    print("\n" + "=" * 80)
    print("COMPACT SCHEMA SAMPLE")
    print("=" * 80)
    print(compact_json)
    
    print("\n" + "=" * 80)
    print("BENEFITS")
    print("=" * 80)
    print("""
[+] Faster initial exploration - AI agents get essential info quickly
[+] Reduced token usage - smaller payloads mean lower costs
[+] Better performance - less data to parse and process
[+] Focused context - only required/system fields shown initially
[+] On-demand details - can request full schema when enum values needed

[!] USAGE:
   - Use mode='compact' for initial schema exploration
   - Use mode='full' only when you need enum values or all optional fields
   - Compact mode is ideal for query construction (just need field names/types)
   - Full mode is better for form generation (need enum values for dropdowns)
""")

if __name__ == "__main__":
    analyze_schemas()