"""
Fixture streaming service for SSE events.
Manages fixture data queue and streaming to frontend clients.
"""
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from collections import deque
import uuid
import threading

from app.core.redis_client import redis_client

# Logger for fixture stream
logger = logging.getLogger(__name__)


class FixtureStreamManager:
    """Manages fixture data streaming via SSE."""
    
    def __init__(self):
        # In-memory queues: session_id -> deque of fixture data
        self._queues: Dict[str, deque] = {}
        # Active SSE connections: session_id -> set of (queue, loop) tuples
        self._connections: Dict[str, Set[tuple]] = {}
        # Lock for thread safety (using threading lock for cross-event-loop safety)
        self._lock = threading.Lock()
    
    async def push_fixtures(self, session_id: str, fixtures: List[Dict[str, Any]]) -> bool:
        """
        Push fixture data to the queue for a session.
        
        Args:
            session_id: Session identifier (user_id or thread_id)
            fixtures: List of fixture objects to stream
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import time
            fixture_data = {
                "type": "fixtures",
                "data": fixtures,
                "timestamp": time.time()  # Use time.time() instead of event loop time
            }
            logger.info(f"[FixtureStreamManager] Created fixture_data with {len(fixtures)} fixtures for session_id={session_id}")
            
            # Store in Redis/in-memory (skip if Redis has event loop issues)
            try:
                key = f"fixture_stream:{session_id}"
                await redis_client.aset(key, json.dumps(fixture_data), ex=300)  # 5 min expiry
            except Exception as redis_error:
                logger.warning(f"[FixtureStreamManager] Redis storage failed (non-critical): {redis_error}")
                # Continue without Redis - in-memory queue will still work
            
            # Also store in in-memory queue (thread-safe)
            with self._lock:
                if session_id not in self._queues:
                    self._queues[session_id] = deque(maxlen=100)  # Limit queue size
                self._queues[session_id].append(fixture_data)
            
            # Notify all active connections for this session
            # Use thread-safe access to connections dict
            with self._lock:
                connections_copy = list(self._connections.get(session_id, set()))
            
            if connections_copy:
                logger.info(f"[FixtureStreamManager] Notifying {len(connections_copy)} connections for session_id={session_id}")
                for queue, loop in connections_copy:
                    try:
                        # Use the queue's original event loop
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(queue.put(fixture_data), loop)
                        else:
                            await queue.put(fixture_data)
                        logger.info(f"[FixtureStreamManager] Successfully put fixture_data into queue")
                    except Exception as e:
                        logger.error(f"[FixtureStreamManager] Error putting into queue: {e}")
                        pass  # Connection might be closed
            else:
                logger.warning(f"[FixtureStreamManager] No active connections for session_id={session_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error pushing fixtures: {e}", exc_info=True)
            return False
    
    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """
        Subscribe to fixture updates for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AsyncQueue that will receive fixture updates
        """
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        
        # Thread-safe access to connections
        with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add((queue, loop))
            logger.info(f"[FixtureStreamManager] Subscribed session_id={session_id}, total connections: {len(self._connections[session_id])}")
            print(f"[CRITICAL] Subscribed session_id={session_id}, total connections: {len(self._connections[session_id])}")
            print(f"[CRITICAL] All session_ids in connections: {list(self._connections.keys())}")
        
        # Send any existing data from Redis
        try:
            key = f"fixture_stream:{session_id}"
            existing_data = await redis_client.aget(key)
            if existing_data:
                fixture_data = json.loads(existing_data)
                await queue.put(fixture_data)
        except Exception:
            pass
        
        return queue
    
    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from fixture updates.
        
        Args:
            session_id: Session identifier
            queue: Queue to remove
        """
        with self._lock:
            if session_id in self._connections:
                # Remove any tuple containing this queue
                to_remove = [item for item in self._connections[session_id] if item[0] == queue]
                for item in to_remove:
                    self._connections[session_id].discard(item)
                if not self._connections[session_id]:
                    del self._connections[session_id]
                logger.info(f"[FixtureStreamManager] Unsubscribed session_id={session_id}")
    
    async def get_latest_fixtures(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get latest fixture data for a session (non-streaming).
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of fixture objects or None
        """
        try:
            key = f"fixture_stream:{session_id}"
            data = await redis_client.aget(key)
            if data:
                fixture_data = json.loads(data)
                return fixture_data.get("data")
        except Exception:
            pass
        return None
    
    def push_fixtures_sync(self, session_id: str, fixtures: List[Dict[str, Any]]) -> bool:
        """
        Synchronous wrapper for push_fixtures (for use in sync tools).
        
        Instead of sending full fixture data, sends a notification message
        instructing the frontend to fetch fixtures from the API endpoint.
        
        Args:
            session_id: Session identifier
            fixtures: List of fixture objects (count used for notification, not sent)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import time
            logger.info(f"[FixtureStreamManager] push_fixtures_sync called with session_id={session_id}, fixtures_count={len(fixtures)} - sending notification to fetch from API")
            print(f"[CRITICAL] push_fixtures_sync called: session_id={session_id}, fixtures_count={len(fixtures)} - sending notification")
            
            # Create notification message instead of full fixture data
            # Frontend should fetch from API endpoint when receiving this message
            fixture_data = {
                "type": "fixtures",
                "action": "fetch",
                "session_id": session_id,
                "count": len(fixtures),
                "api_endpoint": f"/api/v1/fixtures/fixtures?session_id={session_id}",
                "timestamp": time.time()
            }
            
            # Store notification in in-memory queue (thread-safe, synchronous)
            with self._lock:
                if session_id not in self._queues:
                    self._queues[session_id] = deque(maxlen=100)
                self._queues[session_id].append(fixture_data)
                
                # Get connections for this session (queue, loop) tuples
                all_session_ids = list(self._connections.keys())
                connections = list(self._connections.get(session_id, set()))
                logger.info(f"[FixtureStreamManager] All active session_ids: {all_session_ids}")
                logger.info(f"[FixtureStreamManager] Looking for session_id: {session_id}")
                logger.info(f"[FixtureStreamManager] Found {len(connections)} connections for session_id={session_id}")
                print(f"[CRITICAL] Connections dict keys: {all_session_ids}")
                print(f"[CRITICAL] Looking for session_id: {session_id}")
                print(f"[CRITICAL] Found {len(connections)} connections for session_id={session_id}")
            
            if len(connections) == 0:
                logger.warning(f"[FixtureStreamManager] No active SSE connections for session_id={session_id}. Notification not sent - no clients connected.")
                print(f"[CRITICAL] No active SSE connections for session_id={session_id}. Notification not sent.")
            
            # Put data into queues using their original event loops
            for queue, loop in connections:
                try:
                    if loop.is_running():
                        # Schedule in the queue's original event loop
                        asyncio.run_coroutine_threadsafe(queue.put(fixture_data), loop)
                        logger.info(f"[FixtureStreamManager] Scheduled fixture notification into queue via run_coroutine_threadsafe")
                    else:
                        # Loop is not running, try direct await in a new coroutine
                        async def put_data():
                            await queue.put(fixture_data)
                        asyncio.run(put_data())
                        logger.info(f"[FixtureStreamManager] Put fixture notification into queue directly")
                except Exception as e:
                    logger.error(f"[FixtureStreamManager] Error putting into queue: {e}")
            
            # Also try to store notification in Redis (non-blocking, non-critical)
            # Use synchronous Redis client since we're in a sync context
            try:
                key = f"fixture_stream:{session_id}"
                redis_client.set(key, json.dumps(fixture_data), ex=300)
                logger.debug(f"[FixtureStreamManager] Stored fixture notification in Redis for session_id={session_id}")
            except Exception as redis_error:
                logger.warning(f"[FixtureStreamManager] Redis storage failed (non-critical): {redis_error}")
            
            return True
        except Exception as e:
            logger.error(f"[FixtureStreamManager] Error in push_fixtures_sync: {e}", exc_info=True)
            return False


# Global fixture stream manager instance
fixture_stream_manager = FixtureStreamManager()

