"""
Betting tools for agents.
"""
from app.agents.tools.betting_tools import (
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
    fetch_upcoming_games,
)
from app.agents.tools.web_tools import internet_search

__all__ = [
    "fetch_live_odds",
    "fetch_player_props",
    "fetch_live_game_stats",
    "fetch_injury_reports",
    "detect_arbitrage_opportunities",
    "fetch_futures",
    "fetch_grader",
    "fetch_historical_odds",
    "calculate_parlay_odds",
    "image_to_bet_analysis",
    "generate_bet_deep_link",
    "read_url_content",
    "get_current_datetime",
    "fetch_upcoming_games",
    "internet_search",
]

