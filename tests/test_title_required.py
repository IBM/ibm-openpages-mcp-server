"""
Test to verify that title is marked as required when the object type requires it
"""
import asyncio
import logging
import pytest
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.core.openpages_client import OpenPagesClient
from src.app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.skip(reason="Integration test requires live OpenPages connection")
@pytest.mark.asyncio
async def test_title_required():
    """Test that title is marked as required in schema when object type requires it"""
    
    # Initialize client and schema builder
    client = OpenPagesClient(
        base_url=settings.OPENPAGES_BASE_URL,
        auth_type=getattr(settings, 'OPENPAGES_AUTH_TYPE', 'basic'),
        username=settings.OPENPAGES_USERNAME,
        password=settings.OPENPAGES_PASSWORD,
        api_key=getattr(settings, 'OPENPAGES_API_KEY', None),
        authentication_url=getattr(settings, 'OPENPAGES_AUTHENTICATION_URL', None),
        instance_name=getattr(settings, 'OPENPAGES_INSTANCE_NAME', None)
    )
    
    schema_builder = SchemaBuilder(client)
    
    # Test with different object types
    test_types = ["SOXControl", "SOXIssue", "SOXRisk"]
    
    for object_type in test_types:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {object_type}")
        logger.info(f"{'='*60}")
        
        try:
            # Get type definition
            type_def = await schema_builder.get_type_definition(object_type)
            
            if not type_def:
                logger.warning(f"Could not get type definition for {object_type}")
                continue
            
            # Check if Title field exists and is required
            title_field = None
            is_required = False
            for field in type_def.get("field_definitions", []):
                if field.get("name") == "Title":
                    title_field = field
                    is_required = title_field.get("required", False)
                    break
            
            if title_field:
                logger.info(f"Title field found for {object_type}")
                logger.info(f"  - Required: {is_required}")
                logger.info(f"  - Data Type: {title_field.get('data_type')}")
                logger.info(f"  - Description: {title_field.get('description', 'N/A')}")
            else:
                logger.info(f"Title field NOT found in type definition for {object_type}")
            
            # Build schema
            schema = await schema_builder.build_dynamic_schema_for_object(
                object_type=object_type,
                object_label=object_type.lower()
            )
            
            # Check if title is in required fields
            required_fields = schema.get("required", [])
            title_in_required = "title" in required_fields
            
            logger.info(f"\nSchema Analysis:")
            logger.info(f"  - Required fields: {required_fields}")
            logger.info(f"  - Title is required in schema: {title_in_required}")
            
            # Verify title property exists
            if "title" in schema.get("properties", {}):
                title_prop = schema["properties"]["title"]
                logger.info(f"  - Title description: {title_prop.get('description')}")
            
            # Test upsert schema
            upsert_schema = schema_builder.create_upsert_schema(
                base_schema=schema,
                object_type=object_type,
                available_types=["SOXControl", "SOXIssue", "SOXRisk"],
                type_def=type_def
            )
            
            upsert_required = upsert_schema.get("required", [])
            title_in_upsert_required = "title" in upsert_required
            
            logger.info(f"\nUpsert Schema Analysis:")
            logger.info(f"  - Required fields: {upsert_required}")
            logger.info(f"  - Title is required in upsert schema: {title_in_upsert_required}")
            
            # Validation
            if title_field and is_required:
                if title_in_required and title_in_upsert_required:
                    logger.info(f"✅ SUCCESS: Title correctly marked as required for {object_type}")
                else:
                    logger.error(f"❌ FAILURE: Title should be required but isn't in schema for {object_type}")
            else:
                if not title_in_required and not title_in_upsert_required:
                    logger.info(f"✅ SUCCESS: Title correctly marked as optional for {object_type}")
                else:
                    logger.warning(f"⚠️  WARNING: Title marked as required in schema but not in type definition for {object_type}")
            
        except Exception as e:
            logger.error(f"Error testing {object_type}: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_title_required())