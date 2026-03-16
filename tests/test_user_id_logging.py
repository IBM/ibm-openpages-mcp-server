"""
Test User ID Logging Enhancement

Tests the automatic extraction and logging of user_id from authentication context.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.auth.token_utils import extract_username_from_token, extract_username_from_user_data
from src.app.auth.service import AuthService, AuthResult
from src.app.auth.providers import ServerCredentialProvider
from src.app.config.settings import Settings


class TestJWTUsernameExtraction:
    """Test JWT token username extraction"""
    
    def test_extract_from_jwt_with_sub(self):
        """Test extracting username from JWT with 'sub' claim"""
        # Sample JWT token with sub claim (not verified, just for testing)
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqb2huLmRvZUBleGFtcGxlLmNvbSIsIm5hbWUiOiJKb2huIERvZSIsImlhdCI6MTUxNjIzOTAyMn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        username = extract_username_from_token(token)
        assert username == "john.doe@example.com"
    
    def test_extract_from_jwt_with_bearer_prefix(self):
        """Test extracting username from JWT with Bearer prefix"""
        token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqb2huLmRvZUBleGFtcGxlLmNvbSIsIm5hbWUiOiJKb2huIERvZSIsImlhdCI6MTUxNjIzOTAyMn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        username = extract_username_from_token(token)
        assert username == "john.doe@example.com"
    
    def test_extract_from_invalid_token(self):
        """Test extracting username from invalid token"""
        token = "not-a-jwt-token"
        
        username = extract_username_from_token(token)
        assert username is None
    
    def test_extract_from_empty_token(self):
        """Test extracting username from empty token"""
        username = extract_username_from_token("")
        assert username is None


class TestUserDataExtraction:
    """Test user data extraction"""
    
    def test_extract_from_user_data_with_name(self):
        """Test extracting username from user data with 'name' field"""
        user_data = {"name": "john.doe", "email": "john@example.com"}
        
        username = extract_username_from_user_data(user_data)
        assert username == "john.doe"
    
    def test_extract_from_user_data_with_email(self):
        """Test extracting username from user data with only 'email' field"""
        user_data = {"email": "john@example.com"}
        
        username = extract_username_from_user_data(user_data)
        assert username == "john@example.com"
    
    def test_extract_from_empty_user_data(self):
        """Test extracting username from empty user data"""
        username = extract_username_from_user_data({})
        assert username is None


class TestBasicAuthUsernameExtraction:
    """Test basic auth username extraction"""
    
    @pytest.mark.asyncio
    async def test_server_credential_provider_basic_auth(self):
        """Test ServerCredentialProvider extracts username for basic auth"""
        # Create settings with basic auth
        settings = Settings()
        settings.OPENPAGES_AUTHENTICATION_TYPE = "basic"
        settings.OPENPAGES_USERNAME = "testuser"
        settings.OPENPAGES_PASSWORD = "testpass"
        
        provider = ServerCredentialProvider()
        provider.settings = settings
        
        # Resolve should set username
        await provider.resolve()
        
        username = provider.get_username()
        assert username == "testuser"


class TestAuthServiceUsernameExtraction:
    """Test AuthService username extraction"""
    
    @pytest.mark.asyncio
    async def test_auth_service_with_jwt_token(self):
        """Test AuthService extracts username from JWT token"""
        settings = Settings()
        auth_service = AuthService(settings)
        
        # JWT token with sub claim
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJqb2huLmRvZUBleGFtcGxlLmNvbSIsIm5hbWUiOiJKb2huIERvZSIsImlhdCI6MTUxNjIzOTAyMn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        
        auth_result = await auth_service.resolve_for_request(context_token=token)
        
        assert auth_result.username == "john.doe@example.com"
    
    @pytest.mark.asyncio
    async def test_auth_service_with_basic_auth(self):
        """Test AuthService extracts username from basic auth"""
        settings = Settings()
        settings.OPENPAGES_AUTHENTICATION_TYPE = "basic"
        settings.OPENPAGES_USERNAME = "admin"
        settings.OPENPAGES_PASSWORD = "password"
        
        auth_service = AuthService(settings)
        
        auth_result = await auth_service.resolve_for_request()
        
        assert auth_result.username == "admin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])