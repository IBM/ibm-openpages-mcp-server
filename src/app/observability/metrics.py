"""
Metrics collection module for GRC MCP Server
Provides Prometheus-compatible metrics for monitoring
"""

import time
from typing import Dict, Optional, Callable, Any
from functools import wraps
from contextvars import ContextVar

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    Counter = None
    Histogram = None
    Gauge = None
    Info = None
    CollectorRegistry = None

from .logger import get_logger

logger = get_logger(__name__)

# Global metrics registry
metrics_registry: Optional[Any] = None
_metrics_enabled: bool = False

# Metrics instances
http_requests_total: Optional[Any] = None
http_request_duration_seconds: Optional[Any] = None
http_requests_in_progress: Optional[Any] = None
tool_executions_total: Optional[Any] = None
tool_execution_duration_seconds: Optional[Any] = None
tool_execution_errors_total: Optional[Any] = None
openpages_api_calls_total: Optional[Any] = None
openpages_api_duration_seconds: Optional[Any] = None
openpages_api_errors_total: Optional[Any] = None
mcp_connections_active: Optional[Any] = None
mcp_messages_total: Optional[Any] = None
server_info: Optional[Any] = None


def setup_metrics(
    enabled: bool = True,
    service_name: str = "grc-mcp-server",
    service_version: str = "1.0.0",
) -> None:
    """
    Setup Prometheus metrics collection
    
    Args:
        enabled: Whether metrics collection is enabled
        service_name: Name of the service
        service_version: Version of the service
    """
    global metrics_registry, _metrics_enabled
    global http_requests_total, http_request_duration_seconds, http_requests_in_progress
    global tool_executions_total, tool_execution_duration_seconds, tool_execution_errors_total
    global openpages_api_calls_total, openpages_api_duration_seconds, openpages_api_errors_total
    global mcp_connections_active, mcp_messages_total, server_info
    
    if not enabled:
        logger.info("Metrics collection is disabled")
        _metrics_enabled = False
        return
    
    if not METRICS_AVAILABLE:
        logger.warning(
            "Prometheus client not available. Install with: pip install prometheus-client"
        )
        _metrics_enabled = False
        return
    
    try:
        # Create custom registry
        metrics_registry = CollectorRegistry()
        
        # Server info
        server_info = Info(
            "grc_mcp_server",
            "GRC MCP Server information",
            registry=metrics_registry
        )
        server_info.info({
            "service": service_name,
            "version": service_version,
        })
        
        # HTTP metrics
        http_requests_total = Counter(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status"],
            registry=metrics_registry
        )
        
        http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            registry=metrics_registry
        )
        
        http_requests_in_progress = Gauge(
            "http_requests_in_progress",
            "Number of HTTP requests currently being processed",
            ["method", "endpoint"],
            registry=metrics_registry
        )
        
        # Tool execution metrics
        tool_executions_total = Counter(
            "tool_executions_total",
            "Total number of tool executions",
            ["tool_name", "status"],
            registry=metrics_registry
        )
        
        tool_execution_duration_seconds = Histogram(
            "tool_execution_duration_seconds",
            "Tool execution duration in seconds",
            ["tool_name"],
            registry=metrics_registry
        )
        
        tool_execution_errors_total = Counter(
            "tool_execution_errors_total",
            "Total number of tool execution errors",
            ["tool_name", "error_type"],
            registry=metrics_registry
        )
        
        # OpenPages API metrics
        openpages_api_calls_total = Counter(
            "openpages_api_calls_total",
            "Total number of OpenPages API calls",
            ["method", "endpoint", "status"],
            registry=metrics_registry
        )
        
        openpages_api_duration_seconds = Histogram(
            "openpages_api_duration_seconds",
            "OpenPages API call duration in seconds",
            ["method", "endpoint"],
            registry=metrics_registry
        )
        
        openpages_api_errors_total = Counter(
            "openpages_api_errors_total",
            "Total number of OpenPages API errors",
            ["method", "endpoint", "error_type"],
            registry=metrics_registry
        )
        
        # MCP protocol metrics
        mcp_connections_active = Gauge(
            "mcp_connections_active",
            "Number of active MCP connections",
            registry=metrics_registry
        )
        
        mcp_messages_total = Counter(
            "mcp_messages_total",
            "Total number of MCP messages",
            ["message_type", "direction"],
            registry=metrics_registry
        )
        
        _metrics_enabled = True
        logger.info(f"Metrics collection initialized: service={service_name}, version={service_version}")
        
    except Exception as e:
        logger.error(f"Failed to setup metrics: {e}", exc_info=True)
        _metrics_enabled = False


def is_metrics_enabled() -> bool:
    """
    Check if metrics collection is enabled
    
    Returns:
        Boolean indicating whether metrics collection is active
    """
    return _metrics_enabled


def get_metrics_registry() -> Optional[Any]:
    """
    Get the metrics registry
    
    Returns:
        Prometheus metrics registry instance or None if not initialized
    """
    return metrics_registry


def get_metrics_output() -> tuple:
    """
    Get metrics in Prometheus format
    
    Returns:
        Tuple of (metrics_data, content_type)
    """
    if not _metrics_enabled or not metrics_registry:
        return b"", "text/plain"
    
    try:
        return generate_latest(metrics_registry), CONTENT_TYPE_LATEST
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return b"", "text/plain"


def track_request(method: str, endpoint: str):
    """
    Decorator to track HTTP request metrics
    
    Args:
        method: HTTP method
        endpoint: Request endpoint
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not _metrics_enabled:
                return await func(*args, **kwargs)
            
            # Increment in-progress gauge
            if http_requests_in_progress:
                http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
            
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                # Record duration
                duration = time.time() - start_time
                if http_request_duration_seconds:
                    http_request_duration_seconds.labels(
                        method=method,
                        endpoint=endpoint
                    ).observe(duration)
                
                # Increment counter
                if http_requests_total:
                    http_requests_total.labels(
                        method=method,
                        endpoint=endpoint,
                        status=status
                    ).inc()
                
                # Decrement in-progress gauge
                if http_requests_in_progress:
                    http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not _metrics_enabled:
                return func(*args, **kwargs)
            
            # Increment in-progress gauge
            if http_requests_in_progress:
                http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
            
            start_time = time.time()
            status = "success"
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                # Record duration
                duration = time.time() - start_time
                if http_request_duration_seconds:
                    http_request_duration_seconds.labels(
                        method=method,
                        endpoint=endpoint
                    ).observe(duration)
                
                # Increment counter
                if http_requests_total:
                    http_requests_total.labels(
                        method=method,
                        endpoint=endpoint,
                        status=status
                    ).inc()
                
                # Decrement in-progress gauge
                if http_requests_in_progress:
                    http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
        
        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def track_tool_execution(tool_name: str):
    """
    Decorator to track tool execution metrics
    
    Args:
        tool_name: Name of the tool
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not _metrics_enabled:
                return await func(*args, **kwargs)
            
            start_time = time.time()
            status = "success"
            error_type = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                
                # Record error
                if tool_execution_errors_total:
                    tool_execution_errors_total.labels(
                        tool_name=tool_name,
                        error_type=error_type
                    ).inc()
                raise
            finally:
                # Record duration
                duration = time.time() - start_time
                if tool_execution_duration_seconds:
                    tool_execution_duration_seconds.labels(tool_name=tool_name).observe(duration)
                
                # Increment counter
                if tool_executions_total:
                    tool_executions_total.labels(tool_name=tool_name, status=status).inc()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not _metrics_enabled:
                return func(*args, **kwargs)
            
            start_time = time.time()
            status = "success"
            error_type = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                
                # Record error
                if tool_execution_errors_total:
                    tool_execution_errors_total.labels(
                        tool_name=tool_name,
                        error_type=error_type
                    ).inc()
                raise
            finally:
                # Record duration
                duration = time.time() - start_time
                if tool_execution_duration_seconds:
                    tool_execution_duration_seconds.labels(tool_name=tool_name).observe(duration)
                
                # Increment counter
                if tool_executions_total:
                    tool_executions_total.labels(tool_name=tool_name, status=status).inc()
        
        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def record_openpages_api_call(
    method: str,
    endpoint: str,
    duration: float,
    status: str = "success",
    error_type: Optional[str] = None,
) -> None:
    """
    Record OpenPages API call metrics
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        duration: Call duration in seconds
        status: Call status (success/error)
        error_type: Type of error if failed
    """
    if not _metrics_enabled:
        return
    
    try:
        # Record duration
        if openpages_api_duration_seconds:
            openpages_api_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        
        # Increment counter
        if openpages_api_calls_total:
            openpages_api_calls_total.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()
        
        # Record error if present
        if error_type and openpages_api_errors_total:
            openpages_api_errors_total.labels(
                method=method,
                endpoint=endpoint,
                error_type=error_type
            ).inc()
    except Exception as e:
        logger.warning(f"Failed to record OpenPages API metrics: {e}")


def increment_mcp_connections() -> None:
    """
    Increment active MCP connections counter
    
    Increases the gauge tracking the number of active MCP connections.
    """
    if _metrics_enabled and mcp_connections_active:
        mcp_connections_active.inc()


def decrement_mcp_connections() -> None:
    """
    Decrement active MCP connections counter
    
    Decreases the gauge tracking the number of active MCP connections.
    """
    if _metrics_enabled and mcp_connections_active:
        mcp_connections_active.dec()


def record_mcp_message(message_type: str, direction: str) -> None:
    """
    Record MCP message
    
    Increments the counter for MCP messages by type and direction.
    
    Args:
        message_type: Type of MCP message (e.g., 'initialize', 'call_tool')
        direction: Message direction ('inbound' or 'outbound')
    """
    if _metrics_enabled and mcp_messages_total:
        mcp_messages_total.labels(message_type=message_type, direction=direction).inc()