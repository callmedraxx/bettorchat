"""
Non-blocking database operations using background threads.
This ensures database saves don't block the agent from doing other things.

All database save operations in this module run in background threads,
allowing the agent to continue processing and call multiple tools in parallel
without waiting for database writes to complete.

The agent framework (LangGraph/DeepAgents) supports parallel tool execution
by default - when the LLM requests multiple tools, they can execute concurrently.
Combined with non-blocking database saves, this allows the agent to:
1. Call multiple tools simultaneously
2. Continue processing while database saves happen in the background
3. Get information as quickly as possible
"""
import logging
import threading
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


def run_in_background(func: Callable, *args, **kwargs) -> None:
    """
    Run a function in a background thread without blocking.
    
    This function creates a daemon thread that executes the given function,
    allowing the calling code to continue immediately without waiting.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
    """
    def _run():
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in background thread for {func.__name__}: {e}", exc_info=True)
    
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def non_blocking_db_operation(func: Callable) -> Callable:
    """
    Decorator to make database operations non-blocking.
    
    The decorated function will be executed in a background thread,
    allowing the calling code to continue immediately.
    
    Usage:
        @non_blocking_db_operation
        def save_to_db(data):
            # database save logic
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Run the function in a background thread
        run_in_background(func, *args, **kwargs)
        # Return immediately (function returns None for non-blocking operations)
        return None
    
    return wrapper


def save_tool_result_async(
    tool_call_id: str,
    session_id: str,
    tool_name: str,
    full_result: str,
    structured_data: Optional[Any] = None
) -> None:
    """
    Non-blocking version of save_tool_result_to_db.
    Executes in background thread and returns immediately.
    
    This allows tools to save their results to the database without blocking
    the agent from continuing to process other tools or operations.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        session_id: Session identifier
        tool_name: Name of the tool
        full_result: Full result string
        structured_data: Optional structured data for querying
    """
    from app.core.tool_result_db import save_tool_result_to_db
    
    run_in_background(
        save_tool_result_to_db,
        tool_call_id=tool_call_id,
        session_id=session_id,
        tool_name=tool_name,
        full_result=full_result,
        structured_data=structured_data
    )


def save_odds_async(
    tool_call_id: str,
    session_id: str,
    fixture_id: str,
    odds_data: dict
) -> None:
    """
    Non-blocking version of save_odds_to_db.
    Executes in background thread and returns immediately.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        session_id: Session identifier
        fixture_id: Fixture ID
        odds_data: Odds data dictionary
    """
    from app.core.odds_db import save_odds_to_db
    
    run_in_background(
        save_odds_to_db,
        tool_call_id=tool_call_id,
        session_id=session_id,
        fixture_id=fixture_id,
        odds_data=odds_data
    )


def save_fixtures_async(
    session_id: str,
    fixtures: list
) -> None:
    """
    Non-blocking version of save_fixtures_to_db.
    Executes in background thread and returns immediately.
    
    Args:
        session_id: Session identifier
        fixtures: List of fixture dictionaries
    """
    from app.core.fixture_storage import save_fixtures_to_db
    
    run_in_background(
        save_fixtures_to_db,
        session_id=session_id,
        fixtures=fixtures
    )
