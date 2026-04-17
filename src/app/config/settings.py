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
    
    # OpenPages settings (mandatory - will be validated)
    _base_url: str = ""
    # Ensure the base URL has the correct protocol
    OPENPAGES_BASE_URL: str = ""
    OPENPAGES_AUTHENTICATION_TYPE: str = "basic"
    OPENPAGES_USERNAME: str = ""
    OPENPAGES_PASSWORD: str = ""
    OPENPAGES_APIKEY: str = ""
    OPENPAGES_AUTHENTICATION_URL: str = ""
    OPENPAGES_INSTANCE_NAME: str = ""  # For CP4D deployments

    # Server settings (with sensible defaults)
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # SSL settings (default to True for security)
    SSL_VERIFY: bool = True

    # HTTP connection pool settings (default to reasonable values)
    HTTP_MAX_CONNECTIONS: int = 20
    
    # Logging settings (with sensible defaults)
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # Options: "json" or "text"
    LOG_FILE: Optional[str] = None
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB default
    LOG_BACKUP_COUNT: int = 5  # Keep 5 backup files
    
    # Observability settings (default to False for optional features)
    OBSERVABILITY_ENABLED: bool = False
    
    # Metrics settings (default to False)
    METRICS_ENABLED: bool = False
    
    # Tracing settings (default to False)
    TRACING_ENABLED: bool = False
    OTLP_ENDPOINT: Optional[str] = None  # e.g., "http://localhost:4317"
    CONSOLE_TRACING: bool = False
    
    # Rate limiting settings (default to False for optional feature)
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST_SIZE: int = 10
    
    # Object type configuration (empty list is safe default)
    OPENPAGES_OBJECT_TYPES: List[Dict[str, Any]] = []
    # Global output format setting (loaded from object_types.json)
    OUTPUT_FORMAT: str = "json"  # Options: "text" or "json"
    
    
    # Global namespace for generic tools (empty string is safe default)
    NAMESPACE: str = ""  # Namespace prefix for generic tools (e.g., "openpages")
    
    # Tool exposure configuration (safe default)
    TOOL_EXPOSURE_MODE: str = "ontology_based"  # Options: "all", "ontology_based", "type_based"

    # Authentication framework settings (default to True for security)
    AUTH_ENABLED: bool = True
    
    # Default currency for CURRENCY_TYPE fields (safe default)
    DEFAULT_CURRENCY: str = "USD"  # ISO 4217 currency code
    
    # Path to object types configuration file (safe default)
    OBJECT_TYPES_CONFIG_PATH: str = "src/app/config/object_types.json"
    
    # Token optimization settings (Phase 2) - with sensible defaults
    SCHEMA_CACHE_MAX_SIZE: int = 20  # Maximum number of schemas to cache (LRU)
    SCHEMA_CACHE_TTL: int = 3600  # Schema cache TTL in seconds (1 hour)
    ENABLE_MINIMAL_SCHEMA_MODE: bool = True  # Enable minimal schema mode by default
    CACHE_QUERY_EXAMPLES: bool = True  # Cache query examples by default

    # MCP session enforcement (Streamable HTTP transport, spec 2025-03-26)
    # Default to False to allow clients that do not support session headers
    MCP_SESSION_ENFORCEMENT: bool = False
    
    # MCP session management settings (with sensible defaults)
    MCP_SESSION_TTL: int = 3600  # Session TTL in seconds (1 hour)
    MCP_SESSION_MAX_COUNT: int = 1000  # Maximum number of concurrent sessions
    MCP_SESSION_CLEANUP_INTERVAL: int = 300  # Cleanup task interval in seconds (5 minutes)
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from environment
    )
    
    def __init__(self, env_file: Optional[str] = None, **data: Any):
        """
        Initialize settings with optional custom environment file
        
        Args:
            env_file: Optional path to environment file
            data: Additional data to initialize settings with
        """
        # Determine the .env file path
        if env_file:
            env_file_path = env_file
        else:
            # Look for .env file relative to the project root (where this file is located)
            project_root = pathlib.Path(__file__).parent.parent.parent.parent
            env_file_path = project_root / ".env"
            
            # If .env doesn't exist in project root, try .env.local
            if not env_file_path.exists():
                env_local_path = project_root / ".env.local"
                if env_local_path.exists():
                    env_file_path = env_local_path
        
        # Update model config with the resolved env file path
        self.model_config["env_file"] = str(env_file_path)
            
        super().__init__(**data)
        
        # Process base URL to ensure it has the correct protocol
        if self.OPENPAGES_BASE_URL and not (self.OPENPAGES_BASE_URL.startswith('http://') or self.OPENPAGES_BASE_URL.startswith('https://')):
            self.OPENPAGES_BASE_URL = f"https://{self.OPENPAGES_BASE_URL}"
        
        # Load object types from JSON file (non-blocking)
        self._load_object_types()
        
        # Validate mandatory settings
        self._validate_settings()
    
    def _validate_settings(self) -> None:
        """
        Validate mandatory settings and provide helpful error messages.
        
        This method checks that all required configuration is present for the server
        to function properly. It provides clear error messages to help users fix
        configuration issues.
        
        Raises:
            ValueError: If mandatory settings are missing or invalid
        """
        import sys
        
        errors = []
        
        # Validate OpenPages base URL (mandatory)
        if not self.OPENPAGES_BASE_URL:
            errors.append(
                "OPENPAGES_BASE_URL is required. "
                "Please set it in your .env file or environment variables. "
                "Example: OPENPAGES_BASE_URL=https://your-openpages-instance.com"
            )
        
        # Validate authentication type
        if self.OPENPAGES_AUTHENTICATION_TYPE not in ["basic", "bearer"]:
            errors.append(
                f"OPENPAGES_AUTHENTICATION_TYPE must be 'basic' or 'bearer', got '{self.OPENPAGES_AUTHENTICATION_TYPE}'. "
                "Please set it in your .env file."
            )
        
        # Validate authentication credentials based on type
        if self.OPENPAGES_AUTHENTICATION_TYPE == "basic":
            if not self.OPENPAGES_USERNAME or not self.OPENPAGES_PASSWORD:
                errors.append(
                    "OPENPAGES_USERNAME and OPENPAGES_PASSWORD are required for basic authentication. "
                    "Please set them in your .env file."
                )
        elif self.OPENPAGES_AUTHENTICATION_TYPE == "bearer":
            if not self.OPENPAGES_AUTHENTICATION_URL:
                errors.append(
                    "OPENPAGES_AUTHENTICATION_URL is required for bearer authentication. "
                    "Please set it in your .env file. "
                    "Example: OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token"
                )
            
            # Check if this is CP4D authentication
            is_cp4d = (
                self.OPENPAGES_AUTHENTICATION_URL and
                ('/icp4d-api/v1/authorize' in self.OPENPAGES_AUTHENTICATION_URL
                 in self.OPENPAGES_AUTHENTICATION_URL)
            )
            
            if is_cp4d:
                # CP4D uses username/password
                if not self.OPENPAGES_USERNAME or not self.OPENPAGES_PASSWORD:
                    errors.append(
                        "OPENPAGES_USERNAME and OPENPAGES_PASSWORD are required for CP4D authentication. "
                        "Please set them in your .env file."
                    )
            else:
                # IBM Cloud IAM/MCSP uses API key
                if not self.OPENPAGES_APIKEY:
                    errors.append(
                        "OPENPAGES_APIKEY is required for bearer authentication (IBM Cloud/MCSP). "
                        "Please set it in your .env file."
                    )
        
        # Validate port number
        if not (1 <= self.PORT <= 65535):
            errors.append(
                f"PORT must be between 1 and 65535, got {self.PORT}. "
                "Please set a valid port number in your .env file."
            )
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL.upper() not in valid_log_levels:
            print(
                f"Warning: LOG_LEVEL '{self.LOG_LEVEL}' is not valid. "
                f"Valid options are: {', '.join(valid_log_levels)}. "
                f"Defaulting to INFO.",
                file=sys.stderr
            )
            self.LOG_LEVEL = "INFO"
        
        # Validate log format
        if self.LOG_FORMAT not in ["json", "text"]:
            print(
                f"Warning: LOG_FORMAT '{self.LOG_FORMAT}' is not valid. "
                f"Valid options are: json, text. Defaulting to json.",
                file=sys.stderr
            )
            self.LOG_FORMAT = "json"
        
        # Validate server mode
        if self.SERVER_MODE not in ["remote", "local"]:
            print(
                f"Warning: SERVER_MODE '{self.SERVER_MODE}' is not valid. "
                f"Valid options are: remote, local. Defaulting to remote.",
                file=sys.stderr
            )
            self.SERVER_MODE = "remote"
        
        # Validate tool exposure mode
        valid_exposure_modes = ["all", "ontology_based", "type_based"]
        if self.TOOL_EXPOSURE_MODE not in valid_exposure_modes:
            print(
                f"Warning: TOOL_EXPOSURE_MODE '{self.TOOL_EXPOSURE_MODE}' is not valid. "
                f"Valid options are: {', '.join(valid_exposure_modes)}. "
                f"Defaulting to ontology_based.",
                file=sys.stderr
            )
            self.TOOL_EXPOSURE_MODE = "ontology_based"
        
        # Validate numeric settings have reasonable values
        if self.RATE_LIMIT_REQUESTS_PER_MINUTE < 1:
            print(
                f"Warning: RATE_LIMIT_REQUESTS_PER_MINUTE must be at least 1, got {self.RATE_LIMIT_REQUESTS_PER_MINUTE}. "
                f"Defaulting to 60.",
                file=sys.stderr
            )
            self.RATE_LIMIT_REQUESTS_PER_MINUTE = 60
        
        if self.RATE_LIMIT_BURST_SIZE < 1:
            print(
                f"Warning: RATE_LIMIT_BURST_SIZE must be at least 1, got {self.RATE_LIMIT_BURST_SIZE}. "
                f"Defaulting to 10.",
                file=sys.stderr
            )
            self.RATE_LIMIT_BURST_SIZE = 10
        
        if self.SCHEMA_CACHE_MAX_SIZE < 1:
            print(
                f"Warning: SCHEMA_CACHE_MAX_SIZE must be at least 1, got {self.SCHEMA_CACHE_MAX_SIZE}. "
                f"Defaulting to 20.",
                file=sys.stderr
            )
            self.SCHEMA_CACHE_MAX_SIZE = 20
        
        if self.SCHEMA_CACHE_TTL < 0:
            print(
                f"Warning: SCHEMA_CACHE_TTL must be non-negative, got {self.SCHEMA_CACHE_TTL}. "
                f"Defaulting to 3600.",
                file=sys.stderr
            )
            self.SCHEMA_CACHE_TTL = 3600
        
        if self.MCP_SESSION_TTL < 1:
            print(
                f"Warning: MCP_SESSION_TTL must be at least 1, got {self.MCP_SESSION_TTL}. "
                f"Defaulting to 3600.",
                file=sys.stderr
            )
            self.MCP_SESSION_TTL = 3600
        
        if self.MCP_SESSION_MAX_COUNT < 1:
            print(
                f"Warning: MCP_SESSION_MAX_COUNT must be at least 1, got {self.MCP_SESSION_MAX_COUNT}. "
                f"Defaulting to 1000.",
                file=sys.stderr
            )
            self.MCP_SESSION_MAX_COUNT = 1000
        
        if self.MCP_SESSION_CLEANUP_INTERVAL < 1:
            print(
                f"Warning: MCP_SESSION_CLEANUP_INTERVAL must be at least 1, got {self.MCP_SESSION_CLEANUP_INTERVAL}. "
                f"Defaulting to 300.",
                file=sys.stderr
            )
            self.MCP_SESSION_CLEANUP_INTERVAL = 300
        
        # If there are any critical errors, raise an exception
        if errors:
            error_message = "\n\n" + "=" * 80 + "\n"
            error_message += "CONFIGURATION ERROR: Missing or invalid mandatory settings\n"
            error_message += "=" * 80 + "\n\n"
            error_message += "The following configuration issues must be fixed:\n\n"
            for i, error in enumerate(errors, 1):
                error_message += f"{i}. {error}\n\n"
            error_message += "=" * 80 + "\n"
            error_message += "Please check your .env file or environment variables.\n"
            error_message += "See .env.example for a complete configuration template.\n"
            error_message += "=" * 80 + "\n"
            
            # Print to stderr for visibility
            print(error_message, file=sys.stderr)
            raise ValueError("Configuration validation failed. See error messages above.")
    
    def _load_object_types(self) -> None:
        """
        Load object types from JSON configuration file
        
        Reads the object_types.json file and populates the OPENPAGES_OBJECT_TYPES
        list with configured object type definitions. Also loads global settings
        like output format.
        
        This method is designed to be non-blocking - if the configuration file
        is missing or invalid, the server will still start with default settings.
        
        Note: Uses sys.stderr for output to avoid polluting stdout in stdio mode.
        """
        import sys
        
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
                    # Use stderr to avoid polluting stdout in stdio mode
                    print(
                        f"WARNING: Object types configuration not found at {self.OBJECT_TYPES_CONFIG_PATH}. "
                        f"Server will start with limited functionality (query tool only).",
                        file=sys.stderr
                    )
                    return
                    
            if not config_path.exists():
                print(
                    f"WARNING: Object types configuration not found at {config_path}. "
                    f"Server will start with limited functionality (query tool only).",
                    file=sys.stderr
                )
                return
                
            # Load the configuration from the file
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    config_data = json.load(f)
                    
                    # Validate that config_data is a dictionary
                    if not isinstance(config_data, dict):
                        print(
                            f"Warning: Object types configuration file must contain a JSON object, got {type(config_data).__name__}. "
                            f"Using default settings.",
                            file=sys.stderr
                        )
                        return
                    
                    # Load object types (with validation)
                    object_types = config_data.get('object_types', [])
                    if isinstance(object_types, list):
                        self.OPENPAGES_OBJECT_TYPES = object_types
                        print(f"Loaded {len(self.OPENPAGES_OBJECT_TYPES)} object types from {config_path}", file=sys.stderr)
                    else:
                        print(
                            f"Warning: 'object_types' in configuration file must be a list, got {type(object_types).__name__}. "
                            f"Using empty list.",
                            file=sys.stderr
                        )
                        self.OPENPAGES_OBJECT_TYPES = []
                    
                    # Load global settings if present
                    global_settings = config_data.get('global_settings', {})
                    
                    if not isinstance(global_settings, dict):
                        print(
                            f"Warning: 'global_settings' in configuration file must be an object, got {type(global_settings).__name__}. "
                            f"Using default global settings.",
                            file=sys.stderr
                        )
                        global_settings = {}
                    
                    # Load output_format from object_types.json (single source of truth)
                    output_format = global_settings.get('output_format', 'json')
                    if output_format in ['json', 'text']:
                        self.OUTPUT_FORMAT = output_format
                        print(f"Loaded global output format: {self.OUTPUT_FORMAT}", file=sys.stderr)
                    else:
                        print(
                            f"Warning: Invalid output_format '{output_format}' in configuration file. "
                            f"Valid options are: json, text. Using default: json",
                            file=sys.stderr
                        )
                        self.OUTPUT_FORMAT = 'json'
                    
                    # Load namespace if present
                    if 'namespace' in global_settings:
                        namespace = global_settings['namespace']
                        if isinstance(namespace, str):
                            self.NAMESPACE = namespace
                            print(f"Loaded global namespace: {self.NAMESPACE}", file=sys.stderr)
                        else:
                            print(
                                f"Warning: 'namespace' in configuration file must be a string, got {type(namespace).__name__}. "
                                f"Using empty namespace.",
                                file=sys.stderr
                            )
                    
                    # Load tool exposure mode if present
                    if 'tool_exposure_mode' in global_settings:
                        tool_mode = global_settings['tool_exposure_mode']
                        valid_modes = ['all', 'ontology_based', 'type_based']
                        if tool_mode in valid_modes:
                            self.TOOL_EXPOSURE_MODE = tool_mode
                            print(f"Loaded tool exposure mode: {self.TOOL_EXPOSURE_MODE}", file=sys.stderr)
                        else:
                            print(
                                f"Warning: Invalid tool_exposure_mode '{tool_mode}' in configuration file. "
                                f"Valid options are: {', '.join(valid_modes)}. Using default: ontology_based",
                                file=sys.stderr
                            )
                    
                except json.JSONDecodeError as e:
                    print(
                        f"Error: Failed to parse object types configuration file as JSON: {e}. "
                        f"Server will start with default settings. "
                        f"Please check the file syntax at: {config_path}",
                        file=sys.stderr
                    )
                except Exception as e:
                    print(
                        f"Error: Unexpected error while reading configuration file: {e}. "
                        f"Server will start with default settings.",
                        file=sys.stderr
                    )
        except Exception as e:
            print(
                f"Error: Failed to load object types configuration: {e}. "
                f"Server will start with default settings.",
                file=sys.stderr
            )

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

