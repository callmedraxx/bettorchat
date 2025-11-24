"""
Redis client for caching and session management.
Uses in-memory dict for development, Redis for production.
"""
from typing import Optional, Dict, Any
import json
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

# In-memory store for development
_in_memory_store: Dict[str, Any] = {}


class RedisClient:
    """Redis client wrapper with fallback to in-memory store."""
    
    def __init__(self):
        self._redis: Optional[Redis] = None
        self._async_redis: Optional[AsyncRedis] = None
        self._use_redis = settings.ENVIRONMENT == "production" and settings.REDIS_URL
        
    def _get_sync_client(self) -> Optional[Redis]:
        """Get synchronous Redis client."""
        if not self._use_redis:
            return None
        if self._redis is None:
            self._redis = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self._redis
    
    async def _get_async_client(self) -> Optional[AsyncRedis]:
        """Get asynchronous Redis client."""
        if not self._use_redis:
            return None
        if self._async_redis is None:
            self._async_redis = AsyncRedis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self._async_redis
    
    def get(self, key: str) -> Optional[str]:
        """Get value from Redis or in-memory store."""
        if self._use_redis:
            client = self._get_sync_client()
            if client:
                return client.get(key)
        return _in_memory_store.get(key)
    
    async def aget(self, key: str) -> Optional[str]:
        """Async get value from Redis or in-memory store."""
        if self._use_redis:
            client = await self._get_async_client()
            if client:
                return await client.get(key)
        return _in_memory_store.get(key)
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value in Redis or in-memory store."""
        if self._use_redis:
            client = self._get_sync_client()
            if client:
                return client.set(key, value, ex=ex)
        _in_memory_store[key] = value
        return True
    
    async def aset(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Async set value in Redis or in-memory store."""
        if self._use_redis:
            client = await self._get_async_client()
            if client:
                return await client.set(key, value, ex=ex)
        _in_memory_store[key] = value
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis or in-memory store."""
        if self._use_redis:
            client = self._get_sync_client()
            if client:
                return bool(client.delete(key))
        return _in_memory_store.pop(key, None) is not None
    
    async def adelete(self, key: str) -> bool:
        """Async delete key from Redis or in-memory store."""
        if self._use_redis:
            client = await self._get_async_client()
            if client:
                return bool(await client.delete(key))
        return _in_memory_store.pop(key, None) is not None
    
    def clear(self):
        """Clear all data (for development/testing)."""
        if self._use_redis:
            client = self._get_sync_client()
            if client:
                client.flushdb()
        else:
            _in_memory_store.clear()
    
    async def close(self):
        """Close Redis connections."""
        if self._async_redis:
            await self._async_redis.close()
        if self._redis:
            self._redis.close()


# Global Redis client instance
redis_client = RedisClient()

