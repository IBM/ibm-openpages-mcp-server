"""
Test tool exposure modes configuration

This module tests the TOOL_EXPOSURE_MODE setting to ensure tools are
correctly exposed based on the configuration in object_types.json.
"""

import pytest
from src.app.config.settings import Settings
from src.app.mcp.mcp_server import MCPServer


class TestToolExposureModes:
    """Test tool exposure mode configurations"""
    
    def test_all_mode_exposes_all_tools(self):
        """Test that 'all' mode exposes both generic and type-specific tools"""
        # Create settings with 'all' mode
        settings = Settings(TOOL_EXPOSURE_MODE="all")
        server = MCPServer(custom_settings=settings)
        
        tool_names = [tool["name"] for tool in server.tools]
        
        # Check for generic tools
        assert "execute_openpages_query" in tool_names, "Generic query tool should be present"
        assert any("upsert_object" in name for name in tool_names), "Generic upsert tool should be present"
        assert any("delete_object" in name for name in tool_names), "Generic delete tool should be present"
        assert any("associate_objects" in name for name in tool_names), "Generic associate tool should be present"
        assert any("dissociate_objects" in name for name in tool_names), "Generic dissociate tool should be present"
        
        # Check for type-specific tools (if configured)
        if settings.OPENPAGES_OBJECT_TYPES:
            # Should have type-specific upsert tools
            type_specific_upsert = [name for name in tool_names if "upsert_" in name and "upsert_object" not in name]
            assert len(type_specific_upsert) > 0, "Type-specific upsert tools should be present"
            
            # Should have type-specific query tools
            type_specific_query = [name for name in tool_names if "query" in name.lower() and name != "execute_openpages_query"]
            assert len(type_specific_query) > 0, "Type-specific query tools should be present"
    
    def test_ontology_based_mode(self):
        """Test that 'ontology_based' mode exposes only generic tools"""
        # Create settings with 'ontology_based' mode
        settings = Settings(TOOL_EXPOSURE_MODE="ontology_based")
        server = MCPServer(custom_settings=settings)
        
        tool_names = [tool["name"] for tool in server.tools]
        
        # Check for generic tools
        assert "execute_openpages_query" in tool_names, "Generic query tool should be present"
        assert any("upsert_object" in name for name in tool_names), "Generic upsert tool should be present"
        assert any("delete_object" in name for name in tool_names), "Generic delete tool should be present"
        assert any("associate_objects" in name for name in tool_names), "Generic associate tool should be present"
        assert any("dissociate_objects" in name for name in tool_names), "Generic dissociate tool should be present"
        
        # Check that type-specific tools are NOT present (if configured)
        if settings.OPENPAGES_OBJECT_TYPES:
            # Should NOT have type-specific upsert tools (other than generic upsert_object)
            type_specific_upsert = [name for name in tool_names if "upsert_" in name and "upsert_object" not in name]
            assert len(type_specific_upsert) == 0, "Type-specific upsert tools should NOT be present"
            
            # Should NOT have type-specific query tools (other than execute_openpages_query)
            type_specific_query = [name for name in tool_names if "query" in name.lower() and name != "execute_openpages_query"]
            assert len(type_specific_query) == 0, "Type-specific query tools should NOT be present"
    
    def test_type_based_mode(self):
        """Test that 'type_based' mode exposes only type-specific tools"""
        # Create settings with 'type_based' mode
        settings = Settings(TOOL_EXPOSURE_MODE="type_based")
        server = MCPServer(custom_settings=settings)
        
        tool_names = [tool["name"] for tool in server.tools]
        
        # Check that generic query tool is NOT present
        assert "execute_openpages_query" not in tool_names, "Generic query tool should NOT be present"
        
        # Check that generic upsert/associate/dissociate are NOT present
        generic_upsert = [name for name in tool_names if name.endswith("upsert_object")]
        assert len(generic_upsert) == 0, "Generic upsert_object tool should NOT be present"
        
        generic_associate = [name for name in tool_names if name.endswith("associate_objects")]
        assert len(generic_associate) == 0, "Generic associate_objects tool should NOT be present"
        
        generic_dissociate = [name for name in tool_names if name.endswith("dissociate_objects")]
        assert len(generic_dissociate) == 0, "Generic dissociate_objects tool should NOT be present"
        
        # Check that delete tool IS present (always available)
        assert any("delete_object" in name for name in tool_names), "Generic delete tool should always be present"
        
        # Check for type-specific tools (if configured)
        if settings.OPENPAGES_OBJECT_TYPES:
            # Should have type-specific upsert tools
            type_specific_upsert = [name for name in tool_names if "upsert_" in name and not name.endswith("upsert_object")]
            assert len(type_specific_upsert) > 0, "Type-specific upsert tools should be present"
            
            # Should have type-specific query tools
            type_specific_query = [name for name in tool_names if "query" in name.lower() and name != "execute_openpages_query"]
            assert len(type_specific_query) > 0, "Type-specific query tools should be present"
    
    def test_base_tools_always_present(self):
        """Test that base tools (echo, list_resources, get_resource) are always present"""
        for mode in ["all", "ontology_based", "type_based"]:
            settings = Settings(TOOL_EXPOSURE_MODE=mode)
            server = MCPServer(custom_settings=settings)
            
            tool_names = [tool["name"] for tool in server.tools]
            
            assert "echo" in tool_names, f"Echo tool should be present in {mode} mode"
            assert "list_resources" in tool_names, f"list_resources tool should be present in {mode} mode"
            assert "get_resource" in tool_names, f"get_resource tool should be present in {mode} mode"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
