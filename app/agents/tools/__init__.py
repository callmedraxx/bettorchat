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
    filter_odds_from_json,
    build_opticodds_url,
)
from app.agents.tools.web_tools import internet_search
from app.agents.tools.python_tools import python_repl

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
    "read_url_content",
    "fetch_upcoming_games",
    "fetch_available_sports",
    "fetch_available_leagues",
    "fetch_available_markets",
    "fetch_market_types",
    "fetch_available_sportsbooks",
    "fetch_players",
    "fetch_teams",
    "query_tool_results",
    "query_odds_entries",
    "filter_odds_from_json",
    "build_opticodds_url",
    "internet_search",
    "python_repl",
]

