"""
Test configuration robustness - verify server can start with missing optional settings
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.config.settings import Settings


class TestConfigurationRobustness:
    """Test that configuration handles missing and invalid settings gracefully"""
    
    def test_minimal_valid_config_basic_auth(self):
        """Test with minimal valid configuration for basic auth"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            env_file = f.name
        
        try:
            settings = Settings(env_file=env_file)
            
            # Verify mandatory settings are loaded
            assert settings.OPENPAGES_BASE_URL == "https://test.example.com"
            assert settings.OPENPAGES_AUTHENTICATION_TYPE == "basic"
            assert settings.OPENPAGES_USERNAME == "testuser"
            assert settings.OPENPAGES_PASSWORD == "testpass"
            
            # Verify optional settings have defaults
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 8000
            assert settings.LOG_LEVEL == "INFO"
            assert settings.LOG_FORMAT == "json"
            assert settings.OBSERVABILITY_ENABLED == False
            assert settings.METRICS_ENABLED == False
            assert settings.TRACING_ENABLED == False
            assert settings.RATE_LIMIT_ENABLED == False
            assert settings.DEFAULT_CURRENCY == "USD"
            assert settings.SCHEMA_CACHE_MAX_SIZE == 20
            assert settings.MCP_SESSION_ENFORCEMENT == False
            
        finally:
            os.unlink(env_file)
    
    def test_minimal_valid_config_bearer_auth_ibm_cloud(self):
        """Test with minimal valid configuration for bearer auth (IBM Cloud)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=bearer\n")
            f.write("OPENPAGES_APIKEY=test-api-key\n")
            f.write("OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token\n")
            env_file = f.name
        
        try:
            settings = Settings(env_file=env_file)
            
            # Verify mandatory settings are loaded
            assert settings.OPENPAGES_BASE_URL == "https://test.example.com"
            assert settings.OPENPAGES_AUTHENTICATION_TYPE == "bearer"
            assert settings.OPENPAGES_APIKEY == "test-api-key"
            assert settings.OPENPAGES_AUTHENTICATION_URL == "https://iam.cloud.ibm.com/identity/token"
            
        finally:
            os.unlink(env_file)
    
    def test_minimal_valid_config_bearer_auth_cp4d(self):
        """Test with minimal valid configuration for bearer auth (CP4D)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://cpd-test.example.com/openpages-instance\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=bearer\n")
            f.write("OPENPAGES_USERNAME=cpadmin\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            f.write("OPENPAGES_AUTHENTICATION_URL=https://cpd-test.example.com/icp4d-api/v1/authorize\n")
            env_file = f.name
        
        try:
            settings = Settings(env_file=env_file)
            
            # Verify mandatory settings are loaded
            assert settings.OPENPAGES_BASE_URL == "https://cpd-test.example.com/openpages-instance"
            assert settings.OPENPAGES_AUTHENTICATION_TYPE == "bearer"
            assert settings.OPENPAGES_USERNAME == "cpadmin"
            assert settings.OPENPAGES_PASSWORD == "testpass"
            
        finally:
            os.unlink(env_file)
    
    def test_missing_base_url_raises_error(self):
        """Test that missing base URL raises validation error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            env_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Configuration validation failed"):
                Settings(env_file=env_file)
        finally:
            os.unlink(env_file)
    
    def test_missing_basic_auth_credentials_raises_error(self):
        """Test that missing basic auth credentials raises validation error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            env_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Configuration validation failed"):
                Settings(env_file=env_file)
        finally:
            os.unlink(env_file)
    
    def test_missing_bearer_auth_url_raises_error(self):
        """Test that missing bearer auth URL raises validation error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=bearer\n")
            f.write("OPENPAGES_APIKEY=test-key\n")
            env_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Configuration validation failed"):
                Settings(env_file=env_file)
        finally:
            os.unlink(env_file)
    
    def test_missing_bearer_auth_apikey_for_ibm_cloud_raises_error(self):
        """Test that missing API key for IBM Cloud bearer auth raises validation error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=bearer\n")
            f.write("OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token\n")
            env_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Configuration validation failed"):
                Settings(env_file=env_file)
        finally:
            os.unlink(env_file)
    
    def test_missing_bearer_auth_credentials_for_cp4d_raises_error(self):
        """Test that missing credentials for CP4D bearer auth raises validation error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=bearer\n")
            f.write("OPENPAGES_AUTHENTICATION_URL=https://cpd-test.example.com/icp4d-api/v1/authorize\n")
            env_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Configuration validation failed"):
                Settings(env_file=env_file)
        finally:
            os.unlink(env_file)
    
    def test_invalid_log_level_uses_default(self, capsys):
        """Test that invalid log level falls back to default"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            f.write("LOG_LEVEL=INVALID\n")
            env_file = f.name
        
        try:
            settings = Settings(env_file=env_file)
            
            # Should default to INFO
            assert settings.LOG_LEVEL == "INFO"
            
            # Check warning was printed
            captured = capsys.readouterr()
            assert "LOG_LEVEL 'INVALID' is not valid" in captured.err
            
        finally:
            os.unlink(env_file)
    
    def test_invalid_port_raises_error(self):
        """Test that invalid port number raises validation error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            f.write("PORT=99999\n")
            env_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Configuration validation failed"):
                Settings(env_file=env_file)
        finally:
            os.unlink(env_file)
    
    def test_missing_object_types_config_file_is_non_blocking(self, capsys):
        """Test that missing object types config file doesn't prevent server start"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            f.write("OBJECT_TYPES_CONFIG_PATH=/nonexistent/path/object_types.json\n")
            env_file = f.name
        
        try:
            settings = Settings(env_file=env_file)
            
            # Should have empty object types list
            assert settings.OPENPAGES_OBJECT_TYPES == []
            
            # Check warning message was printed
            captured = capsys.readouterr()
            assert "Object types configuration not found" in captured.err
            assert "Server will start with limited functionality" in captured.err
            
        finally:
            os.unlink(env_file)
    
    def test_base_url_without_protocol_gets_https_added(self):
        """Test that base URL without protocol gets https:// added"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            # Use _base_url field which triggers the protocol addition logic
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            f.write("OBJECT_TYPES_CONFIG_PATH=/nonexistent/path.json\n")
            env_file = f.name
        
        try:
            # Set via environment variable to test the _base_url logic
            os.environ['OPENPAGES_BASE_URL'] = 'test.example.com'
            settings = Settings(env_file=env_file)
            
            # Should have https:// added
            assert settings.OPENPAGES_BASE_URL == "https://test.example.com"
            
        finally:
            os.environ.pop('OPENPAGES_BASE_URL', None)
            os.unlink(env_file)
    
    def test_all_optional_settings_can_be_omitted(self):
        """Test that all optional settings can be safely omitted"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            # Only mandatory settings
            f.write("OPENPAGES_BASE_URL=https://test.example.com\n")
            f.write("OPENPAGES_AUTHENTICATION_TYPE=basic\n")
            f.write("OPENPAGES_USERNAME=testuser\n")
            f.write("OPENPAGES_PASSWORD=testpass\n")
            # Point to non-existent config to avoid loading actual object types
            f.write("OBJECT_TYPES_CONFIG_PATH=/nonexistent/path.json\n")
            env_file = f.name
        
        try:
            settings = Settings(env_file=env_file)
            
            # All optional settings should have defaults
            assert settings.APP_NAME == "GRC MCP Server"
            assert settings.DEBUG == False
            assert settings.SERVER_MODE == "remote"
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 8000
            assert settings.SSL_VERIFY == True
            assert settings.HTTP_MAX_CONNECTIONS == 20
            assert settings.LOG_LEVEL == "INFO"
            assert settings.LOG_FORMAT == "json"
            assert settings.LOG_FILE is None
            assert settings.LOG_MAX_BYTES == 10 * 1024 * 1024
            assert settings.LOG_BACKUP_COUNT == 5
            assert settings.OBSERVABILITY_ENABLED == False
            assert settings.METRICS_ENABLED == False
            assert settings.TRACING_ENABLED == False
            assert settings.OTLP_ENDPOINT is None
            assert settings.CONSOLE_TRACING == False
            assert settings.RATE_LIMIT_ENABLED == False
            assert settings.RATE_LIMIT_REQUESTS_PER_MINUTE == 60
            assert settings.RATE_LIMIT_BURST_SIZE == 10
            assert settings.OPENPAGES_OBJECT_TYPES == []
            assert settings.OUTPUT_FORMAT == "json"
            assert settings.NAMESPACE == ""
            assert settings.TOOL_EXPOSURE_MODE == "ontology_based"
            assert settings.AUTH_ENABLED == True
            assert settings.DEFAULT_CURRENCY == "USD"
            assert settings.SCHEMA_CACHE_MAX_SIZE == 20
            assert settings.SCHEMA_CACHE_TTL == 3600
            assert settings.ENABLE_MINIMAL_SCHEMA_MODE == True
            assert settings.CACHE_QUERY_EXAMPLES == True
            assert settings.MCP_SESSION_ENFORCEMENT == False
            assert settings.MCP_SESSION_TTL == 3600
            assert settings.MCP_SESSION_MAX_COUNT == 1000
            assert settings.MCP_SESSION_CLEANUP_INTERVAL == 300
            
        finally:
            os.unlink(env_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
