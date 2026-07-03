"""
RabbitMQ Client for Schema Synchronization (aio-pika implementation)

This module provides an async RabbitMQ consumer using aio-pika library,
which offers built-in resilience features including:
- Automatic reconnection with fixed 5-second interval
- Connection and channel pooling
- Robust connection management
- Built-in heartbeat handling

This replaces the previous pika-based implementation with significantly
less code and better reliability.
"""
import asyncio
import json
import logging
import os
import socket
import ssl
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from collections import defaultdict
from urllib.parse import quote

import aio_pika
from aio_pika import connect_robust, ExchangeType, DeliveryMode
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel, AbstractQueue

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """
    Async RabbitMQ consumer using aio-pika with built-in resilience.
    
    Features:
    - Automatic reconnection (built into aio-pika)
    - Durable queues and messages
    - Dead letter queue for failed messages
    - Connection pooling and channel management
    - Async/await native support
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        exchange_name: str,
        routing_key: str,
        deployment_name: str,
        use_ssl: bool = True,
        virtual_host: str = "/"
    ):
        """
        Initialize RabbitMQ client.
        
        Args:
            host: RabbitMQ server hostname
            port: RabbitMQ server port
            username: RabbitMQ username
            password: RabbitMQ password
            exchange_name: Exchange name for metadata events
            routing_key: Routing key for queue binding
            deployment_name: Unique deployment identifier for queue naming
            use_ssl: Whether to use SSL/TLS connection
            virtual_host: RabbitMQ virtual host
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange_name = exchange_name
        self.routing_key = routing_key
        self.deployment_name = deployment_name
        self.use_ssl = use_ssl
        self.virtual_host = virtual_host
        
        # Generate unique queue name: {deployment_name}-{hostname}-{pid}
        # In Kubernetes, hostname is the pod name, ensuring uniqueness per pod
        hostname = socket.gethostname()
        pid = os.getpid()
        self.queue_name = f"{deployment_name}-{hostname}-{pid}"
        self.dlx_name = f"{exchange_name}.dlx"
        self.dlq_name = f"{self.queue_name}.dlq"
        
        # Connection objects (managed by aio-pika)
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractRobustChannel] = None
        self.queue: Optional[AbstractQueue] = None
        
        # Event callback
        self.event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Statistics
        self.messages_received = 0
        self.messages_processed = 0
        self.messages_failed = 0
        
        # State tracking
        self.is_running = False
        self._consumer_task: Optional[asyncio.Task] = None
        
        logger.info(
            "RabbitMQ client initialized (aio-pika)",
            extra={
                "host": host,
                "port": port,
                "exchange": exchange_name,
                "routing_key": routing_key,
                "queue": self.queue_name,
                "use_ssl": use_ssl
            }
        )
    
    def set_event_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback function for processing metadata events.
        
        Args:
            callback: Function to call when metadata event is received
        """
        self.event_callback = callback
        logger.debug("Event callback registered")
    
    async def connect(self) -> None:
        """
        Connect to RabbitMQ and setup queue/exchange.
        
        Uses aio-pika's connect_robust which provides automatic reconnection.
        """
        try:
            logger.info("Connecting to RabbitMQ...")
            
            # Create SSL context with custom CA certificate (same as pika version)
            ssl_context = None
            if self.use_ssl:
                ca_cert_path = os.getenv('RABBITMQ_SSL_CA_CERT', '/etc/pki/tls/certs/ca.crt')

                # Check if CA certificate exists
                if os.path.exists(ca_cert_path):
                    logger.info(f"Using custom CA certificate: {ca_cert_path}")
                    ssl_context = ssl.create_default_context(cafile=ca_cert_path)
                else:
                    logger.warning(f"CA certificate not found at {ca_cert_path}, using default SSL context")
                    ssl_context = ssl.create_default_context()

                # Optional: Add client certificates if available
                client_cert = os.getenv('RABBITMQ_SSL_CLIENT_CERT')
                client_key = os.getenv('RABBITMQ_SSL_CLIENT_KEY')
                if client_cert and client_key and os.path.exists(client_cert) and os.path.exists(client_key):
                    logger.info(f"Loading client certificate: {client_cert}")
                    ssl_context.load_cert_chain(client_cert, client_key)
            
            # URL-encode username and password to handle special characters
            # (e.g., @, :, /, ?, #, %) that would break URL parsing
            encoded_username = quote(self.username, safe='')
            encoded_password = quote(self.password, safe='')
            
            # Build connection URL with encoded credentials
            protocol = "amqps" if self.use_ssl else "amqp"
            url = f"{protocol}://{encoded_username}:{encoded_password}@{self.host}:{self.port}/{self.virtual_host}" #pragma: allowlist secret
            
            self.connection = await connect_robust(
                url,
                timeout=30,
                reconnect_interval=5.0,  # Production-grade: retry every 5 seconds
                fail_fast=False,
                ssl_context=ssl_context
            )
            
            # Add connection state callbacks for visibility
            self.connection.reconnect_callbacks.add(self._on_reconnect_callback)
            self.connection.close_callbacks.add(self._on_close_callback)
            
            # Create channel (also robust - auto-recovers)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)  # Process up to 10 messages concurrently
            
            # Declare exchange (idempotent)
            exchange = await self.channel.declare_exchange(
                self.exchange_name,
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Declare dead letter exchange
            dlx = await self.channel.declare_exchange(
                self.dlx_name,
                ExchangeType.TOPIC,
                durable=True
            )
            
            # Declare dead letter queue
            dlq = await self.channel.declare_queue(
                self.dlq_name,
                durable=True,
                arguments={
                    "x-message-ttl": 86400000,  # 24 hours
                    "x-max-length": 1000,  # Max 1000 messages
                    "x-overflow": "drop-head"  # Drop oldest when full
                }
            )
            
            # Bind DLQ to DLX
            await dlq.bind(dlx, routing_key=f"{self.routing_key}.failed")
            
            # Declare main queue with DLX configuration
            self.queue = await self.channel.declare_queue(
                self.queue_name,
                durable=True,  # Survives RabbitMQ restart
                auto_delete=False,  # Persists during reconnection
                arguments={
                    "x-message-ttl": 3600000,  # 1 hour message TTL
                    "x-expires": 86400000,  # 24 hours queue expiration if unused
                    "x-dead-letter-exchange": self.dlx_name,
                    "x-dead-letter-routing-key": f"{self.routing_key}.failed"
                }
            )
            
            # Bind queue to exchange
            await self.queue.bind(exchange, routing_key=self.routing_key)
            
            logger.info(
                "Connected to RabbitMQ successfully",
                extra={
                    "queue": self.queue_name,
                    "exchange": self.exchange_name,
                    "routing_key": self.routing_key,
                    "dlq": self.dlq_name
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to connect to RabbitMQ: {e}",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise
    
    async def _process_message(self, message: aio_pika.IncomingMessage) -> None:
        """
        Process incoming RabbitMQ message.
        
        Args:
            message: Incoming message from RabbitMQ
        """
        async with message.process():  # Auto-ack on success, nack on exception
            try:
                self.messages_received += 1
                
                # Parse message body
                body = json.loads(message.body.decode())
                
                logger.debug(
                    "Received metadata event",
                    extra={
                        "message_id": message.message_id,
                        "routing_key": message.routing_key,
                        "object_type": body.get("object_type"),
                        "action": body.get("action")
                    }
                )
                
                # Call event callback if registered
                if self.event_callback:
                    # Run callback in thread pool to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.event_callback, body)
                    self.messages_processed += 1
                else:
                    logger.warning("No event callback registered, message ignored")
                    self.messages_failed += 1
                
            except json.JSONDecodeError as e:
                self.messages_failed += 1
                logger.error(
                    f"Invalid JSON in message: {e}",
                    extra={
                        "error": str(e),
                        "message_id": message.message_id,
                        "body_preview": message.body[:200].decode(errors='replace')
                    }
                )
                # Message will be nacked and sent to DLQ
                raise
                
            except Exception as e:
                self.messages_failed += 1
                logger.error(
                    f"Error processing message: {e}",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "message_id": message.message_id
                    }
                )
                # Message will be nacked and sent to DLQ
                raise
    
    async def start_consuming(self) -> None:
        """
        Start consuming messages from RabbitMQ.
        
        This method runs indefinitely, processing messages as they arrive.
        aio-pika handles reconnection automatically.
        """
        if not self.queue:
            raise RuntimeError("Must call connect() before start_consuming()")
        
        self.is_running = True
        
        logger.info(
            "Starting message consumption",
            extra={"queue": self.queue_name}
        )
        
        try:
            # Start consuming messages
            # aio-pika will automatically reconnect if connection is lost
            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.is_running:
                        break
                    
                    try:
                        await self._process_message(message)
                    except Exception as e:
                        # Log error but continue consuming
                        # Bad messages are already sent to DLQ by _process_message
                        logger.error(
                            f"Error processing message (sent to DLQ): {e}",
                            extra={
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "message_id": getattr(message, 'message_id', 'unknown')
                            }
                        )
                        # Continue to next message - don't stop the consumer
                    
        except asyncio.CancelledError:
            logger.info("Message consumption cancelled")
            raise
        except Exception as e:
            logger.error(
                f"Fatal error in consumption loop: {e}",
                extra={"error": str(e), "error_type": type(e).__name__}
            )
            raise
        finally:
            self.is_running = False
    
    async def stop_consuming(self) -> None:
        """
        Stop consuming messages and close connection.
        """
        logger.info("Stopping RabbitMQ consumer...")
        
        self.is_running = False
        
        # Cancel consumer task if running
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        # Close channel and connection
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
        
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        
        logger.info(
            "Stopped RabbitMQ consumer",
            extra={
                "messages_received": self.messages_received,
                "messages_processed": self.messages_processed,
                "messages_failed": self.messages_failed
            }
        )
    
    async def _on_reconnect_callback(self, connection) -> None:
        """Called when connection is restored."""
        logger.info("RabbitMQ connection restored")
    
    async def _on_close_callback(self, connection, exc) -> None:
        """Called when connection is lost."""
        logger.warning(f"RabbitMQ connection lost: {exc}")
    
    def is_connected(self) -> bool:
        """
        Check if connected to RabbitMQ.
        
        Returns:
            True if connected, False otherwise
        """
        return (
            self.connection is not None and
            not self.connection.is_closed and
            self.channel is not None and
            not self.channel.is_closed
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the RabbitMQ client.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "is_connected": self.is_connected(),
            "is_running": self.is_running,
            "messages_received": self.messages_received,
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "queue_name": self.queue_name,
            "exchange_name": self.exchange_name,
            "routing_key": self.routing_key
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the RabbitMQ client for monitoring.
        
        Returns:
            Dictionary with health status including:
            - healthy: Overall health boolean
            - status_message: Human-readable status
            - is_connected: Connection status
            - messages_processed: Total messages processed
        """
        is_connected = self.is_connected()
        
        # Determine overall health
        if is_connected and self.is_running:
            healthy = True
            status_message = "RabbitMQ consumer connected and running"
        elif self.is_running and not is_connected:
            healthy = False
            status_message = "RabbitMQ consumer reconnecting"
        else:
            healthy = False
            status_message = "RabbitMQ consumer not running"
        
        return {
            "healthy": healthy,
            "status_message": status_message,
            "is_connected": is_connected,
            "is_running": self.is_running,
            "messages_processed": self.messages_processed,
            "messages_received": self.messages_received,
            "messages_failed": self.messages_failed
        }


class SchemaUpdateQueue:
    """
    Thread-safe queue for storing objectType update events before processing.
    
    This queue stores objectType names that need schema updates, using a
    dictionary to deduplicate events for the same objectType.
    """
    
    def __init__(self):
        """Initialize the update queue."""
        self._pending_updates: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()  # For thread-safe sync operations
    
    async def add_update(self, object_type: str) -> None:
        """
        Add an objectType to the update queue.
        
        Args:
            object_type: Name of the objectType to update
        """
        async with self._lock:
            self._pending_updates[object_type] = datetime.now()
    
    def add_update_sync(self, object_type: str) -> None:
        """
        Synchronous version of add_update for compatibility.
        
        Args:
            object_type: Name of the objectType to update
        """
        with self._thread_lock:
            self._pending_updates[object_type] = datetime.now()
    
    async def get_pending_updates(self) -> list[str]:
        """
        Get and clear all pending updates.
        
        Returns:
            List of objectType names that need updates
        """
        async with self._lock:
            updates = list(self._pending_updates.keys())
            self._pending_updates.clear()
            return updates
    
    def get_pending_updates_sync(self) -> list[str]:
        """
        Synchronous version of get_pending_updates.
        
        Returns:
            List of objectType names that need updates
        """
        with self._thread_lock:
            # Atomic swap-and-clear to prevent race conditions
            updates = list(self._pending_updates.keys())
            self._pending_updates.clear()
            return updates
    
    def get_count(self) -> int:
        """
        Get count of pending updates.
        
        Returns:
            Number of pending updates
        """
        return len(self._pending_updates)


# Made with Bob