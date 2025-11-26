"""
Storage for full tool results to prevent truncation by LangGraph.
"""
import json
import logging
import time
from typing import Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)

# In-memory storage for full tool results
# Key: tool_call_id, Value: full result string
_tool_results: Dict[str, str] = {}
_storage_lock = Lock()


def store_tool_result(tool_call_id: str, full_result: str) -> None:
    """
    Store full tool result before LangGraph truncates it.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        full_result: Full result string from the tool
    """
    try:
        with _storage_lock:
            _tool_results[tool_call_id] = full_result
            logger.debug(f"[ToolResultStorage] Stored full result for tool_call_id={tool_call_id}, size={len(full_result)}")
    except Exception as e:
        logger.error(f"[ToolResultStorage] Error storing tool result: {e}", exc_info=True)


def get_tool_result(tool_call_id: str) -> Optional[str]:
    """
    Retrieve full tool result.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        
    Returns:
        Full result string or None if not found
    """
    try:
        with _storage_lock:
            return _tool_results.get(tool_call_id)
    except Exception as e:
        logger.error(f"[ToolResultStorage] Error retrieving tool result: {e}", exc_info=True)
        return None


def clear_tool_result(tool_call_id: str) -> None:
    """
    Clear stored tool result.
    
    Args:
        tool_call_id: Unique identifier for the tool call
    """
    try:
        with _storage_lock:
            _tool_results.pop(tool_call_id, None)
    except Exception as e:
        logger.error(f"[ToolResultStorage] Error clearing tool result: {e}", exc_info=True)


def is_truncated_message(content: str) -> bool:
    """
    Check if a tool result message indicates truncation.
    
    Args:
        content: Tool result content string
        
    Returns:
        True if content indicates truncation
    """
    if not content:
        return False
    return (
        "Tool result too large" in content or
        "was saved in the filesystem" in content or
        "/large_tool_results/" in content
    )


def extract_tool_call_id_from_truncated(content: str) -> Optional[str]:
    """
    Extract tool_call_id from truncated message.
    
    Args:
        content: Truncated tool result content
        
    Returns:
        tool_call_id if found, None otherwise
    """
    try:
        # Look for pattern: "toolu_XXXXX" in the filesystem path
        import re
        match = re.search(r'toolu_[A-Za-z0-9]+', content)
        if match:
            return match.group(0)
    except Exception:
        pass
    return None

