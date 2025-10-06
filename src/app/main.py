#!/usr/bin/env python3
"""
GRC MCP Server - Main Application
This server provides MCP tools to interact with IBM OpenPages GRC platform via HTTP
"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.app.api.router import router as api_router
from src.app.config.settings import settings
from src.app.core.server_instance import initialize_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    import uvicorn
    
    uvicorn.run(
        "src.app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.DEBUG
    )

# Made with Bob
