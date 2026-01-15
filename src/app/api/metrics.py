"""
Metrics endpoint for Prometheus scraping

This module provides the HTTP endpoint for exposing Prometheus-compatible metrics.
The /metrics endpoint returns metrics in Prometheus text format for scraping by
monitoring systems like Prometheus, Grafana, or other observability tools.

Metrics include:
- HTTP request metrics (count, duration, in-progress)
- Tool execution metrics (count, duration, errors)
- OpenPages API call metrics (count, duration, errors)
- MCP protocol metrics (connections, messages)
"""

from fastapi import APIRouter, Response
from src.app.observability.metrics import get_metrics_output, is_metrics_enabled
from src.app.observability.logger import get_logger

logger = get_logger(__name__)

metrics_router = APIRouter(tags=["metrics"])


@metrics_router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    
    Returns metrics in Prometheus text format for scraping by monitoring systems.
    Includes HTTP request metrics, tool execution metrics, OpenPages API metrics,
    and MCP protocol metrics.
    
    Returns:
        Response with Prometheus-formatted metrics or error message
    """
    if not is_metrics_enabled():
        return Response(
            content="Metrics collection is disabled",
            media_type="text/plain",
            status_code=503
        )
    
    try:
        metrics_data, content_type = get_metrics_output()
        return Response(
            content=metrics_data,
            media_type=content_type
        )
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}", exc_info=True)
        return Response(
            content=f"Error generating metrics: {str(e)}",
            media_type="text/plain",
            status_code=500
        )