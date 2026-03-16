#!/usr/bin/env python3
"""
GRC MCP Server - Main Application
This server provides MCP tools to interact with IBM OpenPages GRC platform
Supports both remote (HTTP) and local (stdio) modes
"""

import os
import argparse
import sys

# Only append /app path when running in Docker
if os.path.exists('/app'):
    sys.path.append('/app')

from src.app.config.settings import settings
from src.app.observability.logger import setup_logging, get_logger

# Setup structured logging for remote mode (default)
# This will be reconfigured in local mode to use stderr
setup_logging(
    level=settings.LOG_LEVEL,
    service_name=settings.APP_NAME,
    json_format=(settings.LOG_FORMAT == "json"),
    log_file=settings.LOG_FILE,
    use_stderr=False,  # Remote mode uses stdout
    log_max_bytes=settings.LOG_MAX_BYTES,
    log_backup_count=settings.LOG_BACKUP_COUNT,
)

logger = get_logger(__name__)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="GRC MCP Server")
    parser.add_argument(
        "--mode",
        choices=["remote", "local"],
        default=settings.SERVER_MODE,
        help="Server mode: remote (HTTP) or local (stdio)"
    )
    parser.add_argument(
        "--host",
        default=settings.HOST,
        help="Host to bind the server to (remote mode only)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.PORT,
        help="Port to bind the server to (remote mode only)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=settings.DEBUG,
        help="Enable debug mode"
    )
    
    return parser.parse_args()

def create_remote_app():
    """Create and configure FastAPI application for remote mode"""
    # Import FastAPI dependencies only when needed for remote mode
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from contextlib import asynccontextmanager
    from src.app.mcp.remote.http_router import router as mcp_router
    from src.app.api.health import health_router
    from src.app.api.metrics import metrics_router
    from src.app.observability.tracing import setup_tracing, instrument_fastapi_app
    from src.app.observability.metrics import setup_metrics
    from src.app.observability.middleware import (
        RateLimitMiddleware,
        ObservabilityMiddleware,
    )
    
    # Setup tracing BEFORE creating the app
    if settings.OBSERVABILITY_ENABLED and settings.TRACING_ENABLED:
        setup_tracing(
            service_name=settings.APP_NAME,
            otlp_endpoint=settings.OTLP_ENDPOINT,
            console_export=settings.CONSOLE_TRACING,
            enabled=True,
        )
        logger.info("Tracing setup completed")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialize MCP server and observability on startup"""
        # Import session management functions (only needed in remote mode)
        from src.app.mcp.remote.http_router import (
            start_cleanup_task,
            stop_cleanup_task,
            clear_all_sessions
        )
        
        logger.info("Starting GRC MCP Server")
        
        # Clear any stale session data from previous runs
        clear_all_sessions()
        
        # Setup metrics
        if settings.OBSERVABILITY_ENABLED and settings.METRICS_ENABLED:
            setup_metrics(
                enabled=True,
                service_name=settings.APP_NAME,
                service_version="1.0.0",
            )
            logger.info("Metrics collection enabled")
        
        # Initialize the MCP server using the singleton pattern (async version)
        from src.app.mcp.remote.server_instance import initialize_server_async
        await initialize_server_async()
        logger.info("MCP Server initialized")
        
        # Start background session cleanup task
        await start_cleanup_task()

        yield
        
        # Stop background cleanup task
        await stop_cleanup_task()
        
        # Close the shared httpx client to release connections
        from src.app.mcp.remote.server_instance import get_server
        server = get_server()
        if server and hasattr(server, 'client') and server.client:
            await server.client.close()
        
        # Clear all sessions on shutdown
        clear_all_sessions()

        logger.info("Shutting down GRC MCP Server")

    # Create FastAPI application
    app = FastAPI(
        title="GRC MCP Server",
        description="MCP Server for IBM OpenPages GRC platform",
        version="1.0.0",
        lifespan=lifespan
    )

    # Instrument FastAPI app AFTER creation but BEFORE adding middleware
    if settings.OBSERVABILITY_ENABLED and settings.TRACING_ENABLED:
        instrument_fastapi_app(app)
        logger.info("FastAPI instrumentation completed")

    # Add observability middleware (order matters - add in reverse order of execution)
    if settings.OBSERVABILITY_ENABLED:
        # Add observability middleware first (executes last)
        app.add_middleware(ObservabilityMiddleware)
        
        # Add rate limiting middleware
        if settings.RATE_LIMIT_ENABLED:
            app.add_middleware(
                RateLimitMiddleware,
                requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                burst_size=settings.RATE_LIMIT_BURST_SIZE,
                enabled=True,
            )
            logger.info(
                f"Rate limiting enabled: {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} req/min, "
                f"burst={settings.RATE_LIMIT_BURST_SIZE}"
            )

    # Add CORS middleware (executes first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # Include API routers
    app.include_router(mcp_router)
    app.include_router(health_router)
    app.include_router(metrics_router)

    @app.get("/")
    async def root():
        """Root endpoint - simple status check"""
        return {
            "status": "GRC MCP Server is running",
            "version": "1.0.0",
            "health_endpoints": {
                "comprehensive": "/health",
                "readiness": "/health/ready",
                "liveness": "/health/live",
                "startup": "/health/startup",
                "simple": "/healthz"
            }
        }
    
    return app

# Create the FastAPI app at module level for uvicorn to import
# This is only created when not in local mode
# Note: We delay creation until actually needed to avoid importing
# remote-mode dependencies when running in local mode
app = None

def get_app():
    """Lazy app creation - only create when actually needed"""
    global app
    if app is None and os.getenv("SERVER_MODE", settings.SERVER_MODE) != "local":
        app = create_remote_app()
    return app

# For uvicorn to import: uvicorn main:app
# This will trigger lazy creation on first access
if os.getenv("SERVER_MODE", settings.SERVER_MODE) != "local":
    app = get_app()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Update settings based on command line arguments
    settings.SERVER_MODE = args.mode
    settings.HOST = args.host
    settings.PORT = args.port
    settings.DEBUG = args.debug
    
    # Run in appropriate mode
    if args.mode == "local":
        # Import local runner only when needed
        from src.app.mcp.local.runner import run_local_server
        
        # Reconfigure logging for local mode to use stderr (CRITICAL for stdio protocol)
        setup_logging(
            level="DEBUG" if args.debug else settings.LOG_LEVEL,
            service_name=settings.APP_NAME,
            json_format=(settings.LOG_FORMAT == "json"),
            log_file=None,  # Disable file logging in local mode to avoid path issues
            use_stderr=True,  # Local mode MUST use stderr
            log_max_bytes=settings.LOG_MAX_BYTES,
            log_backup_count=settings.LOG_BACKUP_COUNT,
        )
        # Run local MCP server with stdio transport
        run_local_server(debug_mode=args.debug)
    else:
        # Import uvicorn only when needed for remote mode
        import uvicorn
        
        # Reconfigure logging for remote mode if --debug flag is set
        if args.debug:
            setup_logging(
                level="DEBUG",
                service_name=settings.APP_NAME,
                json_format=(settings.LOG_FORMAT == "json"),
                log_file=settings.LOG_FILE,
                use_stderr=False,  # Remote mode uses stdout
                log_max_bytes=settings.LOG_MAX_BYTES,
                log_backup_count=settings.LOG_BACKUP_COUNT,
            )
            logger.info("Debug mode enabled via command line flag")
        
        # Create the FastAPI app (or get existing one)
        app = get_app() if app is None else app
        
        # Run remote MCP server with HTTP
        logger.info(f"Starting remote MCP server on {args.host}:{args.port}")
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=settings.DEBUG
        )

# Made with Bob
