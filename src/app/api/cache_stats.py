"""
Cache Statistics API Module

Provides endpoints to monitor RabbitMQ-based schema synchronization status.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Response, status

logger = logging.getLogger(__name__)

# Create router for cache stats endpoints
cache_stats_router = APIRouter(tags=["cache"], prefix="/api/cache")

# Global reference to schema cache manager (set during startup)
_schema_cache_manager: Optional[Any] = None


def set_schema_cache_manager(manager: Any) -> None:
    """
    Set the global schema cache manager reference.
    
    Args:
        manager: SchemaCacheManager instance
    """
    global _schema_cache_manager
    _schema_cache_manager = manager
    logger.info("Schema cache manager reference set for API endpoints")


def get_schema_cache_manager() -> Optional[Any]:
    """
    Get the global schema cache manager reference.
    
    Returns:
        SchemaCacheManager instance or None if not initialized
    """
    return _schema_cache_manager


@cache_stats_router.get("/stats", summary="Get cache synchronization statistics")
async def get_cache_stats(response: Response) -> Dict[str, Any]:
    """
    Get statistics about RabbitMQ-based schema synchronization.
    
    Returns detailed information about:
    - Schema cache manager status
    - RabbitMQ connection status
    - Event processing statistics
    - Pending updates
    
    Status codes:
    - 200: Statistics retrieved successfully
    - 503: Schema synchronization not enabled or not available
    """
    manager = get_schema_cache_manager()
    
    if not manager:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "enabled": False,
            "message": "Schema synchronization is not enabled or not initialized",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    try:
        stats = manager.get_stats()
        stats["enabled"] = True
        stats["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return stats
    except Exception as e:
        logger.error(f"Error retrieving cache stats: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "enabled": True,
            "error": str(e),
            "message": "Failed to retrieve cache statistics",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


@cache_stats_router.get("/health", summary="Check cache synchronization health")
async def check_cache_health(response: Response) -> Dict[str, Any]:
    """
    Check the health of RabbitMQ-based schema synchronization.
    
    Returns:
    - Health status of schema cache manager
    - RabbitMQ connection status
    - Recent activity indicators
    
    Status codes:
    - 200: Healthy
    - 503: Unhealthy or not enabled
    """
    manager = get_schema_cache_manager()
    
    if not manager:
        # Import settings to check if RabbitMQ was enabled but failed to initialize
        from src.app.config.settings import settings
        
        if settings.RABBITMQ_ENABLED:
            # RabbitMQ was enabled but failed to initialize
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "failed",
                "message": "Schema synchronization is ENABLED but FAILED to initialize. Check server logs for details.",
                "rabbitmq_enabled": True,
                "initialization_failed": True,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        else:
            # RabbitMQ is intentionally disabled
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "disabled",
                "message": "Schema synchronization is not enabled",
                "rabbitmq_enabled": False,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    try:
        stats = manager.get_stats()
        
        # Determine health status
        is_running = stats.get("is_running", False)
        rabbitmq_stats = stats.get("rabbitmq_stats", {})
        is_connected = rabbitmq_stats.get("is_connected", False)
        
        if is_running and is_connected:
            health_status = "healthy"
            status_code = status.HTTP_200_OK
            message = "Schema synchronization is running and connected"
        elif is_running and not is_connected:
            health_status = "degraded"
            status_code = status.HTTP_200_OK
            message = "Schema synchronization is running but not connected to RabbitMQ"
        else:
            health_status = "unhealthy"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            message = "Schema synchronization is not running"
        
        response.status_code = status_code
        
        return {
            "status": health_status,
            "message": message,
            "is_running": is_running,
            "is_connected": is_connected,
            "events_received": stats.get("events_received", 0),
            "events_processed": stats.get("events_processed", 0),
            "pending_updates": stats.get("pending_updates", 0),
            "last_update_time": stats.get("last_update_time"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Error checking cache health: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "status": "error",
            "message": f"Failed to check cache health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


@cache_stats_router.get("/rabbitmq", summary="Get RabbitMQ connection details")
async def get_rabbitmq_stats(response: Response) -> Dict[str, Any]:
    """
    Get detailed RabbitMQ connection statistics.
    
    Returns:
    - Connection status
    - Queue information
    - Message processing statistics
    
    Status codes:
    - 200: Statistics retrieved successfully
    - 503: Not enabled or not available
    """
    manager = get_schema_cache_manager()
    
    if not manager:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "enabled": False,
            "message": "Schema synchronization is not enabled",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    try:
        stats = manager.get_stats()
        rabbitmq_stats = stats.get("rabbitmq_stats", {})
        rabbitmq_stats["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return rabbitmq_stats
    except Exception as e:
        logger.error(f"Error retrieving RabbitMQ stats: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "error": str(e),
            "message": "Failed to retrieve RabbitMQ statistics",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

# Made with Bob