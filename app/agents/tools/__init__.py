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
    detect_user_location,
    fetch_upcoming_games,
    fetch_available_sports,
    fetch_available_leagues,
    fetch_available_markets,
    fetch_available_sportsbooks,
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
    "detect_user_location",
    "fetch_upcoming_games",
    "fetch_available_sports",
    "fetch_available_leagues",
    "fetch_available_markets",
    "fetch_available_sportsbooks",
    "internet_search",
]

