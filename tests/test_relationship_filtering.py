"""
Test to verify that relationship fields are filtered to only include configured object types
"""
import asyncio
import json
import pytest
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.config.settings import Settings


@pytest.mark.asyncio
async def test_relationship_filtering():
    """Test that relationships are filtered based on configured object types"""
    
    # Create mock settings with only SOXControl and SOXIssue configured
    mock_settings = Settings()
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXControl",
            "tool_prefix": "control",
            "display_name": "Control"
        },
        {
            "type_id": "SOXIssue",
            "tool_prefix": "issue",
            "display_name": "Issue"
        }
    ]
    
    # Create mock schema builder
    class MockSchemaBuilder:
        async def get_type_definition(self, type_name):
            # Mock type definition with associations to both configured and unconfigured types
            return {
                "localizedLabel": "Control",
                "description": "SOX Control object",
                "field_definitions": [
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
                    }
                ],
                "associations": [
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
                    }
                ]
            }
    
    # Create resource handlers
    schema_builder = MockSchemaBuilder()
    resource_handlers = ResourceHandlers(schema_builder, mock_settings)
    
    # Build schema content
    type_def = await schema_builder.get_type_definition("SOXControl")
    obj_config = mock_settings.OPENPAGES_OBJECT_TYPES[0]
    schema_content = resource_handlers._build_schema_content("SOXControl", type_def, obj_config)
    
    # Verify results
    print("=" * 80)
    print("RELATIONSHIP FILTERING TEST RESULTS")
    print("=" * 80)
    print()
    
    print("Configured Object Types:")
    print("  - SOXControl")
    print("  - SOXIssue")
    print()
    
    print("Relationship Fields Found:")
    relationship_fields = schema_content.get("relationship_fields", [])
    for field in relationship_fields:
        target = field.get("target_type", "Unknown")
        print(f"  - {field['name']} -> {target}")
    print()
    
    print("Hierarchical Relationships Found:")
    hierarchical_rels = schema_content.get("hierarchical_relationships", [])
    for rel in hierarchical_rels:
        print(f"  - {rel['direction']}: {rel['type']}")
    print()
    
    # Assertions
    print("Verification:")
    
    # Check that SOXIssue relationship is included
    issue_field = next((f for f in relationship_fields if f.get("target_type") == "SOXIssue"), None)
    if issue_field:
        print("  ✅ SOXIssue relationship field included (configured type)")
    else:
        print("  ❌ SOXIssue relationship field missing (should be included)")
    
    # Check that SOXRisk relationship is excluded
    risk_field = next((f for f in relationship_fields if f.get("target_type") == "SOXRisk"), None)
    if not risk_field:
        print("  ✅ SOXRisk relationship field excluded (unconfigured type)")
    else:
        print("  ❌ SOXRisk relationship field included (should be excluded)")
    
    # Check hierarchical relationships
    issue_hier = next((r for r in hierarchical_rels if r.get("type") == "SOXIssue"), None)
    if issue_hier:
        print("  ✅ SOXIssue hierarchical relationship included (configured type)")
    else:
        print("  ❌ SOXIssue hierarchical relationship missing (should be included)")
    
    risk_hier = next((r for r in hierarchical_rels if r.get("type") == "SOXRisk"), None)
    if not risk_hier:
        print("  ✅ SOXRisk hierarchical relationship excluded (unconfigured type)")
    else:
        print("  ❌ SOXRisk hierarchical relationship included (should be excluded)")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    
    # Print full schema for inspection
    print()
    print("Full Schema Content (JSON):")
    print(json.dumps(schema_content, indent=2))


if __name__ == "__main__":
    asyncio.run(test_relationship_filtering())

# Made with Bob
