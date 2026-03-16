"""
Observability module for GRC MCP Server
Provides structured logging, distributed tracing, and metrics collection
"""

from .logger import get_logger, setup_logging
from .tracing import (
    setup_tracing,
    trace_operation,
    is_tracing_enabled,
    start_span,
    start_async_span,
    set_span_ok,
    set_span_error,
    add_span_attribute,
    add_span_event,
    record_exception,
    get_current_span,
    get_trace_id,
    get_span_id,
)
from .metrics import metrics_registry, track_request, track_tool_execution

__all__ = [
    "get_logger",
    "setup_logging",
    "setup_tracing",
    "trace_operation",
    "is_tracing_enabled",
    "start_span",
    "start_async_span",
    "set_span_ok",
    "set_span_error",
    "add_span_attribute",
    "add_span_event",
    "record_exception",
    "get_current_span",
    "get_trace_id",
    "get_span_id",
    "metrics_registry",
    "track_request",
    "track_tool_execution",
]