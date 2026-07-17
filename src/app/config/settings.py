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

import base64
import os
import json
import pathlib
from pathlib import Path
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

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
    ENVIRONMENT: str = "dev"  # 'dev' or 'production'
    
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
    OPENPAGES_APIKEY_FILE: Optional[str] = None  # Path to file containing API key
    OPENPAGES_AUTHENTICATION_URL: str = ""
    OPENPAGES_INSTANCE_NAME: str = ""  # For CP4D deployments

    # Cloud provider the server is provisioned on.
    # When set to "aws" the user-presented API key (auth type 4) must be exchanged
    # at an INSTANCE-specific MCSP token endpoint rather than OPENPAGES_AUTHENTICATION_URL
    # (which on AWS Marketplace only accepts service-level keys). See
    # resolve_user_apikey_auth_url(). Empty/anything-else preserves the existing flow.
    CLOUD_PROVIDER: str = ""
    # MCSP IAM base URL used to construct the instance-specific API-key exchange
    # endpoint on AWS Marketplace ({MCSP_IAM_URL}/api/2.0/services/{OPENPAGES_INSTANCE_ID}/apikeys/token).
    MCSP_IAM_URL: str = ""

    # OpenPages instance identification (for RabbitMQ routing key construction)
    OPENPAGES_ACCOUNT_ID: str = ""  # Account ID for routing key (e.g., "999")
    OPENPAGES_INSTANCE_ID: str = ""  # OpenPages instance identifier
    OP_EXT_HOST: str = ""

    # MCP auth posture — the SINGLE explicit axis that drives authentication behavior
    # (see uses_server_credentials()), independent of ENVIRONMENT (boot strategy),
    # SERVER_MODE (transport), and OP topology (which is inferred from the auth URL):
    #   * "user" (default) — production-remote multi-tenant: connection gate active
    #     and the 4-key user-auth framework enforced. Tool calls never fall back to
    #     server creds; server creds are used only for the redeemTicket call. This is
    #     the safe default for SaaS and ticket-issuing Cloud Pak deployments.
    #   * "server" — the MCP server runs on its own credentials: no connection gate,
    #     tool calls fall back to server creds. Opt in explicitly for on-prem /
    #     Cloud Pak agent / local / dev.
    OPENPAGES_AUTH_MODE: str = "user"

    # ── Embedded-chat ticket auth (type 3) + shared 4-type framework ─────────
    # Type-4 API-key header name(s) — a comma-separated list (default "X-Api-Key").
    # Lets different agent deployments carry the key under different headers
    # (first present wins).
    SUPPORTED_APIKEY_AUTH_HEADER_NAMES: str = "X-Api-Key"
    # The op_auth_ticket (type 4) redeem+exchange flow has no enable/disable toggle: it is
    # deployment-driven (a ticket is only ever present when OpenPages issued one — SaaS / Cloud Pak).
    # The internal redeemTicket call targets the OpenPages REST API
    # (OPENPAGES_BASE_URL + "/opgrc/api/v2/token/redeemTicket"), authenticated with server credentials.
    # Shared confidential OAuth client used for the refresh-artifact exchange.
    # The id/secret are mounted onto the pods as secret files (see __init__); direct
    # env vars are honoured as a local/dev fallback. All values are deployment-provided
    # (env / configMap / mounted secret) — no tenant-specific values are hardcoded here.
    OPENPAGES_OAUTH_CLIENT_ID: str = ""                      # APP (confidential) client
    OPENPAGES_OAUTH_CLIENT_SECRET: Optional[SecretStr] = None
    OPENPAGES_OAUTH_CLIENT_ID_FILE: Optional[str] = None
    OPENPAGES_OAUTH_CLIENT_SECRET_FILE: Optional[str] = None
    # API client id / audience (receiver_client_ids for IAM, audience for ISV).
    OPENPAGES_OAUTH_AUDIENCE: str = ""                       # API client / token audience
    # IDP token endpoint for the ticket refresh-artifact exchange. When unset, the
    # exchange falls back to OPENPAGES_AUTHENTICATION_URL (the same IDP in the common
    # IBM Cloud case). The grant flow (IBM Cloud IAM delegated-refresh vs RFC 8693
    # refresh_token) is derived from the resolved URL's type, not from the redeem mode.
    OPENPAGES_USER_IDP_TOKEN_URL: str = ""
    # Token cache / refresh tuning (types 3 & 4, in priority order: ticket=3, api-key=4). Ticket sessions are held in a
    # per-pod in-process cache (no shared store), so each pod redeems independently.
    AUTH_TOKEN_EXP_SKEW_SECONDS: int = 60   # treat tokens as expired this early
    AUTH_TOKEN_CACHE_TTL: int = 3600        # default local cache TTL
    AUTH_TOKEN_CACHE_MAX_SIZE: int = 100    # local cache LRU bound

    # Connection gate: a request is allowed iff a credential is present in a header
    # (Authorization or any configured API-key header). The gate is skipped entirely
    # for server-credential deployments (see uses_server_credentials()). No env toggle
    # — see src/app/auth/channel_auth.py.

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
    
    # Include all object types in schemas (safe default)
    INCLUDE_ALL_OBJECT_TYPES: bool = False  # When True, includes ALL object types from OpenPages, not just configured ones
    
    # Default currency for CURRENCY_TYPE fields (safe default)
    DEFAULT_CURRENCY: str = "USD"  # ISO 4217 currency code
    
    # Path to object types configuration file (safe default)
    OBJECT_TYPES_CONFIG_PATH: str = "src/app/config/object_types.json"
    
    # ── OpenPages Query settings ─────────────────────────────
    OPENPAGES_QUERY_PAGE_SIZE: int = 500  # Batch size for paginated OpenPages queries (max: 50000)

    # Token optimization settings (Phase 2) - with sensible defaults
    # SCHEMA_CACHE_MAX_SIZE: increased from 20 to 200 in 9.2.1. Each cached schema is
    # ~100–500 KB, so 200 entries may consume up to ~100 MB. Lower this value in
    # memory-constrained deployments (e.g. SCHEMA_CACHE_MAX_SIZE=20 to restore the
    # previous footprint).
    SCHEMA_CACHE_MAX_SIZE: int = 200  # Maximum number of schemas to cache (LRU)
    SCHEMA_CACHE_TTL: int = 3600  # Schema cache TTL in seconds (1 hour)
    ENABLE_MINIMAL_SCHEMA_MODE: bool = True  # Enable minimal schema mode by default
    CACHE_QUERY_EXAMPLES: bool = True  # Cache query examples by default

    # MCP session enforcement (Streamable HTTP transport, spec 2025-03-26)
    # Default to False to allow clients that do not support session headers
    MCP_SESSION_ENFORCEMENT: bool = False

    # Connect-time OpenPages access verification: at `initialize`, resolve the
    # transport credential and probe GET /api/v2/types so a caller that OpenPages
    # would reject cannot establish a session. Only active in user-auth mode.
    MCP_VERIFY_ACCESS_ON_CONNECT: bool = True

    # MCP session management settings (with sensible defaults)
    MCP_SESSION_TTL: int = 3600  # Session TTL in seconds (1 hour)
    MCP_SESSION_MAX_COUNT: int = 1000  # Maximum number of concurrent sessions
    MCP_SESSION_CLEANUP_INTERVAL: int = 300  # Cleanup task interval in seconds (5 minutes)
    
    # Secrets path for SaaS deployments (file-based credentials)
    SECRETS_PATH: str = os.getenv("SECRETS_PATH", "/secrets/store")
    
    # RabbitMQ configuration for SaaS schema synchronization (optional)
    RABBITMQ_ENABLED: bool = False  # Enable RabbitMQ-based schema sync
    RABBITMQ_HOST: Optional[str] = None  # RabbitMQ host
    RABBITMQ_PORT: int = 5671  # RabbitMQ port (default AMQPS)
    RABBITMQ_USER: Optional[str] = None  # RabbitMQ username (renamed from RABBITMQ_USERNAME)
    RABBITMQ_PASSWORD: Optional[str] = None  # RabbitMQ password
    RABBITMQ_METADATA_EXCHANGE: str = "op.public.metadata"  # Exchange name for metadata events
    RABBITMQ_USE_SSL: bool = True  # Use SSL/TLS for RabbitMQ connection
    RABBITMQ_VIRTUAL_HOST: str = "/"  # RabbitMQ virtual host
    MCP_SERVER_DEPLOYMENT_NAME: str = "mcp-server"  # MCP server deployment name prefix for queue naming
    SCHEMA_UPDATE_INTERVAL: int = 60  # Interval in seconds for processing schema updates
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from environment
    )
    
    @staticmethod
    def _read_mounted_secret(file_path: Optional[str], already_set: bool) -> Optional[str]:
        """
        Read a secret value from an explicitly configured mounted file.

        Used for the shared OAuth client id/secret. Honors only an explicit ``file_path``;
        no default path is assumed. If neither a direct value nor an explicit file is
        configured, the value stays unset (and the exchange path fails fast when it needs it).

        Args:
            file_path: Explicit path from settings (may be None).
            already_set: If True, a direct value is already configured; skip the file.

        Returns:
            The trimmed secret value, or None if not available.
        """
        if already_set or not file_path:
            return None

        try:
            secret_path = pathlib.Path(file_path)
            if not secret_path.exists():
                logger.debug(f"Mounted secret file not found: {file_path}")
                return None
            value = secret_path.read_text().strip()
            if not value:
                logger.debug(f"Mounted secret file is empty: {file_path}")
                return None
            logger.info(f"Loaded mounted secret from file: {file_path}")
            return value
        except Exception as e:  # noqa: BLE001 - never block startup on a secret read
            logger.debug(f"Failed to read mounted secret from {file_path}: {e}")
            return None

    def get_apikey_header_names(self) -> list:
        """Configured API-key header name(s), in priority order (first present wins).

        ``SUPPORTED_APIKEY_AUTH_HEADER_NAMES`` is a comma-separated list so different agent
        deployments may carry the API key under different header names. Falls back to
        the default ``X-Api-Key`` when unset/empty.
        """
        names = [h.strip() for h in self.SUPPORTED_APIKEY_AUTH_HEADER_NAMES.split(",") if h.strip()]
        return names or ["X-Api-Key"]

    def resolve_user_apikey_auth_url(self) -> str:
        """Token endpoint for exchanging a *user-presented* API key (auth type 4).

        On AWS Marketplace (``CLOUD_PROVIDER=aws``) the shared
        ``OPENPAGES_AUTHENTICATION_URL`` only accepts service-level keys, so a user's
        key passed in the API-key header (at initialize or per tool call) must be
        exchanged at the INSTANCE-specific MCSP endpoint:

            {MCSP_IAM_URL}/api/2.0/services/{OPENPAGES_INSTANCE_ID}/apikeys/token

        Every other environment (and the internal MCP→OpenPages call that exchanges
        the server's ``OPENPAGES_APIKEY``) continues to use
        ``OPENPAGES_AUTHENTICATION_URL`` unchanged.

        Raises:
            ValueError: On AWS when MCSP_IAM_URL or OPENPAGES_INSTANCE_ID is missing
                (fail-fast rather than building a malformed endpoint).
        """
        if self.CLOUD_PROVIDER.strip().lower() == "aws":
            base = self.MCSP_IAM_URL.strip().rstrip("/")
            instance_id = self.OPENPAGES_INSTANCE_ID.strip()
            missing = [
                name
                for name, value in (("MCSP_IAM_URL", base), ("OPENPAGES_INSTANCE_ID", instance_id))
                if not value
            ]
            if missing:
                raise ValueError(
                    f"CLOUD_PROVIDER=aws requires {' and '.join(missing)} to build the "
                    f"instance-specific API-key token endpoint, but "
                    f"{'it is' if len(missing) == 1 else 'they are'} unset."
                )
            return f"{base}/api/2.0/services/{instance_id}/apikeys/token"
        return self.OPENPAGES_AUTHENTICATION_URL

    def uses_server_credentials(self) -> bool:
        """Whether this deployment runs entirely on the server's own credentials.

        Auth posture is driven solely by OPENPAGES_AUTH_MODE, independent of
        ENVIRONMENT (boot strategy), SERVER_MODE (transport), and OP topology:
          * "user" (default) — production-remote multi-tenant: connection gate active
            and the 4-key user-auth framework enforced; no server-cred fallback.
          * "server" — no connection gate; tool calls fall back to server credentials.

        Default is "user" (safe by default); server-credential mode must opt in with
        OPENPAGES_AUTH_MODE=server (on-prem / Cloud Pak agent / local / dev).
        """
        return self.OPENPAGES_AUTH_MODE.strip().lower() != "user"

    def verify_access_on_connect_active(self) -> bool:
        """Whether the connect-time OpenPages access probe runs.

        Active only in user-auth mode (where per-user credentials flow) and when
        MCP_VERIFY_ACCESS_ON_CONNECT is enabled. Server-credential deployments
        (dev / local / on-prem) run everything on the server's own creds and skip it.
        """
        return self.MCP_VERIFY_ACCESS_ON_CONNECT and not self.uses_server_credentials()

    def session_enforcement_effective(self) -> bool:
        """Whether Mcp-Session-Id is enforced on non-initialize requests.

        Enforced if explicitly enabled OR implied by connect-time verification:
        without session enforcement a client could skip `initialize` and call tools
        directly, bypassing the connect-time access probe.
        """
        return self.MCP_SESSION_ENFORCEMENT or self.verify_access_on_connect_active()

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
        
        # Read API key from file if path is provided and API key is not already set
        if self.OPENPAGES_APIKEY_FILE and not self.OPENPAGES_APIKEY:
            try:
                api_key_path = pathlib.Path(self.OPENPAGES_APIKEY_FILE)
                if not api_key_path.exists():
                    raise FileNotFoundError(f"API key file not found: {self.OPENPAGES_APIKEY_FILE}")
                
                with open(api_key_path, 'r') as f:
                    self.OPENPAGES_APIKEY = f.read().strip()
                
                if not self.OPENPAGES_APIKEY:
                    raise ValueError(f"API key file is empty: {self.OPENPAGES_APIKEY_FILE}")
                    
                # Log that we loaded from file (mask the key)
   
                logger.info(f"Loaded API key from file: {self.OPENPAGES_APIKEY_FILE}")
                
            except Exception as e:
                raise ValueError(f"Failed to read API key from {self.OPENPAGES_APIKEY_FILE}: {e}") from e

        # Read the shared OAuth client id/secret from an explicitly configured mounted
        # secret file (*_FILE). No default path is assumed; a direct env value takes
        # precedence. Left unset when neither is provided.
        client_id = self._read_mounted_secret(
            self.OPENPAGES_OAUTH_CLIENT_ID_FILE,
            already_set=bool(self.OPENPAGES_OAUTH_CLIENT_ID),
        )
        if client_id:
            self.OPENPAGES_OAUTH_CLIENT_ID = client_id

        if not self.OPENPAGES_OAUTH_CLIENT_SECRET:
            client_secret = self._read_mounted_secret(
                self.OPENPAGES_OAUTH_CLIENT_SECRET_FILE,
                already_set=False,
            )
            if client_secret:
                self.OPENPAGES_OAUTH_CLIENT_SECRET = SecretStr(client_secret)

        # Process base URL to ensure it has the correct protocol
        if self.OPENPAGES_BASE_URL and not (self.OPENPAGES_BASE_URL.startswith('http://') or self.OPENPAGES_BASE_URL.startswith('https://')):
            self.OPENPAGES_BASE_URL = f"https://{self.OPENPAGES_BASE_URL}"
        
        # Load RabbitMQ credentials (from env vars or SaaS secret files)
        self._load_rabbitmq_credentials()
        
        # Load object types from JSON file (non-blocking)
        self._load_object_types()
        
        # Validate mandatory settings
        self._validate_settings()
    
    def _read_secret_file(self, filename: str) -> Optional[str]:
        """
        Read a plain text secret file from SECRETS_PATH.
        
        Args:
            filename: Name of the secret file to read (e.g., 'RABBITMQ_HOST')
            
        Returns:
            Secret value or None if file doesn't exist or read fails
        """
        file_path = None
        try:
            file_path = Path(self.SECRETS_PATH) / filename
            if file_path.exists():
                content = file_path.read_text().strip()
                
                # Basic validation - ensure not empty
                if not content:
                    raise ValueError("Secret file is empty")
                
                return content
        except Exception as e:
            logger.warning("Failed to read secret file %s: %s: %s", file_path, type(e).__name__, e)
        return None
    
    def _load_rabbitmq_credentials(self) -> None:
        """
        Load RabbitMQ credentials from environment variables or secret files.
        
        For SaaS deployments, credentials are read from base64-encoded files
        in SECRETS_PATH when environment variables are not available.
        
        Priority:
        1. Environment variables (RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD)
        2. Secret files in SECRETS_PATH (for SaaS deployments)
        
        Note: Pydantic BaseSettings automatically loads environment variables into fields,
        but we need to explicitly check and load from files for SaaS deployments.
        """
        # Check if environment variables are already loaded by Pydantic
        # If not set, try reading from secret files (SaaS mode)
        if not self.RABBITMQ_HOST:
            host = self._read_secret_file("RABBITMQ_HOST")
            if host:
                self.RABBITMQ_HOST = host
                logger.debug("Loaded RABBITMQ_HOST from secret file")
        
        # For port, check if it's still the default value and no env var was set
        if self.RABBITMQ_PORT == 5671 and not os.getenv("RABBITMQ_PORT"):
            port_str = self._read_secret_file("RABBITMQ_PORT")
            if port_str:
                try:
                    self.RABBITMQ_PORT = int(port_str)
                    logger.debug("Loaded RABBITMQ_PORT from secret file")
                except ValueError:
                    logger.warning("Invalid port value in RABBITMQ_PORT secret file: %s", port_str)
        
        if not self.RABBITMQ_USER:
            user = self._read_secret_file("RABBITMQ_USER")
            if user:
                self.RABBITMQ_USER = user
                logger.debug("Loaded RABBITMQ_USER from secret file")
        
        if not self.RABBITMQ_PASSWORD:
            password = self._read_secret_file("RABBITMQ_PASSWORD")
            if password:
                self.RABBITMQ_PASSWORD = password
                logger.debug("Loaded RABBITMQ_PASSWORD from secret file")
    
    def get_rabbitmq_routing_key(self) -> str:
        """
        Construct RabbitMQ routing key from OpenPages account and instance IDs.
        
        Format: v1.account.{OPENPAGES_ACCOUNT_ID}.instance.{OPENPAGES_INSTANCE_ID}.#
        
        Returns:
            Constructed routing key string
            
        Raises:
            ValueError: If OPENPAGES_ACCOUNT_ID or OPENPAGES_INSTANCE_ID is not set
        """
        if not self.OPENPAGES_ACCOUNT_ID:
            raise ValueError(
                "OPENPAGES_ACCOUNT_ID is required for RabbitMQ routing key construction. "
                "Please set it in your .env file."
            )
        
        if not self.OPENPAGES_INSTANCE_ID:
            raise ValueError(
                "OPENPAGES_INSTANCE_ID is required for RabbitMQ routing key construction. "
                "Please set it in your .env file."
            )
        
        return f"v1.account.{self.OPENPAGES_ACCOUNT_ID}.instance.{self.OPENPAGES_INSTANCE_ID}.#"
    
    def _validate_settings(self) -> None:
        """
        Validate mandatory settings and provide helpful error messages.
        
        This method checks that all required configuration is present for the server
        to function properly. It provides clear error messages to help users fix
        configuration issues.
        
        Raises:
            ValueError: If mandatory settings are missing or invalid
        """
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
                '/icp4d-api/v1/authorize' in self.OPENPAGES_AUTHENTICATION_URL
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
            logger.warning(
                "LOG_LEVEL '%s' is not valid. Valid options are: %s. Defaulting to INFO.",
                self.LOG_LEVEL, ", ".join(valid_log_levels)
            )
            self.LOG_LEVEL = "INFO"
        
        # Validate log format
        if self.LOG_FORMAT not in ["json", "text"]:
            logger.warning(
                "LOG_FORMAT '%s' is not valid. Valid options are: json, text. Defaulting to json.",
                self.LOG_FORMAT
            )
            self.LOG_FORMAT = "json"
        
        # Validate server mode
        if self.SERVER_MODE not in ["remote", "local"]:
            logger.warning(
                "SERVER_MODE '%s' is not valid. Valid options are: remote, local. Defaulting to remote.",
                self.SERVER_MODE
            )
            self.SERVER_MODE = "remote"
        
        # Validate tool exposure mode
        valid_exposure_modes = ["all", "ontology_based", "type_based"]
        if self.TOOL_EXPOSURE_MODE not in valid_exposure_modes:
            logger.warning(
                "TOOL_EXPOSURE_MODE '%s' is not valid. Valid options are: %s. Defaulting to ontology_based.",
                self.TOOL_EXPOSURE_MODE, ", ".join(valid_exposure_modes)
            )
            self.TOOL_EXPOSURE_MODE = "ontology_based"
        
        # Validate numeric settings have reasonable values
        if self.RATE_LIMIT_REQUESTS_PER_MINUTE < 1:
            logger.warning(
                "RATE_LIMIT_REQUESTS_PER_MINUTE must be at least 1, got %d. Defaulting to 60.",
                self.RATE_LIMIT_REQUESTS_PER_MINUTE
            )
            self.RATE_LIMIT_REQUESTS_PER_MINUTE = 60
        
        if self.RATE_LIMIT_BURST_SIZE < 1:
            logger.warning(
                "RATE_LIMIT_BURST_SIZE must be at least 1, got %d. Defaulting to 10.",
                self.RATE_LIMIT_BURST_SIZE
            )
            self.RATE_LIMIT_BURST_SIZE = 10
        
        if self.SCHEMA_CACHE_MAX_SIZE < 1:
            logger.warning(
                "SCHEMA_CACHE_MAX_SIZE must be at least 1, got %d. Defaulting to 200.",
                self.SCHEMA_CACHE_MAX_SIZE
            )
            self.SCHEMA_CACHE_MAX_SIZE = 200
        
        if self.SCHEMA_CACHE_TTL < 0:
            logger.warning(
                "SCHEMA_CACHE_TTL must be non-negative, got %d. Defaulting to 3600.",
                self.SCHEMA_CACHE_TTL
            )
            self.SCHEMA_CACHE_TTL = 3600
        
        if self.MCP_SESSION_TTL < 1:
            logger.warning(
                "MCP_SESSION_TTL must be at least 1, got %d. Defaulting to 3600.",
                self.MCP_SESSION_TTL
            )
            self.MCP_SESSION_TTL = 3600
        
        if self.MCP_SESSION_MAX_COUNT < 1:
            logger.warning(
                "MCP_SESSION_MAX_COUNT must be at least 1, got %d. Defaulting to 1000.",
                self.MCP_SESSION_MAX_COUNT
            )
            self.MCP_SESSION_MAX_COUNT = 1000
        
        if self.MCP_SESSION_CLEANUP_INTERVAL < 1:
            logger.warning(
                "MCP_SESSION_CLEANUP_INTERVAL must be at least 1, got %d. Defaulting to 300.",
                self.MCP_SESSION_CLEANUP_INTERVAL
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
            
            logger.error(error_message)
            raise ValueError("Configuration validation failed. See error messages above.")
    
    def _load_object_types(self) -> None:
        """
        Load object types from JSON configuration file

        Reads the object_types.json file and populates the OPENPAGES_OBJECT_TYPES
        list with configured object type definitions. Also loads global settings
        like output format.

        This method is designed to be non-blocking - if the configuration file
        is missing or invalid, the server will still start with default settings.
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
                    logger.warning(
                        "Object types configuration not found at %s. "
                        "Server will start with limited functionality (query tool only).",
                        self.OBJECT_TYPES_CONFIG_PATH
                    )
                    return
                    
            if not config_path.exists():
                logger.warning(
                    "Object types configuration not found at %s. "
                    "Server will start with limited functionality (query tool only).",
                    config_path
                )
                return
                
            # Load the configuration from the file
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    config_data = json.load(f)
                    
                    # Validate that config_data is a dictionary
                    if not isinstance(config_data, dict):
                        logger.warning(
                            "Object types configuration file must contain a JSON object, got %s. "
                            "Using default settings.",
                            type(config_data).__name__
                        )
                        return
                    
                    # Load object types (with validation)
                    object_types = config_data.get('object_types', [])
                    if isinstance(object_types, list):
                        self.OPENPAGES_OBJECT_TYPES = object_types
                        logger.debug("Loaded %d object types from %s", len(self.OPENPAGES_OBJECT_TYPES), config_path)
                    else:
                        logger.warning(
                            "'object_types' in configuration file must be a list, got %s. Using empty list.",
                            type(object_types).__name__
                        )
                        self.OPENPAGES_OBJECT_TYPES = []
                    
                    # Load global settings if present
                    global_settings = config_data.get('global_settings', {})
                    
                    if not isinstance(global_settings, dict):
                        logger.warning(
                            "'global_settings' in configuration file must be an object, got %s. "
                            "Using default global settings.",
                            type(global_settings).__name__
                        )
                        global_settings = {}
                    
                    # Load output_format from object_types.json (single source of truth)
                    output_format = global_settings.get('output_format', 'json')
                    if output_format in ['json', 'text']:
                        self.OUTPUT_FORMAT = output_format
                        logger.debug("Loaded global output format: %s", self.OUTPUT_FORMAT)
                    else:
                        logger.warning(
                            "Invalid output_format '%s' in configuration file. "
                            "Valid options are: json, text. Using default: json",
                            output_format
                        )
                        self.OUTPUT_FORMAT = 'json'
                    
                    # Load namespace if present
                    if 'namespace' in global_settings:
                        namespace = global_settings['namespace']
                        if isinstance(namespace, str):
                            self.NAMESPACE = namespace
                            logger.debug("Loaded global namespace: %s", self.NAMESPACE)
                        else:
                            logger.warning(
                                "'namespace' in configuration file must be a string, got %s. "
                                "Using empty namespace.",
                                type(namespace).__name__
                            )
                    
                    # Load tool exposure mode if present
                    if 'tool_exposure_mode' in global_settings:
                        tool_mode = global_settings['tool_exposure_mode']
                        valid_modes = ['all', 'ontology_based', 'type_based']
                        if tool_mode in valid_modes:
                            self.TOOL_EXPOSURE_MODE = tool_mode
                            logger.debug("Loaded tool exposure mode: %s", self.TOOL_EXPOSURE_MODE)
                        else:
                            logger.warning(
                                "Invalid tool_exposure_mode '%s' in configuration file. "
                                "Valid options are: %s. Using default: ontology_based",
                                tool_mode, ", ".join(valid_modes)
                            )
                    
                    # Load include_all_object_types if present
                    if 'include_all_object_types' in global_settings:
                        include_all = global_settings['include_all_object_types']
                        if isinstance(include_all, bool):
                            self.INCLUDE_ALL_OBJECT_TYPES = include_all
                            logger.debug("Loaded include_all_object_types: %s", self.INCLUDE_ALL_OBJECT_TYPES)
                        else:
                            logger.warning(
                                "'include_all_object_types' in configuration file must be a boolean, got %s. "
                                "Using default: False",
                                type(include_all).__name__
                            )
                    
                except json.JSONDecodeError as e:
                    logger.error(
                        "Failed to parse object types configuration file as JSON: %s. "
                        "Server will start with default settings. "
                        "Please check the file syntax at: %s",
                        e, config_path
                    )
                except Exception as e:
                    logger.error(
                        "Unexpected error while reading configuration file: %s. "
                        "Server will start with default settings.",
                        e
                    )
        except Exception as e:
            logger.error(
                "Failed to load object types configuration: %s. "
                "Server will start with default settings.",
                e
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

