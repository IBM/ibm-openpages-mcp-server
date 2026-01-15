"""
Distributed tracing module for GRC MCP Server
Provides OpenTelemetry-based tracing for request tracking
"""

import functools
import time
from typing import Any, Callable, Optional, Dict
from contextvars import ContextVar

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    trace = None
    TracerProvider = None
    FastAPIInstrumentor = None

from .logger import get_logger

logger = get_logger(__name__)

# Context variable for current span
current_span_var: ContextVar[Optional[Any]] = ContextVar("current_span", default=None)

# Global tracer instance
_tracer: Optional[Any] = None
_tracing_enabled: bool = False


def setup_tracing(
    service_name: str = "grc-mcp-server",
    otlp_endpoint: Optional[str] = None,
    console_export: bool = False,
    enabled: bool = True,
) -> None:
    """
    Setup distributed tracing with OpenTelemetry
    
    Args:
        service_name: Name of the service
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        console_export: Whether to export traces to console
        enabled: Whether tracing is enabled
    """
    global _tracer, _tracing_enabled
    
    if not enabled:
        logger.info("Tracing is disabled")
        _tracing_enabled = False
        return
    
    if not TRACING_AVAILABLE:
        logger.warning(
            "OpenTelemetry not available. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
        )
        _tracing_enabled = False
        return
    
    try:
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: service_name
        })
        
        # Create tracer provider
        provider = TracerProvider(resource=resource)
        
        # Add exporters
        if otlp_endpoint:
            # OTLP exporter for production
            # Use insecure connection for localhost
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP tracing configured: endpoint={otlp_endpoint}")
        
        if console_export:
            # Console exporter for development
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("Console tracing configured")
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        # Get tracer instance
        _tracer = trace.get_tracer(__name__)
        _tracing_enabled = True
        
        logger.info(f"Tracing initialized: service={service_name}")
        
    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}", exc_info=True)
        _tracing_enabled = False


def get_tracer() -> Optional[Any]:
    """
    Get the global tracer instance
    
    Returns:
        OpenTelemetry tracer instance or None if tracing is not enabled
    """
    return _tracer


def instrument_fastapi_app(app: Any) -> None:
    """
    Instrument FastAPI application for automatic tracing
    
    Adds OpenTelemetry instrumentation to automatically trace all FastAPI requests.
    
    Args:
        app: FastAPI application instance
    """
    if not _tracing_enabled or not TRACING_AVAILABLE or not FastAPIInstrumentor:
        logger.info("FastAPI instrumentation skipped (tracing not enabled or not available)")
        return
    
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI application instrumented for tracing")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI app: {e}", exc_info=True)


def is_tracing_enabled() -> bool:
    """
    Check if tracing is enabled
    
    Returns:
        Boolean indicating whether distributed tracing is active
    """
    return _tracing_enabled


def trace_operation(
    operation_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Decorator to trace a function or method
    
    Args:
        operation_name: Name of the operation (defaults to function name)
        attributes: Additional attributes to add to the span
    
    Example:
        @trace_operation("process_request")
        async def process_request(data):
            # Function implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not _tracing_enabled or not _tracer:
                return await func(*args, **kwargs)
            
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with _tracer.start_as_current_span(span_name) as span:
                # Store span in context
                current_span_var.set(span)
                
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Record success
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    # Record error
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    current_span_var.set(None)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not _tracing_enabled or not _tracer:
                return func(*args, **kwargs)
            
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with _tracer.start_as_current_span(span_name) as span:
                # Store span in context
                current_span_var.set(span)
                
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    
                    # Record success
                    span.set_attribute("duration_ms", duration * 1000)
                    span.set_status(Status(StatusCode.OK))
                    
                    return result
                    
                except Exception as e:
                    # Record error
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
                finally:
                    current_span_var.set(None)
        
        # Return appropriate wrapper based on function type
        if functools.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def add_span_attribute(key: str, value: Any) -> None:
    """
    Add an attribute to the current span
    
    Args:
        key: Attribute key
        value: Attribute value
    """
    if not _tracing_enabled:
        return
    
    span = current_span_var.get()
    if span:
        try:
            span.set_attribute(key, value)
        except Exception as e:
            logger.warning(f"Failed to add span attribute: {e}")


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """
    Add an event to the current span
    
    Args:
        name: Event name
        attributes: Event attributes
    """
    if not _tracing_enabled:
        return
    
    span = current_span_var.get()
    if span:
        try:
            span.add_event(name, attributes=attributes or {})
        except Exception as e:
            logger.warning(f"Failed to add span event: {e}")


def record_exception(exception: Exception) -> None:
    """
    Record an exception in the current span
    
    Args:
        exception: Exception to record
    """
    if not _tracing_enabled:
        return
    
    span = current_span_var.get()
    if span:
        try:
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))
        except Exception as e:
            logger.warning(f"Failed to record exception: {e}")


def get_current_span() -> Optional[Any]:
    """
    Get the current span from context
    
    Returns:
        Current OpenTelemetry span or None if not in a traced context
    """
    return current_span_var.get()


def get_trace_id() -> Optional[str]:
    """
    Get the trace ID of the current span
    
    Returns:
        Trace ID as a hex string or None if not in a traced context
    """
    if not _tracing_enabled:
        return None
    
    span = current_span_var.get()
    if span:
        try:
            span_context = span.get_span_context()
            return format(span_context.trace_id, '032x')
        except Exception:
            return None
    return None


def get_span_id() -> Optional[str]:
    """
    Get the span ID of the current span
    
    Returns:
        Span ID as a hex string or None if not in a traced context
    """
    if not _tracing_enabled:
        return None
    
    span = current_span_var.get()
    if span:
        try:
            span_context = span.get_span_context()
            return format(span_context.span_id, '016x')
        except Exception:
            return None
    return None