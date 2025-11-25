"""
MCP-compatible betting tools wrapping OpticOdds API.
"""
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from langchain.tools import tool
import httpx

from app.core.opticodds_client import OpticOddsClient


# Initialize OpticOdds client (singleton pattern)
_client: Optional[OpticOddsClient] = None


def get_client() -> OpticOddsClient:
    """Get or create OpticOdds client."""
    global _client
    if _client is None:
        _client = OpticOddsClient()
    return _client


@tool
def get_current_datetime() -> str:
    """Get the current date, time, timezone, and day of week.
    
    This tool should be called whenever the user mentions dates like "today", "tomorrow", 
    "next week", or any relative date references. Always use this tool to get the current 
    date before interpreting date-related queries.
    
    Returns:
        Formatted string with current date, time, timezone, and day of week
    """
    now = datetime.now()
    
    # Format date and time information
    formatted = f"""Current Date and Time Information:

Date: {now.strftime('%A, %B %d, %Y')}
Time: {now.strftime('%I:%M %p')}
Timezone: {now.strftime('%Z')} (UTC{now.strftime('%z')})
Day of Week: {now.strftime('%A')}
ISO Format: {now.isoformat()}

Use this information to interpret relative dates:
- "Today" = {now.strftime('%B %d, %Y')}
- "Tomorrow" = {(now + timedelta(days=1)).strftime('%B %d, %Y')}
- "This week" = Week of {now.strftime('%B %d, %Y')}
"""
    
    return formatted


@tool
def fetch_live_odds(
    fixture_id: Optional[str] = None,
    league_id: Optional[str] = None,
    sport_id: Optional[str] = None,
    sportsbook_ids: Optional[str] = None,
    market_types: Optional[str] = None,
) -> str:
    """Fetch live betting odds for fixtures using OpticOdds /fixtures/odds endpoint.
    
    Args:
        fixture_id: Specific fixture ID to get odds for
        league_id: Filter by league ID
        sport_id: Filter by sport ID (e.g., 'NBA' = 1)
        sportsbook_ids: Comma-separated list of sportsbook IDs
        market_types: Comma-separated list of market types (e.g., 'moneyline,spread,total')
    
    Returns:
        Formatted string with odds from multiple sportsbooks
    """
    try:
        client = get_client()
        
        # Convert to correct parameter format
        # Pass sport_id and league_id directly to the client method
        result = client.get_fixture_odds(
            fixture_id=fixture_id,
            sport_id=sport_id if sport_id else None,
            league_id=league_id if league_id else None,
            sportsbook=sportsbook_ids if sportsbook_ids else None,
            market_types=market_types if market_types else None,
        )
        
        # Format response for frontend
        formatted = format_odds_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching live odds: {str(e)}"


@tool
def fetch_upcoming_games(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    fixture_id: Optional[str] = None,
) -> str:
    """Fetch upcoming game schedules/fixtures using OpticOdds /fixtures endpoint.
    
    This is the PRIMARY tool for getting game schedules. Use this before falling back to web search.
    
    Args:
        sport: Sport name (e.g., 'basketball')
        league: League name (e.g., 'nba', 'nfl', 'mlb')
        fixture_id: Optional specific fixture ID
    
    Returns:
        Formatted string with upcoming game schedules including teams, dates, times, and fixture IDs
    """
    try:
        client = get_client()
        
        # Get fixtures from OpticOdds API
        result = client.get_fixtures(
            sport=sport if sport else None,
            league=league if league else None,
            fixture_id=fixture_id if fixture_id else None,
        )
        
        # Format response
        formatted = format_fixtures_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching upcoming games: {str(e)}"


@tool
def fetch_player_props(
    fixture_id: Optional[str] = None,
    player_id: Optional[str] = None,
    league_id: Optional[str] = None,
) -> str:
    """Fetch player proposition odds using OpticOdds /fixtures/player-results and player markets.
    
    Args:
        fixture_id: Specific fixture ID
        player_id: Specific player ID
        league_id: Filter by league ID
    
    Returns:
        Formatted string with player prop odds from multiple sportsbooks
    """
    try:
        client = get_client()
        
        # Get player results/markets
        params = {}
        if fixture_id:
            params["fixture_id"] = int(fixture_id)
        if player_id:
            params["player_id"] = int(player_id)
        
        player_results = client.get_player_results(**params)
        
        # Also get odds for player markets
        odds = client.get_fixture_odds(
            fixture_id=fixture_id if fixture_id else None,
            league=league_id if league_id else None,
            market_types="player_props",
        )
        
        # Format response
        formatted = format_player_props_response(player_results, odds)
        return formatted
    except Exception as e:
        return f"Error fetching player props: {str(e)}"


@tool
def fetch_live_game_stats(
    fixture_id: str,
    player_id: Optional[str] = None,
) -> str:
    """Fetch live in-game statistics using OpticOdds /fixtures/results and /fixtures/player-results.
    
    Args:
        fixture_id: Fixture ID for the game
        player_id: Optional player ID for specific player stats
    
    Returns:
        Formatted string with live game statistics
    """
    try:
        client = get_client()
        
        # Get fixture results
        results = client.get_fixture_results(fixture_id=int(fixture_id))
        
        # Get player results if player_id provided
        player_stats = None
        if player_id:
            player_stats = client.get_player_results(
                fixture_id=int(fixture_id),
                player_id=int(player_id)
            )
        
        # Format response
        formatted = format_live_stats_response(results, player_stats)
        return formatted
    except Exception as e:
        return f"Error fetching live game stats: {str(e)}"


@tool
def fetch_injury_reports(
    sport_id: Optional[str] = None,
    league_id: Optional[str] = None,
    team_id: Optional[str] = None,
) -> str:
    """Fetch current injury reports using OpticOdds /injuries and /injuries/predictions.
    
    Args:
        sport_id: Filter by sport ID
        league_id: Filter by league ID
        team_id: Filter by team ID
    
    Returns:
        Formatted string with injury reports
    """
    try:
        client = get_client()
        
        injuries = client.get_injuries(
            sport=sport_id if sport_id else None,
            league=league_id if league_id else None,
            team=team_id if team_id else None,
        )
        
        # Format response
        formatted = format_injury_response(injuries)
        return formatted
    except Exception as e:
        return f"Error fetching injury reports: {str(e)}"


@tool
def detect_arbitrage_opportunities(
    fixture_id: Optional[str] = None,
    league_id: Optional[str] = None,
    sport_id: Optional[str] = None,
    min_profit_percent: float = 0.0,
) -> str:
    """Identify arbitrage opportunities by comparing /fixtures/odds across sportsbooks.
    
    Args:
        fixture_id: Specific fixture ID
        league_id: Filter by league ID
        sport_id: Filter by sport ID
        min_profit_percent: Minimum profit percentage threshold (default: 0.0)
    
    Returns:
        Formatted string with arbitrage opportunities
    """
    try:
        client = get_client()
        
        odds = client.get_fixture_odds(
            fixture_id=fixture_id if fixture_id else None,
            sport=sport_id if sport_id else None,
            league=league_id if league_id else None,
        )
        
        # Analyze for arbitrage opportunities
        opportunities = find_arbitrage_opportunities(odds, min_profit_percent)
        
        # Format response
        formatted = format_arbitrage_response(opportunities)
        return formatted
    except Exception as e:
        return f"Error detecting arbitrage opportunities: {str(e)}"


@tool
def fetch_futures(
    sport_id: Optional[str] = None,
    league_id: Optional[str] = None,
) -> str:
    """Fetch long-term markets using OpticOdds /futures and /futures/odds.
    
    Args:
        sport_id: Filter by sport ID
        league_id: Filter by league ID
    
    Returns:
        Formatted string with futures markets and odds
    """
    try:
        client = get_client()
        
        futures = client.get_futures(
            sport=sport_id if sport_id else None,
            league=league_id if league_id else None,
        )
        futures_odds = client.get_futures_odds(
            sport=sport_id if sport_id else None,
        )
        
        # Format response
        formatted = format_futures_response(futures, futures_odds)
        return formatted
    except Exception as e:
        return f"Error fetching futures: {str(e)}"


@tool
def fetch_grader(
    fixture_id: str,
    market_id: str,
    selection_id: str,
    future_id: Optional[str] = None,
) -> str:
    """Fetch settlement logic using OpticOdds /grader/odds and /grader/futures.
    
    Args:
        fixture_id: Fixture ID
        market_id: Market ID
        selection_id: Selection ID
        future_id: Optional future ID for futures markets
    
    Returns:
        Formatted string with bet settlement information
    """
    try:
        client = get_client()
        
        if future_id:
            result = client.get_grader_futures(
                future_id=int(future_id),
                selection_id=int(selection_id)
            )
        else:
            result = client.get_grader_odds(
                fixture_id=int(fixture_id),
                market_id=int(market_id),
                selection_id=int(selection_id)
            )
        
        # Format response
        formatted = format_grader_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching grader: {str(e)}"


@tool
def fetch_historical_odds(
    fixture_id: str,
    timestamp: Optional[str] = None,
) -> str:
    """Fetch historical odds data using OpticOdds /fixtures/odds/historical.
    
    Args:
        fixture_id: Fixture ID
        timestamp: Optional timestamp for specific historical point
    
    Returns:
        Formatted string with historical odds data
    """
    try:
        client = get_client()
        
        result = client.get_historical_odds(
            fixture_id=int(fixture_id),
            timestamp=timestamp
        )
        
        # Format response
        formatted = format_historical_odds_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching historical odds: {str(e)}"


@tool
def image_to_bet_analysis(image_data: str) -> str:
    """Analyze betting images and convert to structured data.
    
    Args:
        image_data: Base64 encoded image data or image URL
    
    Returns:
        Formatted string with extracted betting information
    """
    try:
        # This is a placeholder - would need actual image analysis (OCR, vision model, etc.)
        # For now, return a message indicating this needs implementation
        return "Image analysis feature requires implementation. Please provide bet details manually or use other tools to fetch current odds."
    except Exception as e:
        return f"Error analyzing image: {str(e)}"


@tool
def generate_bet_deep_link(
    sportsbook: str,
    fixture_id: str,
    market_id: str,
    selection_id: str,
) -> str:
    """Generate deep links to sportsbook bet pages with pre-filled bet slips using OpticOdds data.
    
    Args:
        sportsbook: Sportsbook name (e.g., 'fanduel', 'draftkings', 'betmgm')
        fixture_id: Fixture ID from OpticOdds
        market_id: Market ID from OpticOdds
        selection_id: Selection ID from OpticOdds
    
    Returns:
        Deep link URL for the sportsbook
    """
    try:
        # Sportsbook deep link patterns
        deep_link_patterns = {
            "fanduel": "https://sportsbook.fanduel.com/addToBetslip?marketId={market_id}&selectionId={selection_id}",
            "draftkings": "https://sportsbook.draftkings.com/betslip?marketId={market_id}&selectionId={selection_id}",
            "betmgm": "https://sports.betmgm.com/betslip?marketId={market_id}&selectionId={selection_id}",
        }
        
        sportsbook_lower = sportsbook.lower()
        if sportsbook_lower not in deep_link_patterns:
            return f"Deep linking not yet supported for {sportsbook}. Supported: {', '.join(deep_link_patterns.keys())}"
        
        pattern = deep_link_patterns[sportsbook_lower]
        deep_link = pattern.format(
            market_id=market_id,
            selection_id=selection_id
        )
        
        return f"Deep link for {sportsbook}: {deep_link}"
    except Exception as e:
        return f"Error generating deep link: {str(e)}"


@tool
def calculate_parlay_odds(
    legs: str,
) -> str:
    """Calculate parlay odds for multiple bet legs using OpticOdds /parlay/odds endpoint.
    
    Args:
        legs: JSON string of parlay legs. Each leg should be a dict with:
            - fixture_id: Fixture ID
            - market_id: Market ID
            - selection_id: Selection ID
            - sportsbook_id: Sportsbook ID (optional)
    
    Example legs format:
        '[{"fixture_id": 123, "market_id": 456, "selection_id": 789}, {"fixture_id": 124, "market_id": 457, "selection_id": 790}]'
    
    Returns:
        Formatted string with parlay odds from multiple sportsbooks
    """
    try:
        client = get_client()
        
        # Parse legs JSON string
        import json
        legs_list = json.loads(legs) if isinstance(legs, str) else legs
        
        if not isinstance(legs_list, list) or len(legs_list) == 0:
            return "Error: legs must be a non-empty list of bet legs"
        
        # Calculate parlay odds
        result = client.calculate_parlay_odds(legs=legs_list)
        
        # Format response for frontend
        formatted = format_parlay_response(result, legs_list)
        return formatted
    except json.JSONDecodeError as e:
        return f"Error parsing legs JSON: {str(e)}"
    except Exception as e:
        return f"Error calculating parlay odds: {str(e)}"


@tool
def read_url_content(url: str) -> str:
    """Read content from URLs for additional context.
    
    Args:
        url: URL to fetch content from
    
    Returns:
        Text content from the URL
    """
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        return response.text[:5000]  # Limit to first 5000 chars
    except Exception as e:
        return f"Error reading URL content: {str(e)}"


# Helper functions for formatting responses

def format_odds_response(data: Dict[str, Any]) -> str:
    """Format odds response for display with structured data for frontend parsing."""
    if not data:
        return "No odds data available"
    
    formatted_lines = []
    fixtures = data.get("data", [])
    
    # Handle case where data might be a single fixture object
    if not isinstance(fixtures, list):
        fixtures = [fixtures] if fixtures else []
    
    # Collect structured data for frontend
    structured_odds = []
    
    for fixture in fixtures:
        if not fixture:
            continue
            
        fixture_info = fixture.get("fixture", {})
        if not fixture_info:
            fixture_info = fixture  # Sometimes fixture data is at top level
        
        fixture_id = fixture_info.get("id")
        home_team_info = fixture_info.get("home_team", {})
        away_team_info = fixture_info.get("away_team", {})
        home_team = home_team_info.get("name", "") if isinstance(home_team_info, dict) else str(home_team_info)
        away_team = away_team_info.get("name", "") if isinstance(away_team_info, dict) else str(away_team_info)
        
        if home_team or away_team:
            formatted_lines.append(f"\n{home_team} vs {away_team}")
        
        markets = fixture.get("markets", [])
        if not isinstance(markets, list):
            markets = [markets] if markets else []
        for market in markets:
            market_type = market.get("market_type", "")
            market_id = market.get("id")
            formatted_lines.append(f"\n{market_type.upper()}:")
            
            selections = market.get("selections", [])
            for selection in selections:
                selection_id = selection.get("id")
                selection_name = selection.get("name", "")
                
                # Handle odds as either a single object or a list
                odds_data = selection.get("odds", [])
                if not isinstance(odds_data, list):
                    odds_data = [odds_data] if odds_data else []
                
                # If no odds, still add the selection
                if not odds_data:
                    formatted_lines.append(f"• {selection_name}: No odds available")
                    structured_odds.append({
                        "fixture_id": fixture_id,
                        "fixture": f"{home_team} vs {away_team}",
                        "market_type": market_type,
                        "market_id": market_id,
                        "selection_id": selection_id,
                        "selection_name": selection_name,
                        "sportsbook_id": None,
                        "sportsbook_name": "Unknown",
                        "american_odds": None,
                        "decimal_odds": None,
                        "deep_link": None,
                    })
                else:
                    # Process each odds entry
                    for odds in odds_data:
                        sportsbook = odds.get("sportsbook", {}) if isinstance(odds, dict) else {}
                        sportsbook_name = sportsbook.get("name", "Unknown") if sportsbook else "Unknown"
                        sportsbook_id = sportsbook.get("id") if sportsbook else None
                        american_odds = odds.get("american", "") if isinstance(odds, dict) else ""
                        decimal_odds = odds.get("decimal", "") if isinstance(odds, dict) else ""
                        deep_link = odds.get("deep_link") if isinstance(odds, dict) else None
                        
                        # Format line with deep link if available
                        odds_line = f"• {selection_name}: {american_odds} ({sportsbook_name})"
                        if deep_link:
                            odds_line += f" [Deep Link: {deep_link}]"
                        formatted_lines.append(odds_line)
                        
                        # Add structured data for frontend (one entry per odds)
                        structured_odds.append({
                            "fixture_id": fixture_id,
                            "fixture": f"{home_team} vs {away_team}",
                            "market_type": market_type,
                            "market_id": market_id,
                            "selection_id": selection_id,
                            "selection_name": selection_name,
                            "sportsbook_id": sportsbook_id,
                            "sportsbook_name": sportsbook_name,
                            "american_odds": american_odds,
                            "decimal_odds": decimal_odds,
                            "deep_link": deep_link,
                        })
    
    # Add structured JSON block for frontend parsing
    if structured_odds:
        formatted_lines.append(f"\n\n<!-- ODDS_DATA_START -->\n{json.dumps({'odds': structured_odds}, indent=2)}\n<!-- ODDS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No odds available"


def format_player_props_response(player_results: Dict[str, Any], odds: Dict[str, Any]) -> str:
    """Format player props response with structured data for frontend parsing."""
    formatted_lines = []
    structured_props = []
    
    if player_results and "data" in player_results:
        players = player_results.get("data", [])
        for player in players:
            player_info = player.get("player", {})
            player_name = player_info.get("name", "Unknown")
            player_id = player_info.get("id")
            formatted_lines.append(f"\n{player_name}:")
            
            stats = player.get("stats", {})
            for stat_name, stat_value in stats.items():
                formatted_lines.append(f"• {stat_name}: {stat_value}")
    
    if odds and "data" in odds:
        formatted_lines.append("\nPlayer Prop Odds:")
        fixtures = odds.get("data", [])
        
        for fixture in fixtures:
            fixture_info = fixture.get("fixture", {})
            fixture_id = fixture_info.get("id")
            markets = fixture.get("markets", [])
            
            for market in markets:
                if market.get("market_type") == "player_props":
                    selections = market.get("selections", [])
                    for selection in selections:
                        player_info = selection.get("player", {})
                        player_name = player_info.get("name", "Unknown")
                        player_id = player_info.get("id")
                        selection_name = selection.get("name", "")
                        selection_id = selection.get("id")
                        market_id = market.get("id")
                        
                        odds_list = selection.get("odds", [])
                        for odds_item in odds_list:
                            sportsbook = odds_item.get("sportsbook", {})
                            sportsbook_name = sportsbook.get("name", "Unknown")
                            sportsbook_id = sportsbook.get("id")
                            american_odds = odds_item.get("american", "")
                            decimal_odds = odds_item.get("decimal", "")
                            
                            formatted_lines.append(f"• {player_name} - {selection_name}: {american_odds} ({sportsbook_name})")
                            
                            structured_props.append({
                                "fixture_id": fixture_id,
                                "player_id": player_id,
                                "player_name": player_name,
                                "market_type": "player_props",
                                "market_id": market_id,
                                "selection_id": selection_id,
                                "selection_name": selection_name,
                                "sportsbook_id": sportsbook_id,
                                "sportsbook_name": sportsbook_name,
                                "american_odds": american_odds,
                                "decimal_odds": decimal_odds,
                            })
    
    # Add structured JSON block for frontend parsing
    if structured_props:
        formatted_lines.append(f"\n\n<!-- PLAYER_PROPS_DATA_START -->\n{json.dumps({'player_props': structured_props}, indent=2)}\n<!-- PLAYER_PROPS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No player props available"


def format_live_stats_response(results: Dict[str, Any], player_stats: Optional[Dict[str, Any]]) -> str:
    """Format live stats response with structured data for frontend parsing."""
    formatted_lines = []
    structured_stats = []
    
    if results and "data" in results:
        results_data = results.get("data", [])
        if not isinstance(results_data, list):
            results_data = [results_data] if results_data else []
            
        for fixture in results_data:
            if not fixture:
                continue
                
            fixture_info = fixture.get("fixture", {})
            if not fixture_info:
                fixture_info = fixture
                
            score = fixture.get("score", {})
            home_team_info = fixture_info.get("home_team", {})
            away_team_info = fixture_info.get("away_team", {})
            home_team = home_team_info.get("name", "") if isinstance(home_team_info, dict) else str(home_team_info)
            away_team = away_team_info.get("name", "") if isinstance(away_team_info, dict) else str(away_team_info)
            home_score = score.get("home", 0) if isinstance(score, dict) else 0
            away_score = score.get("away", 0) if isinstance(score, dict) else 0
            status = fixture.get("status", "Unknown")
            fixture_id = fixture_info.get("id")
            
            formatted_lines.append(f"\n{home_team} {home_score} - {away_score} {away_team}")
            formatted_lines.append(f"Status: {status}")
            
            structured_stats.append({
                "fixture_id": fixture_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "status": status,
            })
    
    if player_stats and "data" in player_stats:
        formatted_lines.append("\nPlayer Stats:")
        players_data = player_stats.get("data", [])
        if not isinstance(players_data, list):
            players_data = [players_data] if players_data else []
            
        for player in players_data:
            if not player:
                continue
                
            player_info = player.get("player", {})
            if not player_info:
                player_info = player
                
            player_name = player_info.get("name", "Unknown") if isinstance(player_info, dict) else "Unknown"
            player_id = player_info.get("id") if isinstance(player_info, dict) else None
            stats = player.get("stats", {})
            
            formatted_lines.append(f"\n{player_name}:")
            player_stat_dict = {}
            for stat_name, stat_value in stats.items():
                formatted_lines.append(f"• {stat_name}: {stat_value}")
                player_stat_dict[stat_name] = stat_value
            
            structured_stats.append({
                "player_id": player_id,
                "player_name": player_name,
                "stats": player_stat_dict,
            })
    
    # Add structured JSON block for frontend parsing
    if structured_stats:
        formatted_lines.append(f"\n\n<!-- STATS_DATA_START -->\n{json.dumps({'stats': structured_stats}, indent=2)}\n<!-- STATS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No live stats available"


def format_injury_response(data: Dict[str, Any]) -> str:
    """Format injury response."""
    if not data or "data" not in data:
        return "No injury data available"
    
    formatted_lines = []
    injuries = data.get("data", [])
    
    for injury in injuries:
        player = injury.get("player", {})
        team = injury.get("team", {})
        formatted_lines.append(f"\n{player.get('name', 'Unknown')} ({team.get('name', 'Unknown')})")
        formatted_lines.append(f"Status: {injury.get('status', 'Unknown')}")
        formatted_lines.append(f"Type: {injury.get('injury_type', 'Unknown')}")
        if injury.get("expected_return"):
            formatted_lines.append(f"Expected Return: {injury.get('expected_return')}")
    
    return "\n".join(formatted_lines) if formatted_lines else "No injuries reported"


def find_arbitrage_opportunities(odds_data: Dict[str, Any], min_profit: float) -> List[Dict[str, Any]]:
    """Find arbitrage opportunities in odds data."""
    opportunities = []
    
    if not odds_data or "data" not in odds_data:
        return opportunities
    
    # This is a simplified arbitrage detection
    # Real implementation would need more sophisticated calculation
    for fixture in odds_data.get("data", []):
        markets = fixture.get("markets", [])
        for market in markets:
            if market.get("market_type") == "moneyline":
                selections = market.get("selections", [])
                if len(selections) >= 2:
                    # Check for arbitrage opportunity
                    # Simplified: would need proper implied probability calculation
                    pass
    
    return opportunities


def format_arbitrage_response(opportunities: List[Dict[str, Any]]) -> str:
    """Format arbitrage opportunities response."""
    if not opportunities:
        return "No arbitrage opportunities found"
    
    formatted_lines = ["Arbitrage Opportunities:"]
    for opp in opportunities:
        formatted_lines.append(f"\n{opp.get('description', 'Opportunity')}")
        formatted_lines.append(f"Profit: {opp.get('profit_percent', 0)}%")
    
    return "\n".join(formatted_lines)


def format_futures_response(futures: Dict[str, Any], futures_odds: Dict[str, Any]) -> str:
    """Format futures response."""
    formatted_lines = []
    
    if futures and "data" in futures:
        for future in futures.get("data", []):
            formatted_lines.append(f"\n{future.get('name', 'Unknown')}")
            formatted_lines.append(f"Type: {future.get('type', 'Unknown')}")
    
    if futures_odds and "data" in futures_odds:
        formatted_lines.append("\nFutures Odds:")
        # Format odds similar to format_odds_response
    
    return "\n".join(formatted_lines) if formatted_lines else "No futures available"


def format_grader_response(data: Dict[str, Any]) -> str:
    """Format grader response."""
    if not data:
        return "No grader data available"
    
    formatted_lines = []
    formatted_lines.append(f"Status: {data.get('status', 'Unknown')}")
    formatted_lines.append(f"Result: {data.get('result', 'Unknown')}")
    
    return "\n".join(formatted_lines)


def format_historical_odds_response(data: Dict[str, Any]) -> str:
    """Format historical odds response."""
    if not data or "data" not in data:
        return "No historical odds available"
    
    # Similar formatting to format_odds_response but with timestamps
    return format_odds_response(data)


def format_parlay_response(data: Dict[str, Any], legs: List[Dict[str, Any]]) -> str:
    """Format parlay response with structured data for frontend parsing."""
    if not data:
        return "No parlay data available"
    
    formatted_lines = []
    structured_parlays = []
    
    # Extract parlay information
    parlay_odds = data.get("data", []) if isinstance(data.get("data"), list) else [data.get("data", {})]
    
    formatted_lines.append("\nParlay Odds:")
    
    for parlay in parlay_odds:
        if not parlay:
            continue
            
        sportsbook = parlay.get("sportsbook", {})
        sportsbook_name = sportsbook.get("name", "Unknown") if sportsbook else "Unknown"
        sportsbook_id = sportsbook.get("id") if sportsbook else None
        american_odds = parlay.get("american", "")
        decimal_odds = parlay.get("decimal", "")
        implied_probability = parlay.get("implied_probability", "")
        
        formatted_lines.append(f"\n{sportsbook_name}:")
        formatted_lines.append(f"• Combined Odds: {american_odds} (Decimal: {decimal_odds})")
        if implied_probability:
            formatted_lines.append(f"• Implied Probability: {implied_probability}")
        
        # Calculate potential payout for $100 bet
        if decimal_odds:
            try:
                payout = float(decimal_odds) * 100
                formatted_lines.append(f"• $100 bet would pay: ${payout:.2f}")
            except (ValueError, TypeError):
                pass
        
        # Add structured data for frontend
        structured_parlays.append({
            "sportsbook_id": sportsbook_id,
            "sportsbook_name": sportsbook_name,
            "american_odds": american_odds,
            "decimal_odds": decimal_odds,
            "implied_probability": implied_probability,
            "legs": legs,  # Include original legs for reference
        })
    
    # Add structured JSON block for frontend parsing
    if structured_parlays:
        formatted_lines.append(f"\n\n<!-- PARLAY_DATA_START -->\n{json.dumps({'parlays': structured_parlays}, indent=2)}\n<!-- PARLAY_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No parlay odds available"


def format_fixtures_response(data: Dict[str, Any]) -> str:
    """Format fixtures response for display with structured data for frontend parsing."""
    if not data:
        return "No fixtures data available"
    
    formatted_lines = []
    fixtures = data.get("data", [])
    
    # Handle case where data might be a single fixture object
    if not isinstance(fixtures, list):
        fixtures = [fixtures] if fixtures else []
    
    if not fixtures:
        return "No upcoming games found"
    
    # Collect structured data for frontend
    structured_fixtures = []
    
    formatted_lines.append("Upcoming Games Schedule:\n")
    
    for fixture in fixtures:
        if not fixture:
            continue
        
        fixture_id = fixture.get("id")
        home_team_info = fixture.get("home_team", {})
        away_team_info = fixture.get("away_team", {})
        
        home_team = home_team_info.get("name", "Unknown") if isinstance(home_team_info, dict) else str(home_team_info)
        away_team = away_team_info.get("name", "Unknown") if isinstance(away_team_info, dict) else str(away_team_info)
        
        # Get date/time information
        start_time = fixture.get("start_time")
        date = fixture.get("date")
        status = fixture.get("status", "Scheduled")
        league_info = fixture.get("league", {})
        league_name = league_info.get("name", "") if isinstance(league_info, dict) else ""
        
        # Format game information
        game_line = f"{away_team} @ {home_team}"
        if date:
            game_line += f" | {date}"
        if start_time:
            game_line += f" | {start_time}"
        if status:
            game_line += f" | Status: {status}"
        
        formatted_lines.append(f"\n{game_line}")
        if fixture_id:
            formatted_lines.append(f"Fixture ID: {fixture_id}")
        if league_name:
            formatted_lines.append(f"League: {league_name}")
        
        # Add to structured data
        structured_fixtures.append({
            "fixture_id": fixture_id,
            "home_team": home_team,
            "away_team": away_team,
            "date": date,
            "start_time": start_time,
            "status": status,
            "league": league_name,
        })
    
    # Add structured JSON block for frontend parsing
    if structured_fixtures:
        formatted_lines.append(f"\n\n<!-- FIXTURES_DATA_START -->\n{json.dumps({'fixtures': structured_fixtures}, indent=2)}\n<!-- FIXTURES_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No fixtures available"

