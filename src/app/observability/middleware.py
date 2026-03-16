"""
Middleware for observability features
Includes rate limiting, request tracking, logging, and metrics
"""

import time
import uuid
from typing import Callable, Optional, Dict, Any, List
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta

from .logger import get_logger, set_request_context, clear_request_context
from .tracing import add_span_attribute, add_span_event, get_trace_id
from . import metrics as metrics_module

logger = get_logger(__name__)

# Import token utilities for user ID extraction
try:
    from src.app.auth.token_utils import extract_user_id_from_token as _extract_user_id
    TOKEN_UTILS_AVAILABLE = True
except ImportError:
    TOKEN_UTILS_AVAILABLE = False
    _extract_user_id = None
    logger.warning("Token utilities not available for user ID extraction")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm
    
    Limits requests per IP address and optionally per user
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        enabled: bool = True,
    ):
        """
        Initialize rate limiter
        
        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute per client
            burst_size: Maximum burst size (tokens in bucket)
            enabled: Whether rate limiting is enabled
        """
        super().__init__(app)
        self.enabled = enabled
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        
        # Token buckets: {client_id: {"tokens": float, "last_refill": datetime}}
        self.buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "tokens": float(burst_size),
            "last_refill": datetime.now()
        })
        
        logger.info(
            f"Rate limiting initialized: {requests_per_minute} req/min, "
            f"burst={burst_size}, enabled={enabled}"
        )
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get client identifier from request
        
        Extracts a unique identifier for the client from the request headers or IP address.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client identifier string (e.g., "user:123" or "ip:192.168.1.1")
        """
        # Try to get user ID from headers or auth
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _refill_bucket(self, bucket: Dict[str, Any]) -> None:
        """
        Refill token bucket based on elapsed time
        
        Implements the token bucket algorithm by adding tokens based on time elapsed
        since the last refill.
        
        Args:
            bucket: Token bucket dictionary containing tokens and last_refill timestamp
        """
        now = datetime.now()
        elapsed = (now - bucket["last_refill"]).total_seconds()
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        bucket["tokens"] = min(
            self.burst_size,
            bucket["tokens"] + tokens_to_add
        )
        bucket["last_refill"] = now
    
    def _check_rate_limit(self, client_id: str) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit
        
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        bucket = self.buckets[client_id]
        
        # Refill bucket
        self._refill_bucket(bucket)
        
        # Check if we have tokens
        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            allowed = True
        else:
            allowed = False
        
        # Calculate retry after
        if not allowed:
            tokens_needed = 1.0 - bucket["tokens"]
            retry_after = int(tokens_needed / self.refill_rate) + 1
        else:
            retry_after = 0
        
        rate_limit_info = {
            "limit": self.requests_per_minute,
            "remaining": int(bucket["tokens"]),
            "reset": int((bucket["last_refill"] + timedelta(minutes=1)).timestamp()),
            "retry_after": retry_after,
        }
        
        return allowed, rate_limit_info
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting
        
        Checks if the request is within rate limits and either allows it to proceed
        or returns a 429 Too Many Requests response.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware or route handler
            
        Returns:
            Response object, either from the next handler or a rate limit error
        """
        
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/healthz", "/metrics", "/health/ready", "/health/live", "/health/startup"]:
            return await call_next(request)
        
        # Get client ID
        client_id = self._get_client_id(request)
        
        # Check rate limit
        allowed, rate_limit_info = self._check_rate_limit(client_id)
        
        # Add rate limit headers to response
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_id}",
                extra_fields={
                    "client_id": client_id,
                    "path": request.url.path,
                    "rate_limit": rate_limit_info,
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {rate_limit_info['retry_after']} seconds.",
                    "rate_limit": rate_limit_info,
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_limit_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_limit_info["reset"]),
                    "Retry-After": str(rate_limit_info["retry_after"]),
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to successful response
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset"])
        
        return response


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request tracking, logging, tracing, and metrics
    
    Adds comprehensive observability to all HTTP requests including:
    - Request ID generation and tracking
    - Structured logging with context
    - Distributed tracing integration
    - Metrics collection
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with observability features
        
        Wraps request processing with logging, tracing, and metrics collection.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware or route handler
            
        Returns:
            Response object with observability headers added
        """
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Extract user and session IDs if present
        user_id = request.headers.get("X-User-ID")
        session_id = request.headers.get("X-Session-ID")
        
        # NEW: For OpenPages MCP operations, try to extract user from Authorization header
        if not user_id and request.url.path.startswith("/mcp") and TOKEN_UTILS_AVAILABLE and _extract_user_id:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                extracted_user = _extract_user_id(auth_header)
                if extracted_user:
                    user_id = extracted_user
                    logger.debug(f"Extracted user_id from Authorization header: {user_id}")
        
        # Get trace ID first
        trace_id = get_trace_id()
        
        # Set request context for logging (includes trace_id)
        set_request_context(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
        )
        
        # Add trace attributes if tracing is enabled
        if trace_id:
            add_span_attribute("http.request_id", request_id)
            add_span_attribute("http.method", request.method)
            add_span_attribute("http.url", str(request.url))
            add_span_attribute("http.user_agent", request.headers.get("user-agent", ""))
            if user_id:
                add_span_attribute("user.id", user_id)
            if session_id:
                add_span_attribute("session.id", session_id)
        
        # Track in-progress requests for metrics
        if metrics_module.is_metrics_enabled() and metrics_module.http_requests_in_progress:
            metrics_module.http_requests_in_progress.labels(
                method=request.method,
                endpoint=request.url.path
            ).inc()
        
        # Log request start
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra_fields={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
            }
        )
        
        # Record start time
        start_time = time.time()
        
        # Initialize status variables
        status_code = 500
        status_category = "error"
        response = None
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            status_category = "success" if status_code < 400 else "error"
            
        except Exception as e:
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra_fields={
                    "request_id": request_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            # Record error in trace
            if trace_id:
                add_span_event("exception", {
                    "exception.type": type(e).__name__,
                    "exception.message": str(e),
                })
            
            status_code = 500
            status_category = "error"
            
            # Re-raise to let FastAPI handle it
            raise
            
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {status_code} ({duration:.3f}s)",
                extra_fields={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration * 1000,
                }
            )
            
            # Record metrics
            metrics_enabled = metrics_module.is_metrics_enabled()
            
            if metrics_enabled:
                if metrics_module.http_request_duration_seconds:
                    metrics_module.http_request_duration_seconds.labels(
                        method=request.method,
                        endpoint=request.url.path
                    ).observe(duration)
                
                if metrics_module.http_requests_total:
                    metrics_module.http_requests_total.labels(
                        method=request.method,
                        endpoint=request.url.path,
                        status=status_category
                    ).inc()
                
                if metrics_module.http_requests_in_progress:
                    metrics_module.http_requests_in_progress.labels(
                        method=request.method,
                        endpoint=request.url.path
                    ).dec()
            else:
                logger.info(
                    f"Metrics disabled - skipping recording for {request.method} {request.url.path}",
                    extra_fields={
                        "request_id": request_id,
                        "metrics_enabled": metrics_enabled,
                        "http_requests_total_exists": metrics_module.http_requests_total is not None,
                    }
                )
            
            # Add trace attributes
            if trace_id:
                add_span_attribute("http.status_code", status_code)
                add_span_attribute("http.duration_ms", duration * 1000)
            
            # Clear request context
            clear_request_context()
        
        # Add observability headers to response (if response exists)
        if response:
            response.headers["X-Request-ID"] = request_id
            if trace_id:
                response.headers["X-Trace-ID"] = trace_id
        
        return response


class CORSMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CORS middleware with logging
    
    Handles Cross-Origin Resource Sharing (CORS) headers for API requests.
    """
    
    def __init__(
        self,
        app,
        allow_origins: Optional[List[str]] = None,
        allow_methods: Optional[List[str]] = None,
        allow_headers: Optional[List[str]] = None,
        allow_credentials: bool = True,
    ):
        """
        Initialize CORS middleware
        
        Args:
            app: FastAPI application
            allow_origins: List of allowed origins (default: ["*"])
            allow_methods: List of allowed HTTP methods (default: ["*"])
            allow_headers: List of allowed headers (default: ["*"])
            allow_credentials: Whether to allow credentials (default: True)
        """
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with CORS headers
        
        Handles preflight OPTIONS requests and adds CORS headers to all responses.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware or route handler
            
        Returns:
            Response object with CORS headers added
        """
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = ", ".join(self.allow_origins)
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = ", ".join(self.allow_origins)
        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response