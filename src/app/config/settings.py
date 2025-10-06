"""
Configuration settings for the GRC MCP Server
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # Application settings
    APP_NAME: str = "GRC MCP Server"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # OpenPages settings
    OPENPAGES_BASE_URL: str = os.getenv("OPENPAGES_BASE_URL", "")
    OPENPAGES_USERNAME: str = os.getenv("OPENPAGES_USERNAME", "")
    OPENPAGES_PASSWORD: str = os.getenv("OPENPAGES_PASSWORD", "")
    
    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # SSL settings
    SSL_VERIFY: bool = os.getenv("SSL_VERIFY", "True").lower() == "true"
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

# Create settings instance
settings = Settings()

# Made with Bob
