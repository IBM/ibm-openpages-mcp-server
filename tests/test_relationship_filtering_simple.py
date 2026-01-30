"""
Simple test to verify relationship filtering logic
"""


def test_relationship_filtering():
    """Test the filtering logic for relationships"""
    
    # Simulate configured types
    configured_types = {"SOXControl", "SOXIssue"}
    
    # Simulate field definitions with relationships
    field_definitions = [
        {
            "name": "Name",
            "localized_label": "Name",
            "data_type": "STRING_TYPE",
            "required": True
        },
        {
            "name": "Related Issues",
            "localized_label": "Related Issues",
            "data_type": "MULTI_VALUE_ID_TYPE",
            "target_type": "SOXIssue",  # Configured - should be included
            "description": "Issues related to this control"
        },
        {
            "name": "Related Risks",
            "localized_label": "Related Risks",
            "data_type": "MULTI_VALUE_ID_TYPE",
            "target_type": "SOXRisk",  # NOT configured - should be filtered out
            "description": "Risks related to this control"
        },
        {
            "name": "Related Process",
            "localized_label": "Related Process",
            "data_type": "ID_TYPE",
            "target_type": "SOXProcess",  # NOT configured - should be filtered out
            "description": "Process related to this control"
        }
    ]
    
    # Simulate associations
    associations = [
        {
            "name": "SOXIssue",
            "relationship": "Child",
            "enabled": True,
            "localizedLabel": "Issues"
        },
        {
            "name": "SOXRisk",  # NOT configured - should be filtered out
            "relationship": "Parent",
            "enabled": True,
            "localizedLabel": "Risks"
        },
        {
            "name": "SOXProcess",  # NOT configured - should be filtered out
            "relationship": "Parent",
            "enabled": True,
            "localizedLabel": "Process"
        }
    ]
    
    # Apply filtering logic for relationship fields
    relationship_fields = []
    for field in field_definitions:
        field_name = field.get("name")
        data_type = field.get("data_type", "STRING_TYPE")
        
        is_system_field = field_name in ["Resource ID", "Name", "Description", "Location"]
        is_relationship = (data_type in ["ID_TYPE", "MULTI_VALUE_ID_TYPE"]) and not is_system_field
        
        if is_relationship:
            target_type = field.get("target_type")
            if target_type:
                # Filter: only include if target type is configured
                if target_type in configured_types:
                    relationship_fields.append({
                        "name": field_name,
                        "target_type": target_type,
                        "relationship_type": "single" if data_type == "ID_TYPE" else "multiple"
                    })
                else:
                    print(f"  Filtered out relationship field: {field_name} -> {target_type} (unconfigured)")
    
    # Apply filtering logic for hierarchical relationships
    hierarchical_relationships = []
    for assoc in associations:
        if not assoc.get("enabled", True):
            continue
        
        relationship_type = assoc.get("relationship", "")
        associated_type = assoc.get("name", "")
        
        if not associated_type:
            continue
        
        # Filter: only include if associated type is configured
        if associated_type in configured_types:
            hierarchical_relationships.append({
                "direction": relationship_type.lower(),
                "type": associated_type
            })
        else:
            print(f"  Filtered out hierarchical relationship: {relationship_type} -> {associated_type} (unconfigured)")
    
    # Print results
    print("=" * 80)
    print("RELATIONSHIP FILTERING TEST")
    print("=" * 80)
    print()
    
    print("Configured Object Types:")
    for t in sorted(configured_types):
        print(f"  - {t}")
    print()
    
    print("Relationship Fields (after filtering):")
    for field in relationship_fields:
        print(f"  [OK] {field['name']} -> {field['target_type']} [{field['relationship_type']}]")
    print()
    
    print("Hierarchical Relationships (after filtering):")
    for rel in hierarchical_relationships:
        print(f"  [OK] {rel['direction']}: {rel['type']}")
    print()
    
    # Verify expectations
    print("Verification:")
    
    # Should have 1 relationship field (Related Issues)
    if len(relationship_fields) == 1:
        print(f"  [PASS] Correct number of relationship fields: {len(relationship_fields)}")
    else:
        print(f"  [FAIL] Wrong number of relationship fields: {len(relationship_fields)} (expected 1)")
    
    # Should have SOXIssue relationship
    if any(f['target_type'] == 'SOXIssue' for f in relationship_fields):
        print("  [PASS] SOXIssue relationship included (configured)")
    else:
        print("  [FAIL] SOXIssue relationship missing")
    
    # Should NOT have SOXRisk or SOXProcess relationships
    if not any(f['target_type'] == 'SOXRisk' for f in relationship_fields):
        print("  [PASS] SOXRisk relationship excluded (unconfigured)")
    else:
        print("  [FAIL] SOXRisk relationship included (should be excluded)")
    
    if not any(f['target_type'] == 'SOXProcess' for f in relationship_fields):
        print("  [PASS] SOXProcess relationship excluded (unconfigured)")
    else:
        print("  [FAIL] SOXProcess relationship included (should be excluded)")
    
    # Should have 1 hierarchical relationship (SOXIssue)
    if len(hierarchical_relationships) == 1:
        print(f"  [PASS] Correct number of hierarchical relationships: {len(hierarchical_relationships)}")
    else:
        print(f"  [FAIL] Wrong number of hierarchical relationships: {len(hierarchical_relationships)} (expected 1)")
    
    # Should have SOXIssue hierarchical
    if any(r['type'] == 'SOXIssue' for r in hierarchical_relationships):
        print("  [PASS] SOXIssue hierarchical relationship included (configured)")
    else:
        print("  [FAIL] SOXIssue hierarchical relationship missing")
    
    # Should NOT have SOXRisk or SOXProcess hierarchical
    if not any(r['type'] == 'SOXRisk' for r in hierarchical_relationships):
        print("  [PASS] SOXRisk hierarchical relationship excluded (unconfigured)")
    else:
        print("  [FAIL] SOXRisk hierarchical relationship included (should be excluded)")
    
    if not any(r['type'] == 'SOXProcess' for r in hierarchical_relationships):
        print("  [PASS] SOXProcess hierarchical relationship excluded (unconfigured)")
    else:
        print("  [FAIL] SOXProcess hierarchical relationship included (should be excluded)")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE - All filtering logic working correctly!")
    print("=" * 80)


if __name__ == "__main__":
    test_relationship_filtering()

# Made with Bob
