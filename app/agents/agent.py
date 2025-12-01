"""
Agent creation and management for sports betting assistant.
"""
import os
import logging
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore

from app.agents.tools import (
    fetch_live_odds,
    fetch_player_props,
    fetch_live_game_stats,
    fetch_injury_reports,
    detect_arbitrage_opportunities,
    fetch_futures,
    fetch_grader,
    fetch_historical_odds,
    calculate_parlay_odds,
    image_to_bet_analysis,
    read_url_content,
    fetch_upcoming_games,
    fetch_available_sports,
    fetch_available_leagues,
    fetch_available_markets,
    fetch_market_types,
    fetch_available_sportsbooks,
    fetch_players,
    fetch_teams,
    query_tool_results,
    query_odds_entries,
    internet_search,
    python_repl,
)
from app.agents.tools.betting_tools import build_opticodds_url
from app.agents.prompts import SPORTS_BETTING_INSTRUCTIONS, get_current_datetime_string
from app.agents.subagents import ALL_SUBAGENTS
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global checkpointer and store instances (singleton pattern)
_checkpointer_instance = None
_store_instance = None
# Keep context managers alive to prevent connection closure
_checkpointer_cm = None
_store_cm = None

# Global agent instance cache (singleton pattern for faster responses)
# NOTE: Cache is keyed by model_name to auto-invalidate when model changes
_agent_instance_cache: dict = {}

def clear_agent_cache():
    """Clear the cached agent instance. Useful when model or prompt changes."""
    global _agent_instance_cache
    _agent_instance_cache = {}


def _get_store() -> BaseStore:
    """Get store - PostgreSQL for production, InMemoryStore for development.
    
    Uses singleton pattern to ensure we reuse the same store instance.
    This is important for PostgresStore to maintain connection pooling.
    
    Returns:
        Store instance (PostgresStore or InMemoryStore)
    """
    global _store_instance
    
    # Return cached instance if available
    if _store_instance is not None:
        return _store_instance
    
    # Try to use PostgreSQL if available
    if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgresql"):
        try:
            from langgraph.store.postgres import PostgresStore
            
            logger.info(f"Initializing PostgresStore with DATABASE_URL")
            # from_conn_string returns a GeneratorContextManager, use it as context manager
            global _store_cm
            _store_cm = PostgresStore.from_conn_string(settings.DATABASE_URL)
            store = _store_cm.__enter__()
            
            # Setup tables if they don't exist
            try:
                store.setup()
                logger.info("PostgresStore initialized and tables created/verified")
            except Exception as setup_error:
                logger.warning(f"PostgresStore setup failed (tables may already exist): {setup_error}")
            
            # Store the instance (context manager kept in global to prevent cleanup)
            _store_instance = store
            return store
        except Exception as conn_error:
            # Check if it's a connection error
            error_msg = str(conn_error).lower()
            if "connection" in error_msg or "timeout" in error_msg or "refused" in error_msg:
                logger.warning(f"PostgresStore connection failed: {conn_error}. This may be transient. Falling back to InMemoryStore.")
            else:
                logger.error(f"Failed to initialize PostgresStore: {conn_error}. Falling back to InMemoryStore.")
        except ImportError:
            logger.warning(
                "PostgresStore not available. Install with: pip install 'langgraph-checkpoint-postgres'"
            )
        except Exception as e:
            logger.error(f"Failed to initialize PostgresStore: {e}. Falling back to InMemoryStore.")
    
    # Fallback to in-memory store for development
    logger.info("Using InMemoryStore (in-memory) - long-term memory will not persist across restarts")
    _store_instance = InMemoryStore()
    return _store_instance


def _get_checkpointer(force_memory: bool = False):
    """Get checkpointer - PostgreSQL for production, MemorySaver for development.
    
    Uses singleton pattern to ensure we reuse the same checkpointer instance.
    This is important for PostgresSaver to maintain connection pooling.
    
    Args:
        force_memory: If True, force use of MemorySaver (needed for async streaming)
    
    Returns:
        Checkpointer instance (PostgresSaver or MemorySaver)
    """
    global _checkpointer_instance
    
    # If forcing memory, always return MemorySaver
    if force_memory:
        from langgraph.checkpoint.memory import MemorySaver
        logger.info("Using MemorySaver (forced) - required for async streaming operations")
        return MemorySaver()
    
    # Return cached instance if available
    if _checkpointer_instance is not None:
        return _checkpointer_instance
    
    # Try to use PostgreSQL if available
    if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            
            logger.info(f"Initializing PostgresSaver with DATABASE_URL")
            # from_conn_string returns a GeneratorContextManager, use it as context manager
            global _checkpointer_cm
            _checkpointer_cm = PostgresSaver.from_conn_string(settings.DATABASE_URL)
            checkpointer = _checkpointer_cm.__enter__()
            
            # Setup tables if they don't exist
            try:
                checkpointer.setup()
                logger.info("PostgresSaver initialized and tables created/verified")
            except Exception as setup_error:
                logger.warning(f"PostgresSaver setup failed (tables may already exist): {setup_error}")
            
            # Store the instance (context manager kept in global to prevent cleanup)
            _checkpointer_instance = checkpointer
            return checkpointer
        except ImportError:
            logger.warning(
                "PostgresSaver not available. Install with: pip install 'langgraph-checkpoint-postgres'"
            )
        except Exception as e:
            logger.error(f"Failed to initialize PostgresSaver: {e}. Falling back to MemorySaver.")
    
    # Fallback to in-memory checkpointer for development
    from langgraph.checkpoint.memory import MemorySaver
    logger.info("Using MemorySaver (in-memory) - conversation state will not persist across restarts")
    _checkpointer_instance = MemorySaver()
    return _checkpointer_instance


def create_betting_agent(
    model_name: str = "claude-haiku-4-5-20251001",
    user_id: str = "default",
    checkpointer=None,
    use_cache: bool = True,
):
    """Create a sports betting agent with deep agent capabilities.
    
    The agent supports parallel tool execution - when the LLM requests multiple tools,
    they can execute concurrently. All database save operations are non-blocking,
    allowing the agent to continue processing while saves happen in the background.
    
    Args:
        model_name: Model to use for the agent
        user_id: User ID for personalization
        checkpointer: Optional checkpointer instance. If None, uses _get_checkpointer().
                     Use MemorySaver for async streaming (PostgresSaver doesn't support async).
        use_cache: If True, reuse cached agent instance for faster responses (default: True).
                  Set to False to force creation of new agent instance.
    
    Returns:
        Configured deep agent that supports parallel tool execution
    """
    global _agent_instance_cache
    
    # Return cached agent if available and caching is enabled
    # Only cache if using default checkpointer (not custom one for async streaming)
    # Cache is keyed by model_name to auto-invalidate when model changes
    cache_key = model_name if use_cache and checkpointer is None else None
    if cache_key and cache_key in _agent_instance_cache:
        logger.debug(f"Reusing cached agent instance (model: {model_name}) for faster response")
        return _agent_instance_cache[cache_key]
    
    # Get API key with proper error handling
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY must be set in environment variables or config. "
            "Please set it in LangSmith deployment settings."
        )
    
    # Initialize model with latency-optimized settings
    # Haiku 4.5 is the smallest, fastest Claude model with minimal latency
    model = init_chat_model(
        model=model_name,  # Explicitly set model parameter to ensure Haiku is used
        model_provider="anthropic",
        api_key=api_key,
        temperature=0,  # Deterministic responses for faster, consistent output
        timeout=10,  # Lower timeout for faster failure detection
        max_retries=1,  # Minimal retries to avoid delay
    )
    
    # Create checkpointer for conversation persistence (PostgreSQL in production, MemorySaver in dev)
    # Note: If checkpointer is provided, use it (e.g., MemorySaver for async streaming)
    if checkpointer is None:
        checkpointer = _get_checkpointer()
    
    # Create store for persistent long-term memory (PostgreSQL in production, InMemoryStore in dev)
    # This enables the /memories/ path in CompositeBackend to persist across threads
    store = _get_store()
    
    # Create composite backend for hybrid storage
    # /memories/ paths go to StoreBackend (persistent)
    # Other paths go to StateBackend (ephemeral)
    def make_backend(runtime):
        return CompositeBackend(
            default=StateBackend(runtime),
            routes={
                "/memories/": StoreBackend(runtime),
            }
        )
    
    # All betting tools
    betting_tools = [ # Location detection and timezone setup
        build_opticodds_url,  # URL builder - MUST be called before data-fetching tools to send URL to frontend
        fetch_upcoming_games,  # Primary tool for game schedules  # Tool for emitting full fixture JSON objects
        fetch_players,  # REQUIRED for player-specific requests - get player_id for player props/odds
        fetch_teams,  # Get team_id for team-specific requests or to filter players by team
        fetch_live_odds,
        fetch_player_props,
        fetch_live_game_stats,
        fetch_injury_reports,
        detect_arbitrage_opportunities,
        fetch_futures,
        fetch_grader,
        fetch_historical_odds,
        calculate_parlay_odds,
        image_to_bet_analysis,
        read_url_content,
        fetch_available_sports,  # Reference data: sports with active fixtures and odds
        fetch_available_leagues,  # Reference data: leagues with active fixtures and odds
        fetch_available_markets,  # Reference data: available market types
        fetch_market_types,  # Reference data: all market type definitions
        fetch_available_sportsbooks,  # Reference data: available sportsbooks
        query_tool_results,  # Query stored tool results by session_id, tool_name, fixture_id, or any field
        query_odds_entries,  # Query odds entries from database for large datasets (chunked retrieval)
        internet_search,  # Keep web search as fallback
        python_repl,  # Python REPL for data extraction and filtering from betting tool results
    ]
    
    # Format system prompt with user information and current date/time
    current_datetime = get_current_datetime_string()
    system_prompt = SPORTS_BETTING_INSTRUCTIONS.format(
        current_datetime=current_datetime
    )
    
    # Create the deep agent
    agent = create_deep_agent(
        model,
        tools=betting_tools,
        system_prompt=system_prompt,
        # subagents=ALL_SUBAGENTS,
        backend=make_backend,
        store=store,
        checkpointer=checkpointer,
    )
    
    # Cache agent instance if using default checkpointer (for non-streaming requests)
    # Cache is keyed by model_name to auto-invalidate when model changes
    cache_key = model_name if use_cache and checkpointer is None else None
    if cache_key:
        _agent_instance_cache[cache_key] = agent
        logger.info(f"Cached agent instance with model: {model_name}")
    
    return agent


# Export the agent graph for LangGraph CLI
# LangGraph requires the agent to be created at module level
# Make sure ANTHROPIC_API_KEY is set in LangSmith environment variables
try:
    agent = create_betting_agent()
except (ValueError, TypeError, KeyError) as e:
    # Provide clear error message for missing API key
    error_msg = str(e)
    if "ANTHROPIC_API_KEY" in error_msg or "api_key" in error_msg.lower():
        raise ValueError(
            "ANTHROPIC_API_KEY is required but not set.\n\n"
            "To fix this:\n"
            "1. Go to your LangSmith/LangGraph deployment settings\n"
            "2. Add environment variable: ANTHROPIC_API_KEY=your-key-here\n"
            "3. Get your API key from: https://console.anthropic.com/\n"
            "4. Redeploy your agent\n\n"
            f"Original error: {error_msg}"
        ) from e
    raise
