"""
Health Check Module
Provides comprehensive health checks for the MCP server
Works for both containerized and native Python deployments
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Response, status

logger = logging.getLogger(__name__)

# Create router for health endpoints
health_router = APIRouter(tags=["health"])

# Track server start time
_server_start_time = time.time()


class HealthChecker:
    """
    Health checker for MCP server components
    
    Provides detailed health status for:
    - Server availability
    - OpenPages connectivity
    - MCP server initialization
    - Dynamic schema loading
    """
    
    def __init__(self):
        """Initialize health checker"""
        self.last_check_time: Optional[float] = None
        self.last_check_result: Optional[Dict[str, Any]] = None
        self.cache_duration = 5  # Cache health check results for 5 seconds
    
    async def check_server_health(self, mcp_server=None) -> Dict[str, Any]:
        """
        Perform comprehensive health check
        
        Args:
            mcp_server: Optional MCP server instance to check
            
        Returns:
            Dict containing health status and details
        """
        # Check if we have a cached result
        current_time = time.time()
        if (self.last_check_time and 
            self.last_check_result and 
            (current_time - self.last_check_time) < self.cache_duration):
            logger.debug("Returning cached health check result")
            return self.last_check_result
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": int(current_time - _server_start_time),
            "checks": {}
        }
        
        # Check 1: Server is running
        health_status["checks"]["server"] = {
            "status": "healthy",
            "message": "Server is running"
        }
        
        # Check 2: MCP Server initialization
        if mcp_server:
            try:
                # Check if MCP server is initialized
                if hasattr(mcp_server, 'client') and mcp_server.client:
                    health_status["checks"]["mcp_server"] = {
                        "status": "healthy",
                        "message": "MCP server initialized"
                    }
                    
                    # Check if dynamic schemas are loaded
                    if hasattr(mcp_server, 'dynamic_schemas_loaded'):
                        if mcp_server.dynamic_schemas_loaded:
                            health_status["checks"]["dynamic_schemas"] = {
                                "status": "healthy",
                                "message": "Dynamic schemas loaded"
                            }
                        else:
                            health_status["checks"]["dynamic_schemas"] = {
                                "status": "warning",
                                "message": "Dynamic schemas not yet loaded"
                            }
                            health_status["status"] = "degraded"
                    
                    # Check tool count
                    if hasattr(mcp_server, 'tools'):
                        tool_count = len(mcp_server.tools)
                        health_status["checks"]["tools"] = {
                            "status": "healthy",
                            "message": f"{tool_count} tools available",
                            "count": tool_count
                        }
                else:
                    health_status["checks"]["mcp_server"] = {
                        "status": "unhealthy",
                        "message": "MCP server not initialized"
                    }
                    health_status["status"] = "unhealthy"
            except Exception as e:
                logger.error(f"Error checking MCP server health: {e}")
                health_status["checks"]["mcp_server"] = {
                    "status": "unhealthy",
                    "message": f"Error: {str(e)}"
                }
                health_status["status"] = "unhealthy"
        else:
            health_status["checks"]["mcp_server"] = {
                "status": "warning",
                "message": "MCP server instance not available for health check"
            }
            health_status["status"] = "degraded"
        
        # Check 3: OpenPages connectivity (optional, only if we can test it)
        if mcp_server and hasattr(mcp_server, 'client'):
            try:
                # We don't actually ping OpenPages here to avoid overhead
                # Just check if client is configured
                if mcp_server.client.base_url:
                    health_status["checks"]["openpages_config"] = {
                        "status": "healthy",
                        "message": "OpenPages client configured",
                        "base_url": mcp_server.client.base_url
                    }
                else:
                    health_status["checks"]["openpages_config"] = {
                        "status": "warning",
                        "message": "OpenPages base URL not configured"
                    }
                    health_status["status"] = "degraded"
            except Exception as e:
                logger.error(f"Error checking OpenPages config: {e}")
                health_status["checks"]["openpages_config"] = {
                    "status": "warning",
                    "message": f"Could not check OpenPages config: {str(e)}"
                }
        
        # Cache the result
        self.last_check_time = current_time
        self.last_check_result = health_status
        
        return health_status
    
    async def check_readiness(self, mcp_server=None) -> Dict[str, Any]:
        """
        Check if server is ready to accept requests
        
        Args:
            mcp_server: Optional MCP server instance to check
            
        Returns:
            Dict containing readiness status
        """
        readiness = {
            "ready": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {}
        }
        
        # Check if MCP server is initialized
        if mcp_server:
            if hasattr(mcp_server, 'client') and mcp_server.client:
                readiness["checks"]["mcp_server"] = {
                    "ready": True,
                    "message": "MCP server initialized"
                }
            else:
                readiness["checks"]["mcp_server"] = {
                    "ready": False,
                    "message": "MCP server not initialized"
                }
                readiness["ready"] = False
        else:
            readiness["checks"]["mcp_server"] = {
                "ready": False,
                "message": "MCP server not available"
            }
            readiness["ready"] = False
        
        return readiness
    
    async def check_liveness(self) -> Dict[str, Any]:
        """
        Check if server is alive (basic liveness probe)
        
        Returns:
            Dict containing liveness status
        """
        return {
            "alive": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": int(time.time() - _server_start_time)
        }


# Create global health checker instance
health_checker = HealthChecker()


# Health check endpoints
@health_router.get("/health", summary="Comprehensive health check")
async def health_check(response: Response):
    """
    Comprehensive health check endpoint
    
    Returns detailed health status including:
    - Server status
    - MCP server initialization
    - Dynamic schema loading
    - Tool availability
    - OpenPages configuration
    
    Status codes:
    - 200: Healthy
    - 503: Unhealthy or degraded
    """
    from src.app.mcp.remote.server_instance import get_server
    
    mcp_server = get_server()
    health_status = await health_checker.check_server_health(mcp_server)
    
    # Set appropriate status code
    if health_status["status"] == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif health_status["status"] == "degraded":
        response.status_code = status.HTTP_200_OK  # Still return 200 for degraded
    
    return health_status


@health_router.get("/health/ready", summary="Readiness probe")
async def readiness_check(response: Response):
    """
    Readiness probe endpoint
    
    Checks if the server is ready to accept requests.
    Returns 200 if ready, 503 if not ready.
    
    Use this for:
    - Load balancer health checks
    - Container orchestration readiness checks
    - Determining if server can handle traffic
    """
    from src.app.mcp.remote.server_instance import get_server
    
    mcp_server = get_server()
    readiness = await health_checker.check_readiness(mcp_server)
    
    if not readiness["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return readiness


@health_router.get("/health/live", summary="Liveness probe")
async def liveness_check():
    """
    Liveness probe endpoint
    
    Simple check to verify the server process is alive.
    Always returns 200 if the server is running.
    
    Use this for:
    - Container orchestration liveness checks
    - Process monitoring
    - Restart triggers
    """
    return await health_checker.check_liveness()


@health_router.get("/health/startup", summary="Startup probe")
async def startup_check(response: Response):
    """
    Startup probe endpoint
    
    Checks if the server has completed initialization.
    Returns 200 once startup is complete, 503 during startup.
    
    Use this for:
    - Container orchestration startup checks
    - Delayed health checks during initialization
    """
    from src.app.mcp.remote.server_instance import get_server
    
    mcp_server = get_server()
    
    if mcp_server and hasattr(mcp_server, 'client') and mcp_server.client:
        return {
            "started": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Server startup complete"
        }
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "started": False,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Server still starting up"
        }


# Simple health check (backward compatible)
@health_router.get("/healthz", summary="Simple health check")
async def simple_health():
    """
    Simple health check endpoint (backward compatible)
    
    Returns a simple status message.
    Always returns 200 if server is running.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Made with Bob