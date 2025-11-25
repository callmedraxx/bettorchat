"""
Odds streaming service for SSE events.
Manages odds data queue and streaming to frontend clients.
"""
import json
import asyncio
from typing import Dict, List, Optional, Any, Set
from collections import deque
import threading

from app.core.redis_client import redis_client


class OddsStreamManager:
    """Manages odds data streaming via SSE."""
    
    def __init__(self):
        # In-memory queues: session_id -> deque of odds data
        self._queues: Dict[str, deque] = {}
        # Active SSE connections: session_id -> set of event queues
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def push_odds(self, session_id: str, odds_data: Dict[str, Any]) -> bool:
        """
        Push odds data to the queue for a session.
        
        Args:
            session_id: Session identifier (user_id or thread_id)
            odds_data: Odds data dictionary (from API response)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            odds_event = {
                "type": "odds",
                "data": odds_data,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Store in Redis/in-memory
            key = f"odds_stream:{session_id}"
            await redis_client.aset(key, json.dumps(odds_event), ex=300)  # 5 min expiry
            
            # Also store in in-memory queue
            async with self._lock:
                if session_id not in self._queues:
                    self._queues[session_id] = deque(maxlen=100)  # Limit queue size
                self._queues[session_id].append(odds_event)
            
            # Notify all active connections for this session
            async with self._lock:
                if session_id in self._connections:
                    for queue in self._connections[session_id]:
                        try:
                            await queue.put(odds_event)
                        except Exception:
                            pass  # Connection might be closed
            
            return True
        except Exception as e:
            print(f"Error pushing odds: {e}")
            return False
    
    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """
        Subscribe to odds updates for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AsyncQueue that will receive odds updates
        """
        queue = asyncio.Queue()
        
        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add(queue)
        
        # Send any existing data from Redis
        try:
            key = f"odds_stream:{session_id}"
            existing_data = await redis_client.aget(key)
            if existing_data:
                odds_data = json.loads(existing_data)
                await queue.put(odds_data)
        except Exception:
            pass
        
        return queue
    
    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from odds updates.
        
        Args:
            session_id: Session identifier
            queue: Queue to remove
        """
        async with self._lock:
            if session_id in self._connections:
                self._connections[session_id].discard(queue)
                if not self._connections[session_id]:
                    del self._connections[session_id]
    
    async def get_latest_odds(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get latest odds data for a session (non-streaming).
        
        Args:
            session_id: Session identifier
            
        Returns:
            Odds data dictionary or None
        """
        try:
            key = f"odds_stream:{session_id}"
            data = await redis_client.aget(key)
            if data:
                odds_data = json.loads(data)
                return odds_data.get("data")
        except Exception:
            pass
        return None
    
    def push_odds_sync(self, session_id: str, odds_data: Dict[str, Any]) -> bool:
        """
        Synchronous wrapper for push_odds (for use in sync tools).
        
        Args:
            session_id: Session identifier
            odds_data: Odds data dictionary to stream
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to get existing event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, we need to use a thread
                result = [False]
                exception = [None]
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result[0] = new_loop.run_until_complete(
                            self.push_odds(session_id, odds_data)
                        )
                    except Exception as e:
                        exception[0] = e
                    finally:
                        new_loop.close()
                
                thread = threading.Thread(target=run_in_thread, daemon=True)
                thread.start()
                thread.join(timeout=5.0)
                
                if exception[0]:
                    raise exception[0]
                return result[0]
            except RuntimeError:
                # No running loop, we can use asyncio.run
                return asyncio.run(self.push_odds(session_id, odds_data))
        except Exception as e:
            print(f"Error in push_odds_sync: {e}")
            return False


# Global odds stream manager instance
odds_stream_manager = OddsStreamManager()

