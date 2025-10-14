#!/usr/bin/env python3
"""
GRC MCP Server - Main Application
This server provides MCP tools to interact with IBM OpenPages GRC platform
Supports both remote (HTTP) and local (stdio) modes
"""

import logging
import os
import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import modules with explicit paths
import sys
# Only append /app path when running in Docker
if os.path.exists('/app'):
    sys.path.append('/app')

from src.app.api.router import router as api_router
from src.app.config.settings import settings
from src.app.core.server_instance import initialize_server, run_local_server

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP server on startup"""
    # Initialize the MCP server using the singleton pattern
    initialize_server()
    
    yield
    
    logger.info("Shutting down MCP Server")

# Create FastAPI application
app = FastAPI(
    title="GRC MCP Server",
    description="MCP Server for IBM OpenPages GRC platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Include API router
app.include_router(api_router)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "GRC MCP Server is running"}

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
        # Run local MCP server with stdio transport
        logger.info("Starting local MCP server with stdio transport")
        run_local_server()
    else:
        # Run remote MCP server with HTTP
        logger.info(f"Starting remote MCP server on {args.host}:{args.port}")
        import uvicorn
        
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=settings.DEBUG
        )

# Made with Bob
