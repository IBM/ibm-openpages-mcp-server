"""
Configuration settings for the GRC MCP Server

This module defines the application configuration using Pydantic settings.
It loads configuration from environment variables and .env files, and provides
settings for:
- Application behavior (debug mode, server mode)
- OpenPages connection (URL, authentication)
- Observability (logging, metrics, tracing)
- Rate limiting
- Object type configurations

The settings are loaded from environment variables with the prefix matching
the variable names, and can be overridden via .env files.
"""

import os
import json
import pathlib
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any, List

# Get the project root directory (where main.py is located)
# This file is at: project_root/src/app/config/settings.py
# So we go up 3 levels to get to project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    """
    Application settings for GRC MCP Server
    
    This class defines all configuration settings for the application using Pydantic.
    Settings are loaded from environment variables and .env files.
    
    Attributes:
        APP_NAME: Name of the application
        DEBUG: Enable debug mode
        SERVER_MODE: Server mode ('remote' for HTTP, 'local' for stdio)
        OPENPAGES_BASE_URL: Base URL for OpenPages API
        OPENPAGES_AUTHENTICATION_TYPE: Authentication type ('basic' or 'bearer')
        OPENPAGES_USERNAME: Username for basic auth
        OPENPAGES_PASSWORD: Password for basic auth
        OPENPAGES_APIKEY: API key for bearer auth
        OPENPAGES_AUTHENTICATION_URL: Authentication URL for bearer auth
        HOST: Server host address
        PORT: Server port number
        SSL_VERIFY: Enable SSL certificate verification
        LOG_LEVEL: Logging level
        LOG_FORMAT: Log format ('json' or 'text')
        LOG_FILE: Optional log file path
        OBSERVABILITY_ENABLED: Enable observability features
        METRICS_ENABLED: Enable Prometheus metrics
        METRICS_PORT: Metrics server port
        TRACING_ENABLED: Enable distributed tracing
        OTLP_ENDPOINT: OpenTelemetry collector endpoint
        CONSOLE_TRACING: Enable console trace export
        RATE_LIMIT_ENABLED: Enable rate limiting
        RATE_LIMIT_REQUESTS_PER_MINUTE: Rate limit threshold
        RATE_LIMIT_BURST_SIZE: Rate limit burst size
        OPENPAGES_OBJECT_TYPES: List of configured object types
        OUTPUT_FORMAT: Default output format ('text' or 'json')
        OBJECT_TYPES_CONFIG_PATH: Path to object types configuration file
    """
    
    # Application settings
    APP_NAME: str = "GRC MCP Server"
    DEBUG: bool = False
    
    # Server mode settings
    SERVER_MODE: str = "remote"  # 'remote' or 'local'
    
    # OpenPages settings
    _base_url: str = ""
    # Ensure the base URL has the correct protocol
    OPENPAGES_BASE_URL: str = ""
    OPENPAGES_AUTHENTICATION_TYPE: str = "basic"
    OPENPAGES_USERNAME: str = ""
    OPENPAGES_PASSWORD: str = ""
    OPENPAGES_APIKEY: str = ""
    OPENPAGES_AUTHENTICATION_URL: str = ""

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # SSL settings
    SSL_VERIFY: bool = True
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # Options: "json" or "text"
    LOG_FILE: Optional[str] = None
    
    # Observability settings
    OBSERVABILITY_ENABLED: bool = True
    
    # Metrics settings
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    
    # Tracing settings
    TRACING_ENABLED: bool = False
    OTLP_ENDPOINT: Optional[str] = None  # e.g., "http://localhost:4317"
    CONSOLE_TRACING: bool = False
    
    # Rate limiting settings
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST_SIZE: int = 10
    
    # Object type configuration
    OPENPAGES_OBJECT_TYPES: List[Dict[str, Any]] = []
    
    # Global output format setting
    OUTPUT_FORMAT: str = "text"  # Options: "text" or "json"
    
    # Path to object types configuration file
    OBJECT_TYPES_CONFIG_PATH: str = "object_types.json"
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    def __init__(self, env_file: Optional[str] = None, **data: Any):
        """
        Initialize settings with optional custom environment file
        
        Args:
            env_file: Optional path to environment file
            data: Additional data to initialize settings with
        """
        # Set custom env file if provided
        if env_file:
            self.model_config["env_file"] = env_file
            
        super().__init__(**data)
        
        # Process base URL to ensure it has the correct protocol
        if self._base_url:
            if not (self._base_url.startswith('http://') or self._base_url.startswith('https://')):
                self.OPENPAGES_BASE_URL = f"https://{self._base_url}"
            else:
                self.OPENPAGES_BASE_URL = self._base_url
        
        # Load object types from JSON file
        self._load_object_types()
    
    def _load_object_types(self) -> None:
        """
        Load object types from JSON configuration file
        
        Reads the object_types.json file and populates the OPENPAGES_OBJECT_TYPES
        list with configured object type definitions. Also loads global settings
        like output format.
        """
        try:
            # Get the path to the object_types.json file
            config_path = pathlib.Path(self.OBJECT_TYPES_CONFIG_PATH)
            
            # If path is not absolute, make it relative to the project root
            if not config_path.is_absolute():
                # Try to find the config file in multiple locations
                possible_paths = [
                    pathlib.Path(__file__).parent.parent.parent.parent / config_path,  # Project root
                    pathlib.Path(__file__).parent / config_path,  # Config directory
                    pathlib.Path.cwd() / config_path,  # Current working directory
                ]
                
                config_path = None
                for path in possible_paths:
                    if path.exists():
                        config_path = path
                        break
                
                if not config_path:
                    print(f"Warning: Object types configuration file not found in any of the expected locations")
                    return
                    
            if not config_path.exists():
                print(f"Warning: Object types configuration file not found: {config_path}")
                return
                
            # Load the configuration from the file
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    config_data = json.load(f)
                    self.OPENPAGES_OBJECT_TYPES = config_data.get('object_types', [])
                    
                    # Load global settings if present
                    global_settings = config_data.get('global_settings', {})
                    if 'output_format' in global_settings:
                        self.OUTPUT_FORMAT = global_settings['output_format']
                        print(f"Loaded global output format: {self.OUTPUT_FORMAT}")
                    
                    print(f"Loaded {len(self.OPENPAGES_OBJECT_TYPES)} object types from {config_path}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing object types configuration file: {e}")
        except Exception as e:
            print(f"Error loading object types configuration: {e}")

# Create settings instance with default .env file
settings = Settings()

# Function to create settings with custom env file
def create_settings(env_file: str) -> Settings:
    """
    Create settings instance with custom environment file
    
    Args:
        env_file: Path to environment file
        
    Returns:
        Settings instance with values from the specified environment file
    """
    return Settings(env_file=env_file)

# Made with Bob
