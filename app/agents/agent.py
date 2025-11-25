"""
Agent creation and management for sports betting assistant.
"""
import os
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

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
    generate_bet_deep_link,
    read_url_content,
    get_current_datetime,
    detect_user_location,
    fetch_upcoming_games,
    emit_fixture_objects,
    fetch_available_sports,
    fetch_available_leagues,
    fetch_available_markets,
    fetch_available_sportsbooks,
    internet_search,
    python_repl,
)
from app.agents.prompts import SPORTS_BETTING_INSTRUCTIONS
from app.agents.subagents import ALL_SUBAGENTS
from app.core.config import settings


def create_betting_agent(
    model_name: str = "claude-sonnet-4-5-20250929",
    user_id: str = "default",
):
    """Create a sports betting agent with deep agent capabilities.
    
    Args:
        model_name: Model to use for the agent
        user_id: User ID for personalization
    
    Returns:
        Configured deep agent
    """
    # Get API key with proper error handling
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY must be set in environment variables or config. "
            "Please set it in LangSmith deployment settings."
        )
    
    # Initialize model
    model = init_chat_model(
        model_name,
        api_key=api_key,
    )
    
    # Create checkpointer for conversation persistence
    checkpointer = MemorySaver()
    
    # Create store for persistent memory
    store = InMemoryStore()
    
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
    betting_tools = [
        get_current_datetime,  # Date/time awareness - should be called first for date queries
        detect_user_location,  # Location detection and timezone setup
        fetch_upcoming_games,  # Primary tool for game schedules
        emit_fixture_objects,  # Tool for emitting full fixture JSON objects
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
        generate_bet_deep_link,
        read_url_content,
        fetch_available_sports,  # Reference data: sports with active fixtures and odds
        fetch_available_leagues,  # Reference data: leagues with active fixtures and odds
        fetch_available_markets,  # Reference data: available market types
        fetch_available_sportsbooks,  # Reference data: available sportsbooks
        internet_search,  # Keep web search as fallback
        python_repl,  # Python REPL for data extraction and filtering from betting tool results
    ]
    
    # Format system prompt with user information
    system_prompt = SPORTS_BETTING_INSTRUCTIONS.format(user_id=user_id, user_name=user_id)
    
    # Create the deep agent
    agent = create_deep_agent(
        model=model,
        tools=betting_tools,
        system_prompt=system_prompt,
        subagents=ALL_SUBAGENTS,
        backend=make_backend,
        store=store,
        checkpointer=checkpointer,
    )
    
    return agent


def create_research_agent():
    """Create a research agent with internet search capabilities.
    
    DEPRECATED: Use create_betting_agent instead.
    """
    agent = create_deep_agent(
        tools=[internet_search],
        system_prompt=SPORTS_BETTING_INSTRUCTIONS
    )
    return agent


# Export the agent graph for LangGraph CLI
# LangGraph requires the agent to be created at module level
# Make sure ANTHROPIC_API_KEY is set in LangSmith environment variables
try:
    agent = create_betting_agent()
except (ValueError, TypeError) as e:
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
