"""
Structured logging module for GRC MCP Server
Provides JSON-formatted logging with context and correlation IDs
"""

import logging
import json
import sys
import traceback
import functools
import time
import inspect
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from contextvars import ContextVar
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in structured JSON format
    
    Formats log records as JSON with additional context including timestamps,
    request IDs, user IDs, session IDs, and source location information.
    """
    
    def __init__(self, service_name: str = "grc-mcp-server"):
        """
        Initialize structured formatter
        
        Args:
            service_name: Name of the service for log identification
        """
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log string
        """
        
        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }
        
        # Add context information
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id
        
        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id
        
        session_id = session_id_var.get()
        if session_id:
            log_data["session_id"] = session_id
        
        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id
        
        # Add source location
        log_data["source"] = {
            "file": Path(record.pathname).name,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        return json.dumps(log_data)


class StructuredLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds structured logging capabilities
    
    Extends the standard LoggerAdapter to support structured logging with
    additional context fields and convenience methods for logging with context.
    """
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """
        Initialize structured logger
        
        Args:
            logger: Base logger instance
            extra: Optional extra fields to include in all log messages
        """
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process log message and add extra fields
        
        Args:
            msg: Log message
            kwargs: Keyword arguments for logging
            
        Returns:
            Tuple of (message, kwargs) with extra fields added
        """
        
        # Extract extra fields from kwargs
        extra_fields = kwargs.pop("extra_fields", {})
        
        # Merge with adapter's extra fields
        if self.extra:
            extra_fields.update(self.extra)
        
        # Add extra_fields to the log record
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        kwargs["extra"]["extra_fields"] = extra_fields
        
        return msg, kwargs
    
    def log_with_context(
        self,
        level: int,
        msg: str,
        *args,
        **kwargs
    ) -> None:
        """
        Log with additional context
        
        Logs a message with context variables (request_id, user_id, session_id)
        automatically added from the current context.
        
        Args:
            level: Logging level (e.g., logging.INFO, logging.ERROR)
            msg: Log message
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments including extra_fields
        """
        extra_fields = kwargs.pop("extra_fields", {})
        
        # Add context variables
        request_id = request_id_var.get()
        if request_id:
            extra_fields["request_id"] = request_id
        
        user_id = user_id_var.get()
        if user_id:
            extra_fields["user_id"] = user_id
        
        session_id = session_id_var.get()
        if session_id:
            extra_fields["session_id"] = session_id
        
        self.log(level, msg, *args, extra_fields=extra_fields, **kwargs)
    
    def info_with_context(self, msg: str, **kwargs) -> None:
        """
        Log info message with context
        
        Args:
            msg: Log message
            **kwargs: Additional keyword arguments including extra_fields
        """
        self.log_with_context(logging.INFO, msg, **kwargs)
    
    def error_with_context(self, msg: str, **kwargs) -> None:
        """
        Log error message with context
        
        Args:
            msg: Log message
            **kwargs: Additional keyword arguments including extra_fields
        """
        self.log_with_context(logging.ERROR, msg, **kwargs)
    
    def warning_with_context(self, msg: str, **kwargs) -> None:
        """
        Log warning message with context
        
        Args:
            msg: Log message
            **kwargs: Additional keyword arguments including extra_fields
        """
        self.log_with_context(logging.WARNING, msg, **kwargs)
    
    def debug_with_context(self, msg: str, **kwargs) -> None:
        """
        Log debug message with context
        
        Args:
            msg: Log message
            **kwargs: Additional keyword arguments including extra_fields
        """
        self.log_with_context(logging.DEBUG, msg, **kwargs)


def setup_logging(
    level: str = "INFO",
    service_name: str = "grc-mcp-server",
    json_format: bool = True,
    log_file: Optional[str] = None,
    use_stderr: bool = False,
    log_max_bytes: int = 10 * 1024 * 1024,  # 10 MB default
    log_backup_count: int = 5,  # Keep 5 backup files
) -> None:
    """
    Setup structured logging for the application
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Name of the service for log identification
        json_format: Whether to use JSON format (True) or plain text (False)
        log_file: Optional file path to write logs to (relative paths are resolved from project root)
        use_stderr: If True, log to stderr instead of stdout (required for stdio mode)
        log_max_bytes: Maximum size of log file before rotation (default: 10MB)
        log_backup_count: Number of backup files to keep (default: 5)
    """
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler with appropriate stream
    console_handler = logging.StreamHandler(sys.stderr if use_stderr else sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    # Set formatter
    if json_format:
        formatter = StructuredFormatter(service_name=service_name)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Suppress verbose httpcore and httpx logs at DEBUG level
    # These logs show TCP connection details, TLS handshakes, and HTTP headers
    # which are too verbose for normal debugging
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore.connection").setLevel(logging.INFO)
    logging.getLogger("httpcore.http11").setLevel(logging.INFO)
    
    # Add rotating file handler if specified
    if log_file:
        try:
            # Convert relative paths to absolute paths relative to project root
            log_path = Path(log_file)
            if not log_path.is_absolute():
                # Get project root (4 levels up from this file)
                project_root = Path(__file__).parent.parent.parent.parent
                log_path = project_root / log_file
            
            # Ensure the log directory exists
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use RotatingFileHandler for automatic log rotation
            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=log_max_bytes,
                backupCount=log_backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, level.upper()))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
            # Log rotation configuration
            root_logger.info(
                f"File logging configured: path={log_path}, "
                f"max_size={log_max_bytes / (1024*1024):.1f}MB, "
                f"backup_count={log_backup_count}"
            )
        except Exception as e:
            # If file logging fails, just log to console
            root_logger.warning(f"Failed to setup file logging to {log_file}: {e}")
    
    # Log setup completion
    root_logger.info(
        f"Logging configured: level={level}, format={'JSON' if json_format else 'TEXT'}, "
        f"service={service_name}, stream={'stderr' if use_stderr else 'stdout'}"
    )


def get_logger(name: str, **extra_fields) -> StructuredLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        **extra_fields: Additional fields to include in all log messages
    
    Returns:
        StructuredLogger instance
    """
    logger = logging.getLogger(name)
    return StructuredLogger(logger, extra=extra_fields)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """
    Set context variables for request tracking
    
    Args:
        request_id: Unique request identifier
        user_id: User identifier
        session_id: Session identifier
        trace_id: OpenTelemetry trace identifier
    """
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if session_id:
        session_id_var.set(session_id)
    if trace_id:
        trace_id_var.set(trace_id)


def clear_request_context() -> None:
    """Clear all request context variables"""
    request_id_var.set(None)
    user_id_var.set(None)
    session_id_var.set(None)
    trace_id_var.set(None)


def get_request_id() -> Optional[str]:
    """Get current request ID from context"""
    return request_id_var.get()


def get_user_id() -> Optional[str]:
    """Get current user ID from context"""
    return user_id_var.get()


def get_session_id() -> Optional[str]:
    """Get current session ID from context"""
    return session_id_var.get()


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context"""
    return trace_id_var.get()


def log_method_call(
    log_entry: bool = True,
    log_exit: bool = True,
    log_args: bool = False,
    log_result: bool = False,
    level: int = logging.DEBUG
):
    """
    Decorator to log method entry and exit with timing information
    
    This decorator provides automatic logging of method calls including:
    - Method entry with optional argument logging
    - Method exit with execution time
    - Optional result logging
    - Exception logging if method fails
    
    Args:
        log_entry: Whether to log method entry (default: True)
        log_exit: Whether to log method exit (default: True)
        log_args: Whether to log method arguments (default: False)
        log_result: Whether to log method result (default: False)
        level: Logging level to use (default: logging.DEBUG)
    
    Example:
        @log_method_call(log_args=True, log_result=True)
        async def process_data(self, data):
            # Method implementation
            return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get logger from the class instance if available
            if args and hasattr(args[0], '__class__'):
                logger_name = f"{args[0].__class__.__module__}.{args[0].__class__.__name__}"
                method_logger = logging.getLogger(logger_name)
            else:
                method_logger = logging.getLogger(func.__module__)
            
            func_name = func.__qualname__
            
            # Log entry
            if log_entry:
                entry_msg = f"→ Entering {func_name}"
                extra_fields = {"method": func_name, "event": "method_entry"}
                
                if log_args and (args or kwargs):
                    # Skip 'self' argument for instance methods
                    args_to_log = args[1:] if args and hasattr(args[0], '__class__') else args
                    if args_to_log or kwargs:
                        extra_fields["arguments"] = {
                            "args": str(args_to_log)[:200] if args_to_log else None,
                            "kwargs": str(kwargs)[:200] if kwargs else None
                        }
                
                method_logger.log(level, entry_msg, extra={"extra_fields": extra_fields})
            
            # Execute method and track time
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log exit
                if log_exit:
                    exit_msg = f"← Exiting {func_name} (duration: {duration:.3f}s)"
                    extra_fields = {
                        "method": func_name,
                        "event": "method_exit",
                        "duration_seconds": duration,
                        "duration_ms": duration * 1000
                    }
                    
                    if log_result and result is not None:
                        result_str = str(result)
                        extra_fields["result"] = result_str[:200] if len(result_str) > 200 else result_str
                    
                    method_logger.log(level, exit_msg, extra={"extra_fields": extra_fields})
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"✗ Exception in {func_name} after {duration:.3f}s: {str(e)}"
                extra_fields = {
                    "method": func_name,
                    "event": "method_exception",
                    "duration_seconds": duration,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                }
                method_logger.error(error_msg, exc_info=True, extra={"extra_fields": extra_fields})
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get logger from the class instance if available
            if args and hasattr(args[0], '__class__'):
                logger_name = f"{args[0].__class__.__module__}.{args[0].__class__.__name__}"
                method_logger = logging.getLogger(logger_name)
            else:
                method_logger = logging.getLogger(func.__module__)
            
            func_name = func.__qualname__
            
            # Log entry
            if log_entry:
                entry_msg = f"→ Entering {func_name}"
                extra_fields = {"method": func_name, "event": "method_entry"}
                
                if log_args and (args or kwargs):
                    # Skip 'self' argument for instance methods
                    args_to_log = args[1:] if args and hasattr(args[0], '__class__') else args
                    if args_to_log or kwargs:
                        extra_fields["arguments"] = {
                            "args": str(args_to_log)[:200] if args_to_log else None,
                            "kwargs": str(kwargs)[:200] if kwargs else None
                        }
                
                method_logger.log(level, entry_msg, extra={"extra_fields": extra_fields})
            
            # Execute method and track time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log exit
                if log_exit:
                    exit_msg = f"← Exiting {func_name} (duration: {duration:.3f}s)"
                    extra_fields = {
                        "method": func_name,
                        "event": "method_exit",
                        "duration_seconds": duration,
                        "duration_ms": duration * 1000
                    }
                    
                    if log_result and result is not None:
                        result_str = str(result)
                        extra_fields["result"] = result_str[:200] if len(result_str) > 200 else result_str
                    
                    method_logger.log(level, exit_msg, extra={"extra_fields": extra_fields})
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                error_msg = f"✗ Exception in {func_name} after {duration:.3f}s: {str(e)}"
                extra_fields = {
                    "method": func_name,
                    "event": "method_exception",
                    "duration_seconds": duration,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                }
                method_logger.error(error_msg, exc_info=True, extra={"extra_fields": extra_fields})
                raise
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator