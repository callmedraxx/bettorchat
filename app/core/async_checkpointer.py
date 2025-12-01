"""
Async wrapper for PostgresSaver to enable async operations.
PostgresSaver doesn't implement aget_tuple, so we wrap it to run sync methods in executor.
"""
import asyncio
from typing import Optional, Any, AsyncIterator
from langgraph.checkpoint.base import CheckpointTuple, Checkpoint, CheckpointMetadata, ChannelVersions


class AsyncPostgresSaverWrapper:
    """Wrapper to make PostgresSaver async-compatible by running sync methods in executor."""
    
    def __init__(self, sync_saver):
        """Initialize wrapper with sync PostgresSaver instance."""
        self._sync_saver = sync_saver
    
    async def aget_tuple(self, config: Any) -> Optional[CheckpointTuple]:
        """Run sync get_tuple in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_saver.get_tuple, config)
    
    async def aget(self, config: Any) -> Optional[Checkpoint]:
        """Run sync get in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_saver.get, config)
    
    async def aput(self, config: Any, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> Any:
        """Run sync put in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_saver.put, config, checkpoint, metadata, new_versions)
    
    async def alist(self, config: Any = None, *, filter: Optional[dict] = None, before: Optional[Any] = None, limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        """Run sync list in thread pool and yield results."""
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: list(self._sync_saver.list(config, filter=filter, before=before, limit=limit)))
        for result in results:
            yield result
    
    async def aput_writes(self, config: Any, writes: Any, task_id: str, task_path: str = "") -> None:
        """Run sync put_writes in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_saver.put_writes, config, writes, task_id, task_path)
    
    async def adelete_thread(self, thread_id: str) -> None:
        """Run sync delete_thread in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_saver.delete_thread, thread_id)
    
    def __getattr__(self, name: str):
        """Delegate all other attributes/methods to sync saver."""
        return getattr(self._sync_saver, name)

