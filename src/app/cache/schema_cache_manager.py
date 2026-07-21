"""
Schema cache manager for handling RabbitMQ-based metadata change events.

This module coordinates between RabbitMQ events and schema cache updates,
implementing the periodic update mechanism for SaaS deployments.

Processes BUNDLETYPE and CONTENTTYPE metadata change events to keep
the schema cache synchronized with OpenPages.
"""
import asyncio
import threading
import time
from typing import Optional, Dict, Any, Set, List
from datetime import datetime

from src.app.cache.rabbitmq_client import RabbitMQClient, SchemaUpdateQueue
from src.app.observability.logger import get_logger

logger = get_logger(__name__)


class SchemaCacheManager:
    """
    Manages schema cache updates from RabbitMQ metadata change events.
    
    This manager:
    1. Receives metadata change events (BUNDLETYPE, CONTENTTYPE) from RabbitMQ
    2. Extracts impacted objectTypes from the events
    3. Queues them for batch processing
    4. Periodically updates the schema cache in a thread-safe manner
    """
    
    def __init__(
        self,
        schema_builder,
        rabbitmq_client: RabbitMQClient,
        update_interval: int = 60,
        resource_handlers=None
    ):
        """
        Initialize schema cache manager.
        
        Args:
            schema_builder: SchemaBuilder instance to update
            rabbitmq_client: RabbitMQ client for receiving events
            update_interval: Interval in seconds for processing updates (default: 60)
            resource_handlers: Optional ResourceHandlers instance for clearing formatted schema cache
        """
        self.schema_builder = schema_builder
        self.rabbitmq_client = rabbitmq_client
        self.update_interval = update_interval
        self.resource_handlers = resource_handlers
        
        # Event loop for async operations in update thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Update queue
        self.update_queue = SchemaUpdateQueue()
        
        # Update thread
        self.update_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # Consumer event loop (for proper cleanup)
        self.consumer_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Statistics
        self.events_received = 0
        self.events_processed = 0
        self.events_ignored = 0
        self.updates_processed = 0
        self.updates_failed = 0
        self.last_update_time: Optional[datetime] = None
        
        # Set event callback on RabbitMQ client
        self.rabbitmq_client.set_event_callback(self._on_metadata_event)
        
        logger.info(
            f"Schema cache manager initialized",
            extra={"update_interval": update_interval}
        )
    
    def _on_metadata_event(self, message: Dict[str, Any]) -> None:
        """
        Handle metadata change event from RabbitMQ.
        
        Processes BUNDLETYPE and CONTENTTYPE events to extract impacted objectTypes.
        
        Args:
            message: Metadata change event from RabbitMQ
        """
        try:
            self.events_received += 1
            
            # Extract event details from latest metadata event schema
            metadata_type = message.get('object_type')
            action = message.get('action')
            metadata_name = message.get('metadata_name')
            
            # Only process BUNDLETYPE and CONTENTTYPE events
            if metadata_type not in ['BUNDLETYPE', 'CONTENTTYPE']:
                logger.debug(
                    f"Ignoring non-relevant metadata event",
                    extra={
                        "metadata_type": metadata_type,
                        "metadata_name": metadata_name
                    }
                )
                self.events_ignored += 1
                return
            
            # Extract impacted object types from the event
            impacted_types = self._extract_impacted_types(message)
            
            if not impacted_types:
                logger.debug(
                    f"No impacted object types found in event",
                    extra={
                        "metadata_type": metadata_type,
                        "metadata_name": metadata_name,
                        "action": action
                    }
                )
                self.events_ignored += 1
                return
            
            # Queue each impacted objectType for update
            for object_type in impacted_types:
                self.update_queue.add_update_sync(object_type)
            
            self.events_processed += 1
            
            logger.debug(
                f"Queued objectType updates from metadata event",
                extra={
                    "metadata_type": metadata_type,
                    "metadata_name": metadata_name,
                    "action": action,
                    "impacted_types": list(impacted_types),
                    "queue_size": self.update_queue.get_count()
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error processing metadata event: {e}",
                extra={
                    "error": str(e),
                    "metadata_type": message.get('object_type'),
                    "metadata_name": message.get('metadata_name'),
                    "action": message.get('action')
                }
            )
    
    def _extract_impacted_types(self, message: Dict[str, Any]) -> Set[str]:
        """
        Extract impacted objectType names from metadata event.
        
        Args:
            message: Metadata change event
            
        Returns:
            Set of validated impacted objectType names
        """
        impacted_types = set()
        
        try:
            import re
            # Basic validation pattern for objectType names
            # Allows alphanumeric, underscore, hyphen (standard OpenPages naming)
            valid_name_pattern = re.compile(r'^[A-Za-z0-9_-]{1,255}$')
            
            # Navigate to details.impacted_object_types
            details = message.get('message', {}).get('details', {})
            impacted_list = details.get('impacted_object_types', [])
            
            # Extract and validate names from impacted object types
            for item in impacted_list:
                object_type = None
                if isinstance(item, dict) and 'name' in item:
                    object_type = item['name']
                elif isinstance(item, str):
                    object_type = item
                
                # Validate objectType name format
                if object_type:
                    if valid_name_pattern.match(str(object_type)):
                        impacted_types.add(object_type)
                    else:
                        logger.warning(
                            f"Ignoring invalid objectType name from RabbitMQ event",
                            extra={
                                "object_type": object_type,
                                "reason": "Invalid format (expected alphanumeric, underscore, hyphen, max 255 chars)"
                            }
                        )
            
            logger.debug(
                f"Extracted impacted types",
                extra={
                    "count": len(impacted_types),
                    "types": list(impacted_types)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error extracting impacted types: {e}",
                extra={"error": str(e)}
            )
        
        return impacted_types
    
    def _update_loop(self) -> None:
        """
        Main update loop running in separate thread.
        
        This loop wakes up periodically to process queued schema updates.
        """
        # Create a new event loop for this thread
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        except Exception as e:
            logger.error(f"Failed to create event loop: {e}")
            if self._loop:
                self._loop.close()
            raise
        
        logger.info(f"Schema cache update loop started (interval: {self.update_interval}s)")
        
        try:
            while self.is_running:
                try:
                    # Sleep for update interval (use asyncio.sleep for graceful shutdown)
                    self._loop.run_until_complete(asyncio.sleep(self.update_interval))
                    
                    # Get pending updates
                    pending_updates = self.update_queue.get_pending_updates_sync()
                    
                    if not pending_updates:
                        continue
                    
                    logger.info(
                        f"Processing schema cache updates",
                        extra={"update_count": len(pending_updates)}
                    )
                    
                    # Refresh all_types cache before processing updates
                    # This ensures relationship filtering works without API calls
                    self._loop.run_until_complete(self._refresh_all_types_cache())
                    
                    # Update specific objectTypes (now fully async)
                    self._loop.run_until_complete(
                        self._refresh_schemas(pending_updates)
                    )
                    
                    self.updates_processed += len(pending_updates)
                    self.last_update_time = datetime.utcnow()
                    
                    logger.info(
                        f"Schema cache updates completed",
                        extra={
                            "updated_types": len(pending_updates),
                            "total_updates": self.updates_processed
                        }
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Error in update loop: {e}",
                        extra={"error": str(e)}
                    )
        finally:
            # Clean up the event loop when thread exits
            if self._loop:
                self._loop.close()
                logger.debug("Closed event loop for update thread")
    
    async def _refresh_schemas(self, object_types: List[str]) -> None:
        """
        Refresh schemas for specific objectTypes with atomic invalidation and rebuild (fully async).
        
        This method invalidates BOTH caches:
        1. schema_builder.type_definitions (raw type definitions)
        2. resource_handlers._schema_cache (formatted schemas for MCP resources)
        
        Args:
            object_types: List of objectType names to refresh
        """
        for object_type in object_types:
            try:
                # 1. Mark as rebuilding and invalidate atomically
                if self.resource_handlers:
                    async with self.resource_handlers._schema_cache_lock:
                        # Mark as rebuilding to block concurrent builds
                        self.resource_handlers._schema_rebuilding.add(object_type)
                        
                        # Invalidate formatted schema cache
                        if object_type in self.resource_handlers._schema_cache:
                            del self.resource_handlers._schema_cache[object_type]
                            logger.debug(
                                f"Invalidated resource_handlers cache entry",
                                extra={"cache_key": object_type}
                            )
                
                # 2. Invalidate schema_builder cache (raw type definitions - sync operation)
                if hasattr(self.schema_builder, 'type_definitions'):
                    if object_type in self.schema_builder.type_definitions:
                        del self.schema_builder.type_definitions[object_type]
                        logger.debug(
                            f"Invalidated schema_builder cache for objectType",
                            extra={"object_type": object_type}
                        )
                
                # Also clear cache timestamps if they exist
                if hasattr(self.schema_builder, '_cache_timestamps'):
                    if object_type in self.schema_builder._cache_timestamps:
                        del self.schema_builder._cache_timestamps[object_type]
                
                # 3. Rebuild outside lock (allows other operations)
                try:
                    await self._preload_schema(object_type)
                    logger.info(
                        f"Successfully preloaded schema for {object_type}",
                        extra={"object_type": object_type}
                    )
                except Exception as preload_error:
                    # Track as failure and log at WARNING level
                    self.updates_failed += 1
                    logger.warning(
                        f"Failed to preload schema for {object_type} after invalidation",
                        extra={
                            "object_type": object_type,
                            "error": str(preload_error),
                            "error_type": type(preload_error).__name__,
                            "will_retry_on_demand": True,
                            "failed_count": self.updates_failed
                        },
                        exc_info=True  # Include stack trace for debugging
                    )
                finally:
                    # 4. Clear rebuilding flag atomically
                    if self.resource_handlers:
                        async with self.resource_handlers._schema_cache_lock:
                            self.resource_handlers._schema_rebuilding.discard(object_type)
                
            except Exception as e:
                self.updates_failed += 1
                logger.error(
                    f"Error refreshing schema for {object_type}: {e}",
                    extra={
                        "object_type": object_type,
                        "error": str(e),
                        "failed_count": self.updates_failed
                    }
                )
                # Ensure rebuilding flag is cleared even on error
                if self.resource_handlers:
                    try:
                        async with self.resource_handlers._schema_cache_lock:
                            self.resource_handlers._schema_rebuilding.discard(object_type)
                    except Exception as cleanup_error:
                        logger.error(f"Failed to clear rebuilding flag: {cleanup_error}")
    
    async def _refresh_all_types_cache(self) -> None:
        """
        Refresh the all_types cache to avoid API calls during schema rebuilds.
        This is called before processing schema updates.
        """
        try:
            if not self.resource_handlers:
                return
            
            logger.info("Refreshing all_types cache before schema updates")
            
            # Force refresh by clearing the cache
            async with self.resource_handlers._all_types_cache_lock:
                self.resource_handlers._all_types_cache = None
                self.resource_handlers._all_types_cache_timestamp = None
            
            # Trigger a refresh by calling the method
            await self.resource_handlers._get_all_object_types_cached()
            
            logger.info("All_types cache refreshed successfully")
            
        except Exception as e:
            logger.error(
                "Failed to refresh all_types cache",
                exc_info=True
            )
    
    async def _preload_schema(self, object_type: str) -> None:
        """
        Preload schema for an objectType.
        
        This is called after cache invalidation to eagerly load the new schema.
        
        Args:
            object_type: ObjectType name
        """
        try:
            # Call the schema builder to fetch and cache the schema
            if hasattr(self.schema_builder, 'get_type_definition'):
                await self.schema_builder.get_type_definition(object_type)
                logger.debug(
                    f"Preloaded schema",
                    extra={"object_type": object_type}
                )
        except Exception as e:
            logger.warning(
                f"Failed to preload schema for {object_type}: {e}",
                extra={
                    "object_type": object_type,
                    "error": str(e)
                }
            )
    
    def start(self) -> None:
        """
        Start the schema cache manager.
        
        This starts both the RabbitMQ consumer and the update loop.
        """
        if self.is_running:
            logger.warning("Schema cache manager is already running")
            return
        
        try:
            # Start update loop first
            self.is_running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                name="Schema-Cache-Updater",
                daemon=True
            )
            self.update_thread.start()
            
            # Start RabbitMQ consumer in a separate thread with its own event loop
            self.rabbitmq_thread = threading.Thread(
                target=self._run_rabbitmq_consumer,
                name="RabbitMQ-Consumer",
                daemon=True
            )
            self.rabbitmq_thread.start()
            
            logger.info("Schema cache manager started successfully")
            
        except Exception as e:
            logger.error(
                f"Failed to start schema cache manager: {e}",
                extra={"error": str(e)}
            )
            self.is_running = False
            raise
    
    def _run_rabbitmq_consumer(self) -> None:
        """
        Run RabbitMQ consumer in a separate thread with its own event loop.
        """
        loop = None
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.consumer_loop = loop  # Store the loop for proper cleanup
            
            # Connect and start consuming
            loop.run_until_complete(self.rabbitmq_client.connect())
            loop.run_until_complete(self.rabbitmq_client.start_consuming())
            
        except Exception as e:
            logger.error(
                f"RabbitMQ consumer thread failed: {e}",
                extra={"error": str(e)}
            )
        finally:
            if loop:
                loop.close()
    
    def stop(self) -> None:
        """
        Stop the schema cache manager.
        """
        if not self.is_running:
            return
        
        logger.info("Stopping schema cache manager")
        
        self.is_running = False
        
        # Stop RabbitMQ consumer on its own event loop
        if self.rabbitmq_client:
            try:
                # Schedule stop_consuming on the consumer's loop to avoid
                # "Future attached to a different loop" errors
                if self.consumer_loop and self.consumer_loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self.rabbitmq_client.stop_consuming(),
                        self.consumer_loop
                    )
                    # Wait for completion with timeout
                    future.result(timeout=5.0)
                else:
                    logger.warning("Consumer loop not running, cannot stop gracefully")
            except TimeoutError:
                logger.error("Timeout waiting for RabbitMQ consumer to stop")
            except Exception as e:
                logger.error(f"Error stopping RabbitMQ consumer: {e}")
        
        # Wait for RabbitMQ thread to finish
        if hasattr(self, 'rabbitmq_thread') and self.rabbitmq_thread and self.rabbitmq_thread.is_alive():
            self.rabbitmq_thread.join(timeout=10.0)
            if self.rabbitmq_thread.is_alive():
                logger.warning("RabbitMQ consumer thread did not stop gracefully")
        
        # Clean up the consumer loop reference
        self.consumer_loop = None
        
        # Wait for update thread to finish
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=10.0)
        
        logger.info(
            f"Schema cache manager stopped",
            extra={
                "events_received": self.events_received,
                "events_processed": self.events_processed,
                "events_ignored": self.events_ignored,
                "updates_processed": self.updates_processed
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about cache manager.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "is_running": self.is_running,
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_ignored": self.events_ignored,
            "updates_processed": self.updates_processed,
            "updates_failed": self.updates_failed,
            "pending_updates": self.update_queue.get_count(),
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "rabbitmq_stats": self.rabbitmq_client.get_stats()
        }

# Made with Bob