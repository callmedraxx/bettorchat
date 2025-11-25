"""
Agent creation and management for sports betting assistant.
"""
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
    internet_search,
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
    # Initialize model
    model = init_chat_model(
        model_name,
        api_key=settings.ANTHROPIC_API_KEY,
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
        internet_search,  # Keep web search
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
# Default to betting agent
agent = create_betting_agent()
