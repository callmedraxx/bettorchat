"""
MCP-compatible betting tools wrapping OpticOdds API.
"""
import json
import base64
import re
import logging
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from langchain.tools import tool
import httpx
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    from backports.zoneinfo import ZoneInfo

from app.core.opticodds_client import OpticOddsClient
from app.core.fixture_stream import fixture_stream_manager
from app.core.odds_stream import odds_stream_manager
from app.core.tool_result_storage import store_tool_result
from app.core.tool_result_db import save_tool_result_to_db
from app.core.async_db_ops import save_tool_result_async, save_odds_async, save_fixtures_async

# Logger for betting tools
logger = logging.getLogger(__name__)

# Context variable to store current session_id (thread_id) for tools
_current_session_id: ContextVar[Optional[str]] = ContextVar('current_session_id', default=None)


# Initialize OpticOdds client (singleton pattern)
_client: Optional[OpticOddsClient] = None

# Simple in-memory cache for user timezones (in production, this would be in user preferences)
_user_timezone_cache: Dict[str, str] = {}

# Cache for available sportsbooks (to avoid repeated API calls)
_sportsbooks_cache: Optional[List[str]] = None
_sportsbooks_cache_timestamp: Optional[float] = None
_sportsbooks_cache_ttl: float = 3600.0  # Cache for 1 hour


def get_client() -> OpticOddsClient:
    """Get or create OpticOdds client."""
    global _client
    if _client is None:
        _client = OpticOddsClient()
    return _client





def get_default_sportsbooks(sport_id: Optional[str] = None, league_id: Optional[str] = None) -> List[str]:
    """Get default sportsbooks by fetching from API, with caching and fallback.
    
    Fetches available sportsbooks from OpticOdds API and returns the first 3-5 sportsbook IDs/names.
    Uses caching to avoid repeated API calls. Falls back to hardcoded defaults if API call fails.
    
    Args:
        sport_id: Optional sport ID to filter sportsbooks by sport
        league_id: Optional league ID (not used for filtering, but kept for consistency)
    
    Returns:
        List of sportsbook IDs/names (up to 5)
    """
    import time
    
    global _sportsbooks_cache, _sportsbooks_cache_timestamp
    
    # Check cache validity
    current_time = time.time()
    if (_sportsbooks_cache is not None and 
        _sportsbooks_cache_timestamp is not None and 
        (current_time - _sportsbooks_cache_timestamp) < _sportsbooks_cache_ttl):
        return _sportsbooks_cache[:5]  # Return up to 5 sportsbooks
    
    # Try to fetch from API
    try:
        client = get_client()
        result = client.get_active_sportsbooks(sport=sport_id if sport_id else None)
        
        sportsbooks_data = result.get("data", [])
        if not isinstance(sportsbooks_data, list):
            sportsbooks_data = [sportsbooks_data] if sportsbooks_data else []
        
        if sportsbooks_data:
            # Extract sportsbook IDs or names
            default_sportsbooks = []
            for sb in sportsbooks_data[:5]:  # Take first 5
                if not sb:
                    continue
                # Prefer ID, fallback to name, then slug
                sportsbook_id = sb.get("id")
                sportsbook_name = sb.get("name")
                sportsbook_slug = sb.get("slug")
                
                if sportsbook_id:
                    default_sportsbooks.append(str(sportsbook_id))
                elif sportsbook_name:
                    default_sportsbooks.append(sportsbook_name)
                elif sportsbook_slug:
                    default_sportsbooks.append(sportsbook_slug)
            
            if default_sportsbooks:
                # Update cache
                _sportsbooks_cache = default_sportsbooks
                _sportsbooks_cache_timestamp = current_time
                return default_sportsbooks[:5]
    except Exception:
        # If API call fails, fall through to hardcoded defaults
        pass
    
    # Fallback to hardcoded defaults if API fetch fails
    fallback_sportsbooks = ["DraftKings", "FanDuel", "BetMGM"]
    _sportsbooks_cache = fallback_sportsbooks
    _sportsbooks_cache_timestamp = current_time
    return fallback_sportsbooks


@tool
def build_opticodds_url(
    tool_name: str,
    sportsbook: Optional[str] = None,
    fixture_id: Optional[str] = None,
    team_id: Optional[str] = None,
    player_id: Optional[str] = None,
    market: Optional[str] = None,
    league: Optional[str] = None,
    start_date_after: Optional[str] = None,
    start_date_before: Optional[str] = None,
    **kwargs: Any
) -> str:
    """🚨 MANDATORY: Build and return the OpticOdds API proxy URL for a tool call.
    
    ⚠️ CRITICAL: You MUST call this tool BEFORE calling ANY data-fetching tool (fetch_live_odds, fetch_upcoming_games, fetch_player_props, etc.).
    This is a HARD REQUIREMENT - the frontend needs the URL to display data.
    
    ❌ DO NOT call fetch_live_odds, fetch_upcoming_games, or any other data-fetching tool without first calling this tool.
    
    🚨 MANDATORY WORKFLOW FOR PLAYER-SPECIFIC REQUESTS:
    When user requests odds for a specific player (e.g., "show me odds for Jameson Williams", "Jameson Williams props"):
    ❌ WRONG: Do NOT call build_opticodds_url or fetch_live_odds without player_id
    ❌ WRONG: Do NOT fetch all player props and then extract player info from the response
    ✅ CORRECT WORKFLOW (MANDATORY):
    1. FIRST: Call fetch_players(league="nfl", player_name="Jameson Williams") to get player_id
       - For NFL, this uses fast database lookup (instant)
       - Extract the player_id from the response (e.g., "ABC123...")
    2. THEN: Call build_opticodds_url with player_id included
       - Include: player_id, fixture_id (if known), sportsbook, market
       - The URL MUST include player_id so frontend gets only that player's odds
    3. FINALLY: Call fetch_live_odds with the same player_id
       - Use the exact same parameters including player_id
    
    This tool generates the URL that the frontend should use to fetch data from OpticOdds.
    You MUST call this tool BEFORE calling the actual data-fetching tool to send the URL to the frontend first.
    
    Args:
        tool_name: Name of the tool (e.g., 'fetch_live_odds', 'fetch_upcoming_games', 'fetch_player_props')
        sportsbook: Sportsbook name(s), comma-separated (e.g., 'draftkings,fanduel,betmgm')
        fixture_id: Fixture ID for the game (REQUIRED for player-specific requests)
        team_id: Team ID (optional)
        player_id: 🚨 REQUIRED for player-specific requests. Player ID obtained from fetch_players(league=..., player_name=...).
                   ⚠️ CRITICAL: When user requests odds for a specific player:
                   - You MUST call fetch_players FIRST to get the player_id
                   - Do NOT proceed without player_id - the frontend needs it in the URL
                   - The URL will include player_id so the frontend can filter odds for that specific player only
                   - Without player_id, the frontend will receive ALL player props, not just the requested player
        market: Market type(s), comma-separated (e.g., 'Moneyline,Spread,Total' or 'Player Points,Player Receptions')
        league: League name (e.g., 'nfl', 'nba')
        base_id: Base ID for player (fastest route for specific player info). Get this from stored player data in database.
        start_date_after: Start date filter (ISO format)
        start_date_before: End date filter (ISO format)
        **kwargs: Any other parameters that would be passed to the actual tool
        
    Returns:
        The proxy URL string that the frontend should use to fetch the data.
        Format: /api/v1/opticodds/proxy/{endpoint}?params...
        
    Example for player-specific request ("show me odds for Jameson Williams"):
        # Step 1: Get player_id FIRST (MANDATORY - do not skip this step)
        fetch_players(league="nfl", player_name="Jameson Williams")
        # Returns: player_id="ABC123..." (fast database lookup for NFL)
        
        # Step 2: Call this tool with player_id included (MANDATORY)
        build_opticodds_url(
            tool_name="fetch_live_odds",
            sportsbook="draftkings,fanduel,betmgm",
            fixture_id="20251127E5C64DE0",  # Get from fetch_upcoming_games if not provided
            player_id="ABC123",  # 🚨 CRITICAL: Must include player_id for player-specific requests
            market="Player Points,Player Receptions,Player Touchdowns"
        )
        # Returns: "URL: /api/v1/opticodds/proxy/fixtures/odds?sportsbook=draftkings&sportsbook=fanduel&sportsbook=betmgm&fixture_id=20251127E5C64DE0&player_id=ABC123&market=Player+Points&market=Player+Receptions&market=Player+Touchdowns"
        
        # Step 3: THEN call the actual tool with the same parameters (including player_id)
        fetch_live_odds(
            sportsbook="draftkings,fanduel,betmgm",
            fixture_id="20251127E5C64DE0",
            player_id="ABC123",  # 🚨 CRITICAL: Must include player_id
            market="Player Points,Player Receptions,Player Touchdowns"
        )
    """
    try:
        from app.core.url_builder import build_opticodds_url_from_tool_call
        from app.core.market_names import resolve_market_names
        
        # Build args dict from explicit parameters and kwargs
        args_dict = {}
        if sportsbook:
            args_dict["sportsbook"] = sportsbook
        if fixture_id:
            args_dict["fixture_id"] = fixture_id
        if team_id:
            args_dict["team_id"] = team_id
        if player_id:
            args_dict["player_id"] = player_id
        if market:
            # Resolve market names from user-friendly terms to correct API names
            args_dict["market"] = resolve_market_names(market)
        if league:
            args_dict["league"] = league
        if start_date_after:
            args_dict["start_date_after"] = start_date_after
        if start_date_before:
            args_dict["start_date_before"] = start_date_before
        
        # Add any additional kwargs (but filter out None/empty values)
        for key, value in kwargs.items():
            if value is not None and value != "":
                args_dict[key] = value
        
        # Handle case where AI passes tool_args as a single dict parameter (legacy support)
        if "tool_args" in args_dict and isinstance(args_dict.get("tool_args"), dict):
            # Extract the nested tool_args and merge with other params
            nested_args = args_dict.pop("tool_args")
            # Filter out None/empty values from nested args too
            for key, value in nested_args.items():
                if value is not None and value != "":
                    args_dict[key] = value
        
        # Validate required parameters based on tool_name before building URL
        # Note: sportsbook defaults are handled by URL builder, so we don't require it here
        missing_params = []
        if tool_name == "fetch_live_odds":
            # Requires: at least one of (fixture_id, team_id, player_id)
            # sportsbook is optional - URL builder will add defaults (draftkings, caesars, betmgm, fanduel)
            if not any(key in args_dict and args_dict.get(key) for key in ["fixture_id", "team_id", "player_id"]):
                missing_params.append("at least one of: fixture_id, team_id, or player_id (required)")
            
            # ⚠️ WARNING: Check for player prop markets - if user requested a specific player, player_id should be included
            # Note: We don't block this because user might want ALL player props, not just one player
            market = args_dict.get("market", "")
            if market and isinstance(market, str):
                # Check if market contains player prop markets
                market_lower = market.lower()
                is_player_market = (
                    "player" in market_lower and (
                        "points" in market_lower or
                        "receptions" in market_lower or
                        "touchdowns" in market_lower or
                        "yards" in market_lower or
                        "rushing" in market_lower or
                        "passing" in market_lower or
                        "receiving" in market_lower or
                        "anytime" in market_lower or
                        "total" in market_lower
                    )
                )
                
                if is_player_market:
                    if "player_id" not in args_dict or not args_dict.get("player_id"):
                        logger.warning(
                            f"[build_opticodds_url] ⚠️ WARNING: Player prop markets detected ('{market}') but player_id is not included. "
                            "If the user requested odds for a SPECIFIC player (e.g., 'Jameson Williams'), you MUST call fetch_players first "
                            "to get player_id, then include it here. If the user wants ALL player props, this is correct."
                        )
        elif tool_name == "fetch_player_props":
            # Requires: at least one of (fixture_id, player_id)
            # sportsbook is optional - URL builder will add defaults (draftkings, caesars, betmgm, fanduel)
            if not any(key in args_dict and args_dict.get(key) for key in ["fixture_id", "player_id"]):
                missing_params.append("at least one of: fixture_id or player_id (required)")
        elif tool_name == "fetch_upcoming_games":
            # For fetch_upcoming_games, validation is minimal - just need league or fixture_id
            # Skip strict validation to reduce latency
            pass
        
        if missing_params:
            return f"Error: Could not build URL for {tool_name}. Missing required parameters: {', '.join(missing_params)}. Args provided: {list(args_dict.keys())}"
        
        # Build the URL using the URL builder
        url = build_opticodds_url_from_tool_call(tool_name, args_dict)
        
        if url:
            # Return URL in a shorter format to reduce token usage and latency
            # The frontend will extract this URL from the response
            return f"URL: {url}"
        else:
            # URL builder returned None - provide more detailed error
            if tool_name == "fetch_live_odds":
                has_fixture = "fixture_id" in args_dict and args_dict.get("fixture_id")
                has_team = "team_id" in args_dict and args_dict.get("team_id")
                has_player = "player_id" in args_dict and args_dict.get("player_id")
                details = []
                # Note: sportsbook is optional - URL builder adds defaults
                if not (has_fixture or has_team or has_player):
                    details.append("no valid identifier (fixture_id, team_id, or player_id)")
                
                # If details is empty, parameters appear valid but URL builder failed
                if not details:
                    # Log the actual values for debugging
                    logger.warning(f"[build_opticodds_url] URL builder returned None despite valid-looking parameters. sportsbook={args_dict.get('sportsbook')}, fixture_id={args_dict.get('fixture_id')}, team_id={args_dict.get('team_id')}, player_id={args_dict.get('player_id')}")
                    details.append("URL builder validation failed (check parameter formats)")
                
                return f"Error: Could not build URL for {tool_name}. {'; '.join(details)}. Args provided: {list(args_dict.keys())}"
            else:
                return f"Error: Could not build URL for {tool_name}. Required parameters may be missing or invalid. Args provided: {list(args_dict.keys())}"
    except Exception as e:
        logger.error(f"[build_opticodds_url] Error building URL: {e}", exc_info=True)
        return f"Error building URL: {str(e)}"


@tool
def fetch_live_odds(
    sportsbook: str,
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,
    fixtures: Optional[str] = None,
    market: Optional[str] = None,
    player_id: Optional[str] = None,
    team_id: Optional[str] = None,
    session_id: Optional[str] = None,
    stream_output: bool = True,
) -> str:
    """Fetch live betting odds for fixtures using OpticOdds /fixtures/odds endpoint.
    
    🚨 MANDATORY WORKFLOW FOR PLAYER-SPECIFIC REQUESTS:
    When the user requests odds for a specific player (e.g., "show me odds for Jameson Williams", "Jameson Williams props"):
    
    ❌ WRONG APPROACH (DO NOT DO THIS):
    - Do NOT call this tool without player_id
    - Do NOT fetch all player props and then extract player info from the response
    - Do NOT build URL without player_id - frontend will receive ALL player props, not just the requested player
    
    ✅ CORRECT WORKFLOW (MANDATORY - FOLLOW THIS EXACTLY):
    1. FIRST: Call fetch_players(league="nfl", player_name="Jameson Williams") to get player_id
       - For NFL, this uses fast database lookup (instant, no API call needed)
       - Extract the player_id from the response (e.g., "ABC123...")
       - If you have team info, use: fetch_teams(league="nfl", team_name="Detroit Lions") first, then fetch_players with team_id
    2. THEN: Call build_opticodds_url with player_id included
       - Include: player_id (REQUIRED), fixture_id (if known), sportsbook, market
       - The URL MUST include player_id so frontend gets only that player's odds
    3. FINALLY: Call this tool (fetch_live_odds) with the same player_id
       - Use the exact same parameters including player_id
       - This ensures the frontend receives odds for ONLY the requested player
    
    The player_id MUST be included in both the URL and this tool call so the frontend can filter odds for that specific player.
    Do NOT try to extract player information from odds data - get the player_id first, then request odds with it.
    
    IMPORTANT: 
    - sportsbook is REQUIRED (at least 1, max 5). Pass comma-separated string (e.g., "DraftKings,FanDuel").
    - If requesting odds for fixtures, fixture_id must be provided (up to 5 fixture_ids per request).
    - API requires at least one of: fixture_id, team_id, or player_id AND at least 1 sportsbook.
    - For player-specific requests: ALWAYS provide player_id (obtained from fetch_players) along with fixture_id
    - If market is not provided and fixture_id and sportsbook are provided, this tool will automatically fetch 
      available markets for that specific fixture and sportsbook combination, then select multiple markets 
      (at least 2-3, preferring common markets like "Moneyline", "Point Spread", "Total Points") to provide 
      comprehensive odds coverage while reducing data volume.
    
    Args:
        sportsbook: REQUIRED. Comma-separated list of sportsbook IDs or names (max 5).
                   Example: "DraftKings,FanDuel,BetMGM"
        fixture_id: Single fixture ID or comma-separated list of fixture IDs (up to 5).
                   Example: "20251127E5C64DE0" or "20251127E5C64DE0,20251127C95F3929"
                   REQUIRED when requesting player-specific odds (use with player_id).
        fixture: Full fixture object as JSON string (alternative to fixture_id). 
                 If provided, fixture_id will be extracted from it.
        fixtures: JSON string containing multiple full fixture objects (array, up to 5).
                 If provided, fixture_ids will be extracted and odds fetched for all.
        market: Optional. Comma-separated list of MARKET NAMES (e.g., 'Moneyline,Player Points,Total Points').
               ⚠️ IMPORTANT: Market names are automatically resolved from user-friendly terms to correct API names.
               - ✅ CORRECT: Use user-friendly terms like "total points", "spread", "moneyline" - they will be automatically resolved to "Total Points", "Point Spread", "Moneyline"
               - ✅ CORRECT: "Player Points", "Player Receptions", "Moneyline" (actual market names - also work)
               - ❌ WRONG: "player_total", "player_yes_no", "player_only" (these are market type names, not market names)
               - ❌ WRONG: "Total" (should be "Total Points" or just use "total points" and it will be resolved)
               Common markets are automatically resolved - you don't need to call fetch_available_markets for common requests like "total points", "spread", "moneyline".
               If not provided and fixture_id and sportsbook are provided, automatically fetches available markets 
               for that specific fixture and sportsbook combination, then selects multiple markets (at least 2-3).
               If not provided and no fixture_id, returns all available markets (not recommended - large response).
        player_id: REQUIRED for player-specific requests. Player ID obtained from fetch_players(league=..., player_name=...).
                   ⚠️ CRITICAL: When user requests odds for a specific player:
                   - First call fetch_players to get the player_id
                   - Then pass that player_id to this tool
                   - Include player_id in build_opticodds_url so the frontend receives the correct URL
                   Example: If user says "show me odds for Jameson Williams", do:
                   1. fetch_players(league="nfl", player_name="Jameson Williams") → get player_id
                   2. build_opticodds_url(..., player_id=player_id, fixture_id=...) → build URL with player_id
                   3. fetch_live_odds(..., player_id=player_id, fixture_id=...) → fetch odds with player_id
        team_id: Optional. Team ID to filter odds for a specific team.
        session_id: Optional session identifier for SSE streaming. Defaults to "default".
        stream_output: Whether to emit odds data to SSE stream. Set to False when calling as intermediate step.
                      Defaults to True. Only set to True for the final tool call that directly answers user's request.
    
    Returns:
        Full JSON data with odds from multiple sportsbooks, including Moneyline, Point Spread/Spread, and Total Points when available.
        The response includes a formatted summary of the odds data.
        Spread odds are automatically included when available. Odds data is automatically emitted to SSE stream if stream_output=True.
    """
    try:
        from app.core.market_names import resolve_market_names
        
        # Resolve market names from user-friendly terms to correct API names
        if market and isinstance(market, str):
            market = resolve_market_names(market)
        
        # ⚠️ WARNING: Check for player prop markets - if user requested a specific player, player_id should be included
        # Note: We don't block this because user might want ALL player props, not just one player
        if market and isinstance(market, str):
            # Check if market contains player prop markets
            market_lower = market.lower()
            is_player_market = (
                "player" in market_lower and (
                    "points" in market_lower or
                    "receptions" in market_lower or
                    "touchdowns" in market_lower or
                    "yards" in market_lower or
                    "rushing" in market_lower or
                    "passing" in market_lower or
                    "receiving" in market_lower or
                    "anytime" in market_lower or
                    "total" in market_lower
                )
            )
            
            if is_player_market and not player_id:
                logger.warning(
                    f"[fetch_live_odds] ⚠️ WARNING: Player prop markets detected ('{market}') but player_id is not included. "
                    "If the user requested odds for a SPECIFIC player (e.g., 'Jameson Williams'), you MUST call fetch_players first "
                    "to get player_id, then include it here. If the user wants ALL player props, this is correct."
                )
        
        client = get_client()
        
        # Process sportsbook - REQUIRED, split comma-separated, limit to 5
        if not sportsbook:
            return "Error: sportsbook is required. Provide at least 1 sportsbook (max 5), e.g., 'DraftKings,FanDuel'"
        
        if isinstance(sportsbook, str) and ',' in sportsbook:
            resolved_sportsbook = [sb.strip().lower() for sb in sportsbook.split(',') if sb.strip()][:5]
        elif isinstance(sportsbook, str):
            resolved_sportsbook = [sportsbook.strip().lower()]
        else:
            resolved_sportsbook = [str(sb).strip().lower() for sb in (list(sportsbook)[:5] if isinstance(sportsbook, (list, tuple)) else [sportsbook])]
        
        if not resolved_sportsbook:
            return "Error: Invalid sportsbook. Provide at least 1 sportsbook name or ID."
        
        # Process market parameter (optional)
        resolved_market = None
        if market:
            if isinstance(market, str) and ',' in market:
                resolved_market = [m.strip() for m in market.split(',') if m.strip()]
            elif isinstance(market, str):
                resolved_market = [market.strip()]
            else:
                resolved_market = market if isinstance(market, list) else [str(market)]
        
        # Collect fixture IDs (up to 5)
        fixture_ids_list = []
        
        # Extract from fixtures parameter (JSON array of fixture objects)
        if fixtures:
            try:
                fixtures_data = json.loads(fixtures) if isinstance(fixtures, str) else fixtures
                if isinstance(fixtures_data, list):
                    for fixture_obj in fixtures_data[:5]:  # Limit to 5
                        if isinstance(fixture_obj, dict):
                            fid = extract_fixture_id(json.dumps(fixture_obj))
                            if fid and fid not in fixture_ids_list:
                                fixture_ids_list.append(fid)
                elif isinstance(fixtures_data, dict):
                    fid = extract_fixture_id(json.dumps(fixtures_data))
                    if fid:
                        fixture_ids_list.append(fid)
            except Exception:
                pass
        
        # Extract from fixture parameter (single fixture object)
        if fixture and not fixture_ids_list:
            try:
                fixture_obj = json.loads(fixture) if isinstance(fixture, str) else fixture
                if isinstance(fixture_obj, dict):
                    fid = extract_fixture_id(json.dumps(fixture_obj) if isinstance(fixture, str) else json.dumps(fixture_obj))
                    if fid:
                        fixture_ids_list.append(fid)
            except Exception:
                pass
        
        # Extract from fixture_id parameter (single or comma-separated)
        if fixture_id:
            if isinstance(fixture_id, str) and ',' in fixture_id:
                # Comma-separated list
                ids = [fid.strip() for fid in fixture_id.split(',') if fid.strip()][:5]
                for fid in ids:
                    if fid not in fixture_ids_list:
                        fixture_ids_list.append(fid)
            else:
                # Single fixture ID
                fid = extract_fixture_id(fixture_id) if fixture_id else None
                if fid and fid not in fixture_ids_list:
                    fixture_ids_list.append(fid)
        
        # Limit to 5 fixture IDs per API requirement
        fixture_ids_list = fixture_ids_list[:5]
        
        # API requires at least one of: fixture_id, team_id, or player_id
        if not fixture_ids_list and not team_id and not player_id:
            return "Error: Must provide at least one of: fixture_id, fixtures, fixture, team_id, or player_id"
        
        # Check if this is for NFL - if so, use database instead of API
        is_nfl = False
        if fixture_ids_list:
            # Check if fixtures are NFL by querying database
            try:
                from app.core.database import SessionLocal
                from app.models.nfl_fixture import NFLFixture
                db = SessionLocal()
                try:
                    # Check if any fixture_id exists in NFL fixtures table
                    nfl_fixture = db.query(NFLFixture).filter(NFLFixture.id.in_(fixture_ids_list[:1])).first()
                    if nfl_fixture:
                        is_nfl = True
                        logger.info(f"[fetch_live_odds] Detected NFL fixture(s), using database instead of API")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"[fetch_live_odds] Error checking if NFL: {e}, falling back to API")
        
        # For NFL, use database query instead of API
        if is_nfl and fixture_ids_list:
            try:
                from app.core.odds_db_query import query_odds_from_db
                from app.core.market_names import resolve_market_names
                
                # Resolve market names to market_ids if needed
                resolved_market_ids = None
                resolved_market_category = None
                if resolved_market:
                    # Try to map market names to market_category
                    # Support multiple market categories
                    market_categories = []
                    market_lower = " ".join(resolved_market).lower() if isinstance(resolved_market, list) else resolved_market.lower()
                    market_list = resolved_market if isinstance(resolved_market, list) else [resolved_market]
                    
                    for market in market_list:
                        market_str = str(market).lower()
                        if "moneyline" in market_str or "ml" in market_str:
                            market_categories.append("moneyline")
                        elif "spread" in market_str or "point spread" in market_str:
                            market_categories.append("spread")
                        elif "total" in market_str and "team total" not in market_str:
                            market_categories.append("total")
                        elif "team total" in market_str:
                            market_categories.append("team_total")
                        elif "player" in market_str:
                            market_categories.append("player_prop")
                    
                    # Use list if multiple categories, single value if one
                    if len(market_categories) > 1:
                        resolved_market_category = list(set(market_categories))  # Remove duplicates
                    elif len(market_categories) == 1:
                        resolved_market_category = market_categories[0]
                
                # Handle multiple player_ids if provided as comma-separated string
                player_ids_list = None
                if player_id:
                    if isinstance(player_id, str) and ',' in player_id:
                        player_ids_list = [pid.strip() for pid in player_id.split(',') if pid.strip()]
                    elif isinstance(player_id, list):
                        player_ids_list = player_id
                    else:
                        player_ids_list = [str(player_id)]
                
                # Query database
                result = query_odds_from_db(
                    fixture_id=fixture_ids_list,
                    sportsbook=resolved_sportsbook[0] if resolved_sportsbook and len(resolved_sportsbook) == 1 else None,  # For now, handle single sportsbook
                    market=resolved_market[0] if resolved_market and len(resolved_market) == 1 else None,
                    market_category=resolved_market_category,
                    player_id=player_ids_list,
                    team_id=str(team_id) if team_id else None,
                    limit=1000,
                )
                
                # Check if response has data
                response_data = result.get("data", [])
                if not response_data:
                    return f"No odds data found in database for the specified criteria.\n\nRequest parameters:\n  - fixture_id: {fixture_ids_list}\n  - sportsbook: {resolved_sportsbook}\n  - market: {resolved_market}\n  - player_id: {player_id}\n  - team_id: {team_id}\n\nPossible reasons:\n- The fixture(s) may not have odds stored yet (odds are updated every 24 hours)\n- The sportsbook(s) may not have odds for this fixture\n- Try different sportsbooks or check if the fixture exists"
                
                # Automatically emit odds data to SSE stream (only if stream_output=True)
                if stream_output:
                    session = session_id or "default"
                    try:
                        if result and result.get("data"):
                            odds_stream_manager.push_odds_sync(session, result)
                    except Exception as emit_error:
                        # Don't fail the whole request if emit fails
                        pass
                
                # Create summary
                fixture_count = len(response_data)
                summary_parts = [f"Found odds for {fixture_count} fixture(s) from database."]
                
                if response_data and len(response_data) > 0:
                    first_fixture = response_data[0]
                    if isinstance(first_fixture, dict):
                        home_team = first_fixture.get("home_team_display", "Home")
                        away_team = first_fixture.get("away_team_display", "Away")
                        summary_parts.append(f"Match: {away_team} vs {home_team}.")
                
                json_response = " ".join(summary_parts)
                
                # Store in database for retrieval
                session = session_id or _current_session_id.get() or "default"
                import time
                temp_tool_call_id = f"temp_{session}_{int(time.time() * 1000)}"
                try:
                    save_tool_result_async(
                        tool_call_id=temp_tool_call_id,
                        session_id=session,
                        tool_name="fetch_live_odds",
                        full_result=json_response,
                        structured_data=result
                    )
                    store_tool_result(temp_tool_call_id, json_response)
                except Exception as store_error:
                    logger.warning(f"[fetch_live_odds] Failed to queue tool result save: {store_error}")
                
                return json_response
                
            except Exception as db_error:
                logger.error(f"[fetch_live_odds] Error querying database: {db_error}", exc_info=True)
                # Fall through to API call as fallback
                logger.info(f"[fetch_live_odds] Falling back to OpticOdds API due to database error")
        
        # If no market is specified and we have fixture_ids and sportsbooks, fetch available markets and choose one
        if not resolved_market and fixture_ids_list and resolved_sportsbook:
            try:
                # Use the first fixture_id and first sportsbook to get available markets
                # This gets markets that are actually available for this specific fixture and sportsbook combination
                first_fixture_id = fixture_ids_list[0]
                first_sportsbook = resolved_sportsbook[0] if isinstance(resolved_sportsbook, list) else resolved_sportsbook
                
                logger.info(f"[fetch_live_odds] No market specified, fetching available markets for fixture_id={first_fixture_id}, sportsbook={first_sportsbook}")
                markets_result = client.get_active_markets(
                    fixture_id=first_fixture_id,
                    sportsbook=first_sportsbook
                )
                markets_data = markets_result.get("data", [])
                
                if isinstance(markets_data, list) and len(markets_data) > 0:
                    # Prefer common markets in this order: Moneyline, Point Spread/Spread, Total Points/Total
                    # Always include Spread if available - it's a key market users want to see
                    preferred_markets = ["Moneyline", "Point Spread", "Spread", "Total Points", "Total", "Run Line", "Total Runs"]
                    
                    # Extract market names from the response
                    available_market_names = []
                    for market in markets_data:
                        market_name = market.get("name")
                        if market_name:
                            available_market_names.append(market_name)
                    
                    # Select multiple preferred markets (at least 2-3 common markets)
                    # Always prioritize including Spread/Point Spread if available
                    chosen_markets = []
                    
                    # First, ensure we get Spread if available (high priority)
                    spread_variants = ["Point Spread", "Spread"]
                    for spread_name in spread_variants:
                        if spread_name in available_market_names and spread_name not in chosen_markets:
                            chosen_markets.append(spread_name)
                            break  # Only add one spread variant
                    
                    # Then add other preferred markets
                    for preferred in preferred_markets:
                        if preferred in available_market_names and preferred not in chosen_markets:
                            chosen_markets.append(preferred)
                            # Select at least 2-3 markets for better coverage (including spread)
                            if len(chosen_markets) >= 3:
                                break
                    
                    # If we don't have enough preferred markets, add more from available
                    if len(chosen_markets) < 2:
                        for market_name in available_market_names:
                            if market_name not in chosen_markets:
                                chosen_markets.append(market_name)
                                if len(chosen_markets) >= 2:
                                    break
                    
                    if chosen_markets:
                        resolved_market = chosen_markets
                        logger.info(f"[fetch_live_odds] Selected {len(chosen_markets)} markets: {chosen_markets} from {len(available_market_names)} available markets")
                    else:
                        # Default to Moneyline if no markets found
                        resolved_market = ["Moneyline"]
                        logger.info(f"[fetch_live_odds] No markets found, defaulting to Moneyline")
                else:
                    # Default to Moneyline if no markets data
                    resolved_market = ["Moneyline"]
                    logger.info(f"[fetch_live_odds] No markets data in API response, defaulting to Moneyline")
            except Exception as market_error:
                # Default to Moneyline if market fetch fails
                resolved_market = ["Moneyline"]
                logger.warning(f"[fetch_live_odds] Error fetching available markets: {market_error}, defaulting to Moneyline")
        
        # Build API call parameters
        api_params = {
            "sportsbook": resolved_sportsbook,
        }
        
        # Add fixture_ids if available (up to 5)
        if fixture_ids_list:
            api_params["fixture_id"] = fixture_ids_list if len(fixture_ids_list) > 1 else fixture_ids_list[0]
        
        # Add optional parameters
        if resolved_market:
            api_params["market"] = resolved_market
        if player_id:
            api_params["player_id"] = str(player_id)
        if team_id:
            api_params["team_id"] = str(team_id)
        
        # Make API call
        result = client.get_fixture_odds(**api_params)
        
        # Debug: Log the raw response structure (remove in production)
        if not result:
            return "Error: No response from API"
        
        # Check if response has data
        response_data = result.get("data", [])
        if not response_data:
            # Return helpful error message with request details and response structure
            error_msg = f"No odds data returned from API.\n\n"
            error_msg += f"Request parameters sent:\n"
            error_msg += f"  - sportsbook: {resolved_sportsbook}\n"
            if fixture_ids_list:
                error_msg += f"  - fixture_id: {fixture_ids_list}\n"
            if resolved_market:
                error_msg += f"  - market: {resolved_market}\n"
            error_msg += f"\nAPI Response structure: {list(result.keys()) if isinstance(result, dict) else type(result)}\n"
            if isinstance(result, dict) and result.get("data") is not None:
                error_msg += f"Response 'data' type: {type(result.get('data'))}, length: {len(result.get('data')) if isinstance(result.get('data'), list) else 'N/A'}\n"
            error_msg += f"\nPossible reasons:\n"
            error_msg += f"- The fixture(s) may not have odds available yet\n"
            error_msg += f"- The sportsbook(s) may not have odds for this fixture (try lowercase: 'fanduel' not 'FanDuel')\n"
            error_msg += f"- The fixture_id(s) may be invalid\n"
            if fixture_ids_list:
                error_msg += f"\nTry calling fetch_available_sportsbooks(fixture_id='{fixture_ids_list[0]}') to see which sportsbooks have odds for this fixture."
            return error_msg
        
        # Automatically emit odds data to SSE stream (only if stream_output=True)
        if stream_output:
            session = session_id or "default"
            try:
                if result and result.get("data"):
                    odds_stream_manager.push_odds_sync(session, result)
            except Exception as emit_error:
                # Don't fail the whole request if emit fails
                pass
        
        # Get session_id early so it can be used for both odds storage and tool result storage
        session = session_id or _current_session_id.get() or "default"
        
        # Store odds entries in normalized database table for efficient querying (non-blocking)
        # This allows the agent to query/filter large odds datasets efficiently
        # Run in background thread so it doesn't block the agent
        try:
            import uuid
            temp_tool_call_id = f"odds_{uuid.uuid4().hex[:12]}"
            
            # Save odds for each fixture in background
            fixtures_data = result.get("data", [])
            if not isinstance(fixtures_data, list):
                fixtures_data = [fixtures_data] if fixtures_data else []
            
            for fixture_data in fixtures_data:
                if isinstance(fixture_data, dict):
                    fixture_id = fixture_data.get("id")
                    if fixture_id:
                        # Save in background thread - non-blocking
                        save_odds_async(
                            tool_call_id=temp_tool_call_id,
                            session_id=session,
                            fixture_id=fixture_id,
                            odds_data=fixture_data,
                        )
                        logger.debug(f"Queued odds save for fixture_id={fixture_id} in background thread")
        except Exception as odds_db_error:
            logger.warning(f"Failed to queue odds save to database: {odds_db_error}")
            # Don't fail the whole request if database save fails
        
        # Store full result in database for retrieval if LangGraph truncates it
        # We'll use a temporary key that can be matched when we see the tool_call_id
        
        # Create a temporary tool_call_id placeholder that will be replaced when we see the actual tool_call_id
        # We'll store it with a temporary ID that includes session and timestamp
        import time
        temp_tool_call_id = f"temp_{session}_{int(time.time() * 1000)}"
        
        # Return a formatted summary instead of full JSON
        # Create a concise summary of the odds data
        fixture_count = len(result.get("data", [])) if isinstance(result, dict) and "data" in result else len(result) if isinstance(result, list) else 0
        
        if fixture_count == 0:
            return "No odds data available for the specified criteria."
        
        # Create a summary message
        summary_parts = [f"Found odds for {fixture_count} fixture(s)."]
        
        # Add key information from the first fixture if available
        fixtures = result.get("data", result) if isinstance(result, dict) else result
        if fixtures and len(fixtures) > 0:
            first_fixture = fixtures[0] if isinstance(fixtures, list) else fixtures
            if isinstance(first_fixture, dict):
                home_team = first_fixture.get("home_competitors", [{}])[0].get("name", "Home") if first_fixture.get("home_competitors") else "Home"
                away_team = first_fixture.get("away_competitors", [{}])[0].get("name", "Away") if first_fixture.get("away_competitors") else "Away"
                summary_parts.append(f"Match: {away_team} vs {home_team}.")
        
        json_response = " ".join(summary_parts)
        
        try:
            # Store in database with temporary ID (will be updated when we get the real tool_call_id)
            # Pass raw API result as structured_data for efficient querying
            # Run in background thread so it doesn't block the agent
            save_tool_result_async(
                tool_call_id=temp_tool_call_id,
                session_id=session,
                tool_name="fetch_live_odds",
                full_result=json_response,
                structured_data=result  # Pass raw API response for structured querying
            )
            logger.debug(f"[fetch_live_odds] Queued tool result save in background thread with temp_id={temp_tool_call_id}, size={len(json_response)}")
            
            # Also store in in-memory cache as backup (this is fast, so keep it synchronous)
            store_tool_result(temp_tool_call_id, json_response)
        except Exception as store_error:
            logger.warning(f"[fetch_live_odds] Failed to queue tool result save: {store_error}")
        
        return json_response
    except Exception as e:
        return f"Error fetching live odds: {str(e)}"


@tool
def fetch_upcoming_games(
    league: Optional[str] = None,
    league_id: Optional[str] = None,
    fixture_id: Optional[str] = None,
    team_id: Optional[str] = None,
    start_date: Optional[str] = None,
    start_date_after: Optional[str] = None,
    start_date_before: Optional[str] = None,
    paginate: bool = True,
    stream_output: bool = True,
    session_id: Optional[str] = None,
) -> str:
    """🚨 RARELY NEEDED: Fetch upcoming game schedules/fixtures using OpticOdds /fixtures endpoint.
    
    ⚠️ CRITICAL: DO NOT call this tool if you've already called build_opticodds_url!
    Once build_opticodds_url returns a URL, your job is done - the frontend will fetch the data.
    Only call this tool if you need a specific fixture_id that's not available from query_tool_results.
    
    This tool should ONLY be used when you need to extract a specific fixture_id from the response.
    For simple requests like "show me NFL games", use build_opticodds_url with league="nfl" instead.
    
    IMPORTANT: Use as many filters as possible to narrow down results:
    - Always specify league when possible
    - Use date filters (start_date_after) to get only upcoming games
    - Use start_date_before for past games
    - Use team_id to filter by specific team
    - Use league_id for more precise filtering
    
    Args:
        league: League name (e.g., 'nba', 'nfl', 'mlb') - use if league_id not available
        league_id: League ID - preferred over league name for precision
        fixture_id: Optional specific fixture ID (if provided, other filters are ignored)
        team_id: Optional team ID to filter games for a specific team
        start_date: Specific date (ISO 8601 datetime format: YYYY-MM-DDTHH:MM:SSZ). Cannot be used with start_date_after/start_date_before
        start_date_after: Get fixtures after this datetime (ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ, e.g., '2024-10-21T00:00:00Z'). 
                         Defaults to current datetime in UTC if no date params provided.
        start_date_before: Get fixtures before this datetime (ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ, e.g., '2024-10-21T00:00:00Z'). 
                          Use this for past games.
        paginate: Whether to fetch all pages of results (default: True to get complete data)
        stream_output: Whether to emit fixture data to SSE stream. Set to False when calling as intermediate step.
                      Defaults to True. Only set to True for the final tool call that directly answers user's request.
        session_id: Optional session identifier (user_id or thread_id). If not provided, uses "default".
                    Frontend should connect to /api/v1/fixtures/fixtures/stream?session_id=<same_id> to receive data.
    
    Returns:
        Formatted string with upcoming game schedules including teams, dates, times, and fixture IDs.
        Fixture data is automatically emitted to SSE stream if stream_output=True.
    """
    try:
        # Check if this is for NFL - if so, use local endpoint instead of OpticOdds API
        is_nfl = False
        if league and str(league).lower() == "nfl":
            is_nfl = True
        elif league_id and (str(league_id).lower() == "nfl" or str(league_id) == "367"):
            is_nfl = True
        
        if is_nfl:
            # Use local NFL fixtures endpoint
            from app.core.database import SessionLocal
            from app.models.nfl_fixture import NFLFixture
            from sqlalchemy import or_
            from datetime import datetime as dt
            
            db = SessionLocal()
            try:
                # Build query
                query = db.query(NFLFixture)
                
                # Apply filters matching local endpoint parameters
                if fixture_id:
                    query = query.filter(NFLFixture.id == fixture_id)
                else:
                    # Date filters
                    if start_date_after:
                        try:
                            from_date = dt.fromisoformat(start_date_after.replace("Z", "+00:00"))
                            query = query.filter(NFLFixture.start_date >= from_date)
                        except ValueError:
                            pass
                    elif not start_date_after and not start_date_before:
                        # Default: Only get upcoming games
                        now_utc = datetime.now(ZoneInfo("UTC"))
                        query = query.filter(NFLFixture.start_date >= now_utc)
                    
                    if start_date_before:
                        try:
                            to_date = dt.fromisoformat(start_date_before.replace("Z", "+00:00"))
                            query = query.filter(NFLFixture.start_date <= to_date)
                        except ValueError:
                            pass
                    
                    # Note: team_id would need to be converted to team name - skip for now
                    # The local endpoint supports home_team/away_team but we don't have team_id mapping here
                
                # Order by start_date
                query = query.order_by(NFLFixture.start_date.asc())
                
                # Get fixtures
                fixtures = query.all()
                
                # Convert to OpticOdds API format
                fixture_data = []
                for fixture in fixtures:
                    fixture_dict = fixture.to_dict()
                    if fixture_dict:
                        fixture_data.append(fixture_dict)
                
                # Build result in OpticOdds format
                result = {
                    "data": fixture_data,
                    "page": 1,
                    "total_pages": 1
                }
            finally:
                db.close()
        else:
            # Use OpticOdds API for non-NFL leagues
            client = get_client()
            
            # Build parameters dict - use all available filters to narrow results
            params = {}
            
            # If fixture_id is provided, use only that (most specific filter)
            if fixture_id:
                params["fixture_id"] = str(fixture_id)
            else:
                # Use league_id if provided (more precise), otherwise fall back to league name
                if league_id:
                    params["league_id"] = str(league_id)
                elif league:
                    params["league"] = str(league)
                
                # Add team filter if provided
                if team_id:
                    params["team_id"] = str(team_id)
                
                # Handle date filters - use judiciously to narrow results
                # API rule: Cannot use start_date with start_date_after or start_date_before
                # API expects ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SSZ) for best results
                if start_date:
                    # Specific date - most precise filter (should be ISO 8601 format)
                    params["start_date"] = str(start_date)
                elif start_date_after or start_date_before:
                    # Date range filters (should be ISO 8601 format)
                    if start_date_after:
                        params["start_date_after"] = str(start_date_after)
                    if start_date_before:
                        params["start_date_before"] = str(start_date_before)
                else:
                    # Default: Only get upcoming games (from current datetime onwards)
                    # This prevents getting games from 3 days ago (API default)
                    # Format as ISO 8601 datetime in UTC (YYYY-MM-DDTHH:MM:SSZ)
                    now_utc = datetime.now(ZoneInfo("UTC"))
                    params["start_date_after"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Get fixtures from OpticOdds API with all filters applied
            result = client.get_fixtures(
                paginate=paginate,
                **params
            )
        
        # Format response
        formatted = format_fixtures_response(result)
        
        # Store full result in database for retrieval if LangGraph truncates it
        session = session_id or _current_session_id.get() or "default"
        
        # Create a temporary tool_call_id placeholder that will be replaced when we see the actual tool_call_id
        import time
        temp_tool_call_id = f"temp_{session}_{int(time.time() * 1000)}"
        
        try:
            # Store in database with temporary ID (will be updated when we get the real tool_call_id)
            # Pass raw API result as structured_data for efficient querying
            # Run in background thread so it doesn't block the agent
            save_tool_result_async(
                tool_call_id=temp_tool_call_id,
                session_id=session,
                tool_name="fetch_upcoming_games",
                full_result=formatted,
                structured_data=result  # Pass raw API response for structured querying
            )
            logger.debug(f"[fetch_upcoming_games] Queued tool result save in background thread with temp_id={temp_tool_call_id}, size={len(formatted)}")
            
            # Also store in in-memory cache as backup (this is fast, so keep it synchronous)
            store_tool_result(temp_tool_call_id, formatted)
        except Exception as store_error:
            logger.warning(f"[fetch_upcoming_games] Failed to queue tool result save: {store_error}")
        
        # Automatically extract and emit fixture objects to frontend
        # Extract fixtures from the formatted response (from <!-- FIXTURES_DATA_START --> block)
        try:
            # Extract JSON between FIXTURES_DATA_START and FIXTURES_DATA_END
            pattern = r'<!-- FIXTURES_DATA_START -->\s*(.*?)\s*<!-- FIXTURES_DATA_END -->'
            match = re.search(pattern, formatted, re.DOTALL)
            if match:
                fixtures_json_str = match.group(1).strip()
                fixtures_data = json.loads(fixtures_json_str)
                fixtures_list = fixtures_data.get('fixtures', [])
                
                if fixtures_list and stream_output:
                    # Automatically emit fixture objects to SSE stream (only if stream_output=True)
                    # Use provided session_id, context session_id, or fall back to "default"
                    effective_session_id = (
                        session_id 
                        or _current_session_id.get() 
                        or "default"
                    )
                    
                    # Save fixtures to database (non-blocking)
                    try:
                        save_fixtures_async(effective_session_id, fixtures_list)
                        logger.debug(f"[fetch_upcoming_games] Queued save of {len(fixtures_list)} fixtures to database in background thread for session_id: {effective_session_id}")
                    except Exception as db_error:
                        logger.error(f"[fetch_upcoming_games] Error queueing fixtures save to database: {db_error}", exc_info=True)
                    
                    # Push notification to SSE stream (instructs frontend to fetch from API)
                    print(f"[DEBUG fetch_upcoming_games] Sending notification for {len(fixtures_list)} fixtures to stream with session_id: {effective_session_id}")
                    logger.info(f"[fetch_upcoming_games] Sending notification for {len(fixtures_list)} fixtures to stream with session_id: {effective_session_id}")
                    result = fixture_stream_manager.push_fixtures_sync(effective_session_id, fixtures_list)
                    print(f"[DEBUG fetch_upcoming_games] Notification sent result: {result}")
                    logger.info(f"[fetch_upcoming_games] Notification sent result: {result}")
                elif not fixtures_list:
                    logger.warning(f"[fetch_upcoming_games] No fixtures found in extracted data")
                elif not stream_output:
                    logger.info(f"[fetch_upcoming_games] stream_output=False, skipping push")
            else:
                logger.warning(f"[fetch_upcoming_games] No FIXTURES_DATA markers found in formatted response")
        except Exception as emit_error:
            # Don't fail the whole request if emit fails, but log the error for debugging
            logger.error(f"[fetch_upcoming_games] Error emitting fixtures to stream: {emit_error}", exc_info=True)
        
        return formatted
    except Exception as e:
        return f"Error fetching upcoming games: {str(e)}"




@tool
def fetch_player_props(
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,
    player_id: Optional[str] = None,
    league_id: Optional[str] = None,
) -> str:
    """Fetch player proposition odds using database (for NFL) or OpticOdds API (for other leagues).
    
    Args:
        fixture_id: Specific fixture ID (string ID)
        fixture: Full fixture object as JSON string (alternative to fixture_id).
                 If provided, fixture_id will be extracted from it.
        player_id: Specific player ID
        league_id: Filter by league ID. Can also be extracted from fixture object if provided.
    
    Returns:
        Formatted string with player prop odds from multiple sportsbooks
    """
    try:
        # Extract fixture_id from fixture object if provided
        resolved_fixture_id = None
        resolved_league_id = league_id
        
        if fixture:
            fixture_obj = json.loads(fixture) if isinstance(fixture, str) else fixture
            if isinstance(fixture_obj, dict):
                # Extract fixture_id
                resolved_fixture_id = extract_fixture_id(fixture if isinstance(fixture, str) else json.dumps(fixture_obj))
                # Extract league_id if not provided
                if not resolved_league_id:
                    league_info = fixture_obj.get("league") or fixture_obj.get("full_fixture", {}).get("league", {})
                    if isinstance(league_info, dict):
                        resolved_league_id = league_info.get("id") or league_info.get("numerical_id")
        
        # Use provided fixture_id if fixture object not provided
        if not resolved_fixture_id:
            resolved_fixture_id = extract_fixture_id(fixture_id)
        
        # Check if this is for NFL - if so, use database
        is_nfl = False
        if resolved_fixture_id:
            try:
                from app.core.database import SessionLocal
                from app.models.nfl_fixture import NFLFixture
                db = SessionLocal()
                try:
                    nfl_fixture = db.query(NFLFixture).filter(NFLFixture.id == resolved_fixture_id).first()
                    if nfl_fixture:
                        is_nfl = True
                        logger.info(f"[fetch_player_props] Detected NFL fixture, using database")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"[fetch_player_props] Error checking if NFL: {e}, falling back to API")
        
        # For NFL, use database query
        if is_nfl and resolved_fixture_id:
            try:
                from app.core.odds_db_query import query_odds_from_db
                
                # Query database for player props
                result = query_odds_from_db(
                    fixture_id=[resolved_fixture_id],
                    market_category="player_prop",
                    player_id=str(player_id) if player_id else None,
                    limit=1000,
                )
                
                # Format response similar to OpticOdds API format
                response_data = result.get("data", [])
                if not response_data:
                    return f"No player prop odds found in database for fixture {resolved_fixture_id}."
                
                # Format player props from database result
                formatted_lines = []
                formatted_lines.append("\nPlayer Prop Odds from Database:")
                
                for fixture_data in response_data:
                    odds_list = fixture_data.get("odds", [])
                    if not odds_list:
                        continue
                    
                    # Group by player
                    players_dict = {}
                    for odds_entry in odds_list:
                        player_id = odds_entry.get("player_id")
                        if not player_id:
                            continue
                        
                        if player_id not in players_dict:
                            players_dict[player_id] = {
                                "player_name": odds_entry.get("selection", "Unknown"),
                                "props": []
                            }
                        
                        players_dict[player_id]["props"].append({
                            "market": odds_entry.get("market", ""),
                            "name": odds_entry.get("name", ""),
                            "sportsbook": odds_entry.get("sportsbook", ""),
                            "price": odds_entry.get("price"),
                            "points": odds_entry.get("points"),
                            "selection_line": odds_entry.get("selection_line"),
                        })
                    
                    # Format output
                    for player_id, player_data in players_dict.items():
                        formatted_lines.append(f"\n{player_data['player_name']}:")
                        for prop in player_data["props"]:
                            price_str = f"{prop['price']:+d}" if prop.get("price") else "N/A"
                            line_str = f" ({prop['selection_line']})" if prop.get("selection_line") else ""
                            formatted_lines.append(f"• {prop['market']} - {prop['name']}{line_str}: {price_str} ({prop['sportsbook']})")
                
                return "\n".join(formatted_lines) if formatted_lines else "No player prop odds found in database."
            except Exception as db_error:
                logger.error(f"[fetch_player_props] Error querying database: {db_error}", exc_info=True)
                # Fall through to API call
        
        # For non-NFL or if database query failed, use API
        client = get_client()
        
        # Get player results/markets
        params = {}
        if resolved_fixture_id:
            try:
                params["fixture_id"] = int(resolved_fixture_id)
            except (ValueError, TypeError):
                pass
        if player_id:
            params["player_id"] = int(player_id)
        
        player_results = client.get_player_results(**params)
        
        # Also get odds for player markets
        odds = client.get_fixture_odds(
            fixture_id=resolved_fixture_id if resolved_fixture_id else None,
            league=resolved_league_id if resolved_league_id else None,
            market_types="player_props",
        )
        
        # Format response
        formatted = format_player_props_response(player_results, odds)
        return formatted
    except Exception as e:
        return f"Error fetching player props: {str(e)}"


@tool
def fetch_live_game_stats(
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,
    player_id: Optional[str] = None,
) -> str:
    """Fetch live in-game statistics using OpticOdds /fixtures/results and /fixtures/player-results.
    
    Args:
        fixture_id: Fixture ID for the game (string ID)
        fixture: Full fixture object as JSON string (alternative to fixture_id).
                 If provided, fixture_id will be extracted from it.
        player_id: Optional player ID for specific player stats
    
    Returns:
        Formatted string with live game statistics
    """
    try:
        client = get_client()
        
        # Extract fixture_id from fixture object if provided
        resolved_fixture_id = None
        
        if fixture:
            resolved_fixture_id = extract_fixture_id(fixture)
        
        # Use provided fixture_id if fixture object not provided
        if not resolved_fixture_id:
            resolved_fixture_id = extract_fixture_id(fixture_id)
        
        if not resolved_fixture_id:
            return "Error: fixture_id or fixture object is required"
        
        # Get fixture results
        try:
            results = client.get_fixture_results(fixture_id=int(resolved_fixture_id))
        except (ValueError, TypeError):
            return f"Error: Invalid fixture_id: {resolved_fixture_id}"
        
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
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,
    market_id: str = None,
    selection_id: str = None,
) -> str:
    """Generate deep links to sportsbook bet pages with pre-filled bet slips using OpticOdds data.
    
    Args:
        sportsbook: Sportsbook name (e.g., 'fanduel', 'draftkings', 'betmgm')
        fixture_id: Fixture ID from OpticOdds (string ID)
        fixture: Full fixture object as JSON string (alternative to fixture_id).
                 If provided, fixture_id will be extracted from it.
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
    legs: Optional[str] = None,
    fixtures: Optional[str] = None,
) -> str:
    """Calculate parlay odds for multiple bet legs using OpticOdds /parlay/odds endpoint.
    
    This tool can accept either pre-formatted legs or full fixture objects. If fixtures are provided,
    you'll need to specify market_id, selection_id, and optionally sportsbook_id for each fixture.
    
    Args:
        legs: JSON string of parlay legs. Each leg should be a dict with:
            - fixture_id: Fixture ID (string or extracted from full fixture object)
            - market_id: Market ID
            - selection_id: Selection ID
            - sportsbook_id: Sportsbook ID (optional)
        
            Legs can contain full fixture objects - fixture_id will be automatically extracted.
        
        fixtures: JSON string containing one or more full fixture objects (alternative to legs).
                  If provided, you must also provide market_ids, selection_ids, and optionally
                  sportsbook_ids as separate arrays or in the fixture objects.
    
    Example legs format with fixture_id strings:
        '[{"fixture_id": "123", "market_id": 456, "selection_id": 789}, {"fixture_id": "124", "market_id": 457, "selection_id": 790}]'
    
    Example legs format with full fixture objects:
        '[{"fixture": {"id": "123", ...full object...}, "market_id": 456, "selection_id": 789}]'
    
    Example fixtures format:
        '[{"id": "123", "home_team_display": "Team A", ...}, {"id": "124", "home_team_display": "Team B", ...}]'
    
    Returns:
        Formatted string with parlay odds from multiple sportsbooks
    """
    try:
        client = get_client()
        
        legs_list = []
        
        # If fixtures provided, extract fixture_ids
        if fixtures:
            try:
                fixtures_data = json.loads(fixtures) if isinstance(fixtures, str) else fixtures
                
                # Handle array of fixtures
                if isinstance(fixtures_data, list):
                    for fixture_obj in fixtures_data:
                        fixture_id = extract_fixture_id(json.dumps(fixture_obj) if isinstance(fixture_obj, dict) else str(fixture_obj))
                        if fixture_id:
                            # Create a leg with just fixture_id - user needs to provide market/selection IDs
                            legs_list.append({"fixture_id": fixture_id})
                # Handle single fixture
                elif isinstance(fixtures_data, dict):
                    fixture_id = extract_fixture_id(json.dumps(fixtures_data))
                    if fixture_id:
                        legs_list.append({"fixture_id": fixture_id})
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                return f"Error parsing fixtures: {str(e)}. Please provide valid JSON."
        
        # If legs provided, parse and extract fixture_ids from any full fixture objects
        if legs:
            try:
                legs_data = json.loads(legs) if isinstance(legs, str) else legs
                
                if not isinstance(legs_data, list):
                    return "Error: legs must be a list of bet legs"
                
                # Process each leg - extract fixture_id if it's a full fixture object
                for leg in legs_data:
                    if not isinstance(leg, dict):
                        return f"Error: Each leg must be a dict, got {type(leg)}"
                    
                    processed_leg = leg.copy()
                    
                    # If leg has a 'fixture' key with a full object, extract fixture_id
                    if "fixture" in leg:
                        fixture_id = extract_fixture_id(
                            json.dumps(leg["fixture"]) if isinstance(leg["fixture"], dict) else str(leg["fixture"])
                        )
                        if fixture_id:
                            processed_leg["fixture_id"] = fixture_id
                            # Remove the fixture object to keep leg clean
                            processed_leg.pop("fixture", None)
                    
                    # If fixture_id is a full object, extract the ID
                    if "fixture_id" in processed_leg and isinstance(processed_leg["fixture_id"], (dict, str)):
                        extracted_id = extract_fixture_id(
                            json.dumps(processed_leg["fixture_id"]) if isinstance(processed_leg["fixture_id"], dict) else str(processed_leg["fixture_id"])
                        )
                        if extracted_id:
                            processed_leg["fixture_id"] = extracted_id
                    
                    legs_list.append(processed_leg)
                    
            except json.JSONDecodeError as e:
                return f"Error parsing legs JSON: {str(e)}"
        
        if len(legs_list) == 0:
            return "Error: Must provide either 'legs' or 'fixtures' parameter with at least one fixture"
        
        # Validate legs have required fields
        for i, leg in enumerate(legs_list):
            if "fixture_id" not in leg:
                return f"Error: Leg {i+1} is missing fixture_id"
            if "market_id" not in leg:
                return f"Error: Leg {i+1} is missing market_id"
            if "selection_id" not in leg:
                return f"Error: Leg {i+1} is missing selection_id"
        
        # Calculate parlay odds
        result = client.calculate_parlay_odds(legs=legs_list)
        
        # Format response for frontend
        formatted = format_parlay_response(result, legs_list)
        return formatted
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


@tool
def fetch_available_sports() -> str:
    """Fetch available sports that currently have fixtures with odds using OpticOdds /sports/active endpoint.
    
    This tool returns sports that are currently active and have fixtures with odds available.
    Use this to discover valid sport IDs and names for use in other endpoints.
    
    Returns:
        Formatted string with sports information including IDs, names, and other details
    """
    try:
        client = get_client()
        result = client.get_active_sports()
        formatted = format_sports_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching available sports: {str(e)}"


@tool
def fetch_available_leagues(sport: Optional[str] = None) -> str:
    """Fetch available leagues that currently have fixtures with odds using OpticOdds /leagues/active endpoint.
    
    This tool returns leagues that are currently active and have fixtures with odds available.
    Use this to discover valid league IDs and names for use in other endpoints.
    
    Args:
        sport: Optional sport name or ID to filter leagues. If provided, returns all leagues for that sport.
              If not provided, returns only active leagues with fixtures and odds.
    
    Returns:
        Formatted string with leagues information including IDs, names, and associated sport info
    """
    try:
        client = get_client()
        if sport:
            # Get all leagues for the sport (not just active)
            result = client.get_leagues(sport=sport)
        else:
            # Get only active leagues with fixtures and odds
            result = client.get_active_leagues()
        formatted = format_leagues_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching available leagues: {str(e)}"


@tool
def fetch_available_markets(
    fixture_id: Optional[str] = None,
    sportsbook: Optional[str] = None,
) -> str:
    """🚨 IMPORTANT: Fetch available MARKET NAMES (not market types) using OpticOdds /markets/active endpoint.
    
    ⚠️ CRITICAL: This tool returns actual MARKET NAMES that can be used directly in fetch_live_odds.
    These are NOT market type names - they are the exact market names the API expects.
    
    🔑 USE THIS BEFORE REQUESTING ODDS: When you need to request odds for specific markets,
    call this tool FIRST with the fixture_id and sportsbook to get the correct market names,
    then use those exact market names in fetch_live_odds.
    
    Example workflow:
    1. Call fetch_available_markets(fixture_id="123", sportsbook="draftkings")
    2. Get market names like "Player Points", "Player Receptions", "Moneyline"
    3. Use those EXACT names in fetch_live_odds(market="Player Points,Player Receptions")
    
    ⚠️ DO NOT use market type names (like "player_total", "player_yes_no") - those are NOT valid market names.
    Use the actual market names returned by this tool.
    
    When fixture_id and sportsbook are provided, returns markets available for that specific 
    fixture and sportsbook combination. This ensures you get market names that are actually
    available for that game and sportsbook.
    
    Args:
        fixture_id: Optional fixture ID to filter markets available for this specific fixture.
                   RECOMMENDED: Always provide this to get markets for the specific game.
        sportsbook: Optional sportsbook name or ID to filter markets available for this sportsbook.
                   RECOMMENDED: Provide this to get markets available for the specific sportsbook.
                   Can be comma-separated list (e.g., "draftkings,fanduel") or single sportsbook.
    
    Returns:
        Formatted string with market information including:
        - market_name: The EXACT market name to use in fetch_live_odds (e.g., "Player Points", "Moneyline")
        - market_type: The underlying market type (for reference only, do NOT use this in API calls)
        - market_id: Market ID (for reference)
        - market_slug: Market slug (for reference)
    
    IMPORTANT: Use the "market_name" field when calling fetch_live_odds. Do NOT use market_type.
    """
    try:
        client = get_client()
        
        # Handle sportsbook parameter - can be comma-separated string or single value
        resolved_sportsbook = None
        if sportsbook:
            if isinstance(sportsbook, str) and ',' in sportsbook:
                # Multiple sportsbooks - pass as list
                resolved_sportsbook = [sb.strip().lower() for sb in sportsbook.split(',') if sb.strip()][:5]
            elif isinstance(sportsbook, str):
                resolved_sportsbook = sportsbook.strip().lower()
        
        result = client.get_active_markets(
            fixture_id=fixture_id if fixture_id else None,
            sportsbook=resolved_sportsbook
        )
        formatted = format_markets_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching available markets: {str(e)}"


@tool
def fetch_market_types() -> str:
    """Get all available market type definitions (embedded in codebase for fast access).
    
    This tool returns all market type definitions with their IDs, names, selection templates, and notes.
    Use this to understand which market types are available and how to use them.
    
    Market types define the structure of betting markets (e.g., "moneyline", "spread", "player_total").
    Each market type has:
    - id: Numeric ID for the market type
    - name: The market type name (use this in API requests)
    - selections: Template strings showing how selections are formatted
    - notes: Additional information about the market type
    
    IMPORTANT: When requesting odds, use the market type "name" (e.g., "moneyline", "spread", "player_total").
    Do NOT use display names like "Moneyline" or "Player Props" - use the exact market type name.
    
    Player prop market types include:
    - player_only: Player-specific markets
    - player_total: Player over/under totals
    - player_total_combo: Combined player totals
    - player_yes_no: Player yes/no markets
    - player_h2h_ml: Player head-to-head moneyline
    - player_h2h_spread: Player head-to-head spread
    - player_golf_hole_score_qualifier: Golf-specific player markets
    
    Returns:
        Formatted string with all market type definitions including IDs, names, selections, and notes
    """
    try:
        from app.core.market_types import MARKET_TYPES
        # Use embedded market types data for instant access (no API call needed)
        formatted = format_market_types_response(MARKET_TYPES)
        return formatted
    except Exception as e:
        return f"Error fetching market types: {str(e)}"


@tool
def fetch_available_sportsbooks(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    fixture_id: Optional[str] = None,
) -> str:
    """Fetch available sportsbooks using OpticOdds /sportsbooks/active endpoint.
    
    This tool returns sportsbooks that are currently active and have odds available.
    Use this BEFORE calling fetch_live_odds to verify which sportsbooks are available.
    Also use when user asks about specific sportsbooks or when you need to confirm a sportsbook exists.
    
    IMPORTANT: Use filters to narrow down results:
    - Use sport to filter by sport (e.g., 'basketball')
    - Use league to filter by league (e.g., 'nba')
    - Use fixture_id to see which sportsbooks have odds for a specific game
    
    Args:
        sport: Optional sport name or ID to filter sportsbooks by sport (e.g., 'basketball')
        league: Optional league name or ID to filter sportsbooks by league (e.g., 'nba')
        fixture_id: Optional fixture ID to filter sportsbooks that have odds for this specific fixture
    
    Returns:
        Formatted string with sportsbooks information including IDs, names, and active status
    """
    try:
        client = get_client()
        result = client.get_active_sportsbooks(
            sport=sport if sport else None,
            league=league if league else None,
            fixture_id=fixture_id if fixture_id else None,
        )
        formatted = format_sportsbooks_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching available sportsbooks: {str(e)}"


@tool
def fetch_players(
    league: Optional[str] = None,
    team_id: Optional[str] = None,
    player_id: Optional[str] = None,
    player_name: Optional[str] = None,
    include_statsperform_id: bool = False,
    paginate: bool = True,
) -> str:
    """🚨 MANDATORY: Fetch player details and get player_id using OpticOdds /players endpoint.
    
    ⚡ FAST DATABASE LOOKUP FOR NFL: For NFL players, this tool uses a fast database lookup first 
    (hashmap-like performance), then falls back to the API if needed. This provides instant access 
    to all NFL players without API calls.
    
    ⚠️ CRITICAL WORKFLOW FOR PLAYER-SPECIFIC REQUESTS:
    When user requests odds for a specific player (e.g., "show me odds for Jameson Williams"):
    1. FIRST: Call this tool to get the player_id
       Example: fetch_players(league="nfl", player_name="Jameson Williams")
    2. Extract the player_id from the response
    3. THEN: Call build_opticodds_url with player_id included
       Example: build_opticodds_url(..., player_id=player_id, fixture_id=...)
    4. FINALLY: Call fetch_live_odds with player_id included
       Example: fetch_live_odds(..., player_id=player_id, fixture_id=...)
    
    The player_id MUST be included in the URL so the frontend can filter odds for that specific player.
    Do NOT skip this step - always get player_id first, then use it in build_opticodds_url and fetch_live_odds.
    
    CRITICAL: Player IDs are unique per league. The same player can have different IDs 
    across different leagues. For example, Lionel Messi has:
    - C7231134C08F for USA - Major League Soccer
    - 7D915F8BDA8E for CONMEBOL - Copa America
    
    IMPORTANT: When using player_id in fetch_live_odds or fetch_player_props, you MUST 
    use the player_id that matches the league you're querying. Always pass the league 
    parameter to get the correct league-specific player ID.
    
    Use this tool when:
    - User asks about a specific player (e.g., "show me odds for Jameson Williams")
    - User asks for player props but you don't have the player_id yet
    - You need to find a player's ID for a specific league
    - You need to verify a player exists in a league before fetching odds
    
    TIP: For NFL, you can use fetch_teams(league="nfl", team_name="...") first to get team_id instantly,
    then use that team_id here to filter players by team. This triggers the fast database lookup 
    and makes the search much faster and more accurate. The tool automatically uses the database 
    for NFL lookups when team_id is provided.
    
    Args:
        league: REQUIRED (unless player_id is provided). League name or ID (e.g., 'nfl', 'nba', 'nhl').
                This ensures you get the correct league-specific player ID.
        team_id: Optional. Team ID to filter players by team. For NFL, get this instantly from fetch_teams(league="nfl", team_name="...").
                 Using team_id significantly speeds up player searches and makes them more accurate.
        player_id: Optional. Specific player ID. If provided, returns data for that player 
                  (including inactive players). Use this to get details for a known player ID.
        player_name: REQUIRED when user requests a specific player. Player name to search for. 
                     The tool will filter results to match this name (case-insensitive partial match). 
                     Note: API doesn't support name filtering directly, so results are filtered client-side.
                     TIP: For NFL, combine with team_id from fetch_teams for faster, more accurate results.
        include_statsperform_id: If True, includes StatsPerform IDs in response. Default: False.
        paginate: If True, fetches all pages of results. Default: True.
    
    Returns:
        Formatted string with player information including:
        - Player ID (league-specific - CRITICAL: Extract this and use in fetch_live_odds with player_id parameter)
        - Player name
        - Team information
        - League information
        - Other player details
    
    Example workflow for "show me odds for Jameson Williams":
        OPTION 1 (Recommended for NFL - faster with team filter):
        1. fetch_teams(league="nfl", team_name="Detroit Lions")  # Instant - uses embedded data
           → Returns: team_id="43412DC9CDCA"
        2. fetch_players(league="nfl", player_name="Jameson Williams", team_id="43412DC9CDCA")
           → Returns: player_id="ABC123..." (faster search with team filter)
        3. build_opticodds_url(tool_name="fetch_live_odds", player_id="ABC123", fixture_id="...", sportsbook="...")
           → Returns: URL with player_id included
        4. fetch_live_odds(player_id="ABC123", fixture_id="...", sportsbook="...")
           → Returns: Odds filtered for that player
        
        OPTION 2 (If team is unknown):
        1. fetch_players(league="nfl", player_name="Jameson Williams")
           → Returns: player_id="ABC123..."
        2. build_opticodds_url(tool_name="fetch_live_odds", player_id="ABC123", fixture_id="...", sportsbook="...")
           → Returns: URL with player_id included
        3. fetch_live_odds(player_id="ABC123", fixture_id="...", sportsbook="...")
           → Returns: Odds filtered for that player
    """
    try:
        # For NFL, try database first for fast lookups (hashmap-like performance)
        league_lower = league.lower() if league else ""
        if league_lower == "nfl":
            try:
                from app.core.nfl_players_db import (
                    get_players_by_team,
                    get_player_by_id,
                    get_player_by_name as db_get_player_by_name,
                )
                
                db_players = []
                use_db = False
                
                # Try database lookup based on provided parameters
                if player_id:
                    # Lookup by player_id
                    player = get_player_by_id(player_id)
                    if player:
                        db_players = [player]
                        use_db = True
                        logger.info(f"[fetch_players] Using database lookup for NFL player_id={player_id}")
                
                elif team_id:
                    # Lookup by team_id (fast hashmap-like lookup)
                    if player_name:
                        # Team + name search
                        db_players = db_get_player_by_name(player_name, team_id=team_id, active_only=True)
                        use_db = True
                        logger.info(f"[fetch_players] Using database lookup for NFL team_id={team_id}, player_name={player_name}")
                    else:
                        # All players for team
                        db_players = get_players_by_team(team_id, active_only=True)
                        use_db = True
                        logger.info(f"[fetch_players] Using database lookup for NFL team_id={team_id}")
                
                elif player_name:
                    # Name search without team filter
                    db_players = db_get_player_by_name(player_name, team_id=None, active_only=True)
                    use_db = True
                    logger.info(f"[fetch_players] Using database lookup for NFL player_name={player_name}")
                
                # If we found players in database, convert to API format and return
                if use_db and db_players:
                    # Convert NFLPlayer objects to API response format
                    api_format_players = []
                    for db_player in db_players:
                        player_dict = {
                            "id": db_player.id,
                            "name": db_player.name,
                            "first_name": db_player.first_name,
                            "last_name": db_player.last_name,
                            "position": db_player.position,
                            "number": db_player.number,
                            "age": db_player.age,
                            "height": db_player.height,
                            "weight": db_player.weight,
                            "experience": db_player.experience,
                            "is_active": db_player.is_active,
                            "numerical_id": db_player.numerical_id,
                            "base_id": db_player.base_id,
                            "logo": db_player.logo,
                            "source_ids": db_player.source_ids if db_player.source_ids else {},
                            "team": {
                                "id": db_player.team_id,
                                "name": db_player.team_name or "Unknown",
                            },
                            "league": {
                                "id": "nfl",
                                "name": "NFL",
                                "numerical_id": 367,
                            },
                            "sport": {
                                "id": "football",
                                "name": "Football",
                                "numerical_id": 9,
                            },
                        }
                        api_format_players.append(player_dict)
                    
                    result = {
                        "data": api_format_players,
                        "page": 1,
                        "total_pages": 1,
                    }
                    
                    formatted = format_players_response(result, player_name=player_name, league=league)
                    return formatted
                
                # If database lookup returned no results, return empty result (don't fall back to API for NFL)
                if use_db and not db_players:
                    logger.info(f"[fetch_players] Database lookup returned no results for NFL player_name={player_name}")
                    # Return empty result instead of falling back to API for NFL
                    result = {
                        "data": [],
                        "page": 1,
                        "total_pages": 1,
                    }
                    formatted = format_players_response(result, player_name=player_name, league=league)
                    return formatted
            
            except Exception as db_error:
                # Check if error is due to missing table
                error_str = str(db_error).lower()
                if "no such table" in error_str or "does not exist" in error_str:
                    # Table doesn't exist - fall back to API for this request
                    # But log warning that database should be set up
                    logger.warning(f"[fetch_players] NFL players table doesn't exist, falling back to API. Please run fetch_nfl_players script to populate database.")
                else:
                    # Other database error - log and fall back to API
                    logger.warning(f"[fetch_players] Database lookup failed for NFL: {db_error}, falling back to API")
                
                # Fall through to API call below
        
        # For non-NFL leagues, use API
        client = get_client()
        
        # Validate: must provide at least one of league, player_id, or sport
        if not league and not player_id:
            return "Error: Must provide at least one of: league (recommended) or player_id. League is required to get accurate league-specific player IDs."
        
        # Build params
        params = {}
        if league:
            params["league"] = league
        if player_id:
            params["id"] = player_id
        if include_statsperform_id:
            params["include_statsperform_id"] = "true"
        
        # Note: OpticOdds API /players endpoint doesn't support team_id parameter directly
        # We'll filter by team_id client-side after fetching if provided
        
        # Fetch players from API
        logger.info(f"[fetch_players] Using API lookup for league={league}")
        result = client.get_players(paginate=paginate, **params)
        
        # Filter by team_id if provided (client-side filtering)
        if team_id and result and result.get("data"):
            players_list = result.get("data", [])
            if isinstance(players_list, list):
                filtered_players = []
                for player in players_list:
                    if isinstance(player, dict):
                        # Check if player's team matches team_id
                        team_info = player.get("team", {})
                        if isinstance(team_info, dict):
                            if team_info.get("id") == team_id:
                                filtered_players.append(player)
                        # Also check direct team_id field if present
                        elif player.get("team_id") == team_id:
                            filtered_players.append(player)
                result["data"] = filtered_players
        
        # Format response
        formatted = format_players_response(result, player_name=player_name, league=league)
        return formatted
        
    except Exception as e:
        logger.error(f"Error fetching players: {e}")
        return f"Error fetching players: {str(e)}"


@tool
def fetch_teams(
    league: Optional[str] = None,
    team_id: Optional[str] = None,
    team_name: Optional[str] = None,
    sport: Optional[str] = None,
    division: Optional[str] = None,
    conference: Optional[str] = None,
    include_statsperform_id: bool = False,
    paginate: bool = True,
) -> str:
    """Fetch team details using OpticOdds /teams endpoint.
    
    ⚡ FAST ACCESS FOR NFL: For NFL teams, this tool uses embedded data (no API call needed).
    This provides instant access to all 32 NFL teams with their IDs, names, abbreviations, etc.
    
    CRITICAL: Team IDs are unique per league. The same team can have different IDs 
    across different leagues. For example, Manchester City FC has:
    - 578E2130DC1B for UEFA - Champions League
    - E69E55FFCF65 for England - Premier League
    
    IMPORTANT: When using team_id in fetch_live_odds or fetch_players, you MUST 
    use the team_id that matches the league you're querying. Always pass the league 
    parameter to get the correct league-specific team ID.
    
    This tool is useful for:
    - Finding team IDs when you only know the team name (especially for NFL - instant access)
    - Getting team information (abbreviation, division, conference, etc.)
    - Filtering teams by division or conference
    - Verifying team names before making other API calls
    - Getting team_id to filter players by team (fetch_players with team_id parameter)
    
    Note: For NFL, this tool uses embedded data for instant access. For other leagues, 
    the API doesn't support direct name filtering, so this tool fetches all teams 
    for the league and filters client-side.
    
    Use this tool when:
    - User asks about a specific team (e.g., "show me Dallas Cowboys", "find Lions")
    - You need to find a team's ID for a specific league (especially NFL)
    - User asks for team odds but you don't have the team_id yet
    - You need to verify a team exists in a league before fetching odds
    - You want to filter teams by division or conference (NFL, NBA, etc.)
    - You need team_id to filter players by team (e.g., fetch_players(league="nfl", team_id=...))
    
    Args:
        league: REQUIRED (unless team_id is provided). League name or ID (e.g., 'nfl', 'nba', 'nhl').
                This ensures you get the correct league-specific team ID.
                For NFL, uses embedded data for instant access.
        team_id: Optional. Specific team ID. If provided, returns data for that team 
                (including inactive teams). Use this to get details for a known team ID.
        team_name: Optional. Team name to search for. The tool will filter results to match 
                   this name (case-insensitive partial match). 
                   For NFL: Supports full name, city, mascot, or abbreviation (e.g., "Lions", "Detroit", "DET").
                   For other leagues: API doesn't support name filtering directly, so results are filtered client-side.
        sport: Optional. Sport name or ID (e.g., 'football', 'basketball'). Usually not needed 
               if league is provided.
        division: Optional. Division name to filter by (e.g., 'West', 'East' for NBA; 'North', 'South' for NFL).
        conference: Optional. Conference name to filter by (e.g., 'NFC', 'AFC' for NFL; 'Eastern', 'Western' for NBA).
        include_statsperform_id: If True, includes StatsPerform IDs in response. Default: False.
        paginate: If True, fetches all pages of results. Default: True.
    
    Returns:
        Formatted string with team information including:
        - Team ID (league-specific - CRITICAL for use in fetch_live_odds and fetch_players)
        - Team name, abbreviation, city, mascot
        - Division and conference (if available)
        - base_id (for cross-league linking)
        - League and sport information
        - Logo URL
    
    Example for NFL (uses embedded data - instant):
        fetch_teams(league="nfl", team_name="Detroit Lions")
        # Returns: team_id="43412DC9CDCA" (instant, no API call)
    
    Example for other leagues (uses API):
        fetch_teams(league="nba", team_name="Lakers")
        # Returns: team with NBA-specific ID
    """
    try:
        # For NFL, use embedded data for fast access (no API call needed)
        league_lower = league.lower() if league else ""
        if league_lower == "nfl":
            from app.core.nfl_teams import (
                get_nfl_teams,
                get_team_by_name,
                get_team_by_id,
                get_team_by_abbreviation,
                get_teams_by_division,
                get_teams_by_conference
            )
            
            # Get all NFL teams
            nfl_teams_data = get_nfl_teams()
            teams_list = nfl_teams_data.get("data", [])
            
            # Filter by team_id if provided
            if team_id:
                team = get_team_by_id(team_id)
                if team:
                    teams_list = [team]
                else:
                    teams_list = []
            
            # Filter by team_name if provided
            elif team_name:
                team = get_team_by_name(team_name)
                if team:
                    teams_list = [team]
                else:
                    # Try abbreviation
                    team = get_team_by_abbreviation(team_name)
                    if team:
                        teams_list = [team]
                    else:
                        teams_list = []
            
            # Filter by division if provided
            elif division:
                teams_list = get_teams_by_division(division)
            
            # Filter by conference if provided
            elif conference:
                teams_list = get_teams_by_conference(conference)
            
            # Create result structure matching API format
            result = {
                "data": teams_list,
                "page": 1,
                "total_pages": 1
            }
            
            # Format response
            formatted = format_teams_response(result, team_name=team_name, league=league)
            return formatted
        
        # For other leagues, use API
        client = get_client()
        
        # Validate: must provide at least one of league, team_id, or sport
        if not league and not team_id and not sport:
            return "Error: Must provide at least one of: league (recommended), team_id, or sport. League is required to get accurate league-specific team IDs."
        
        # Build params
        params = {}
        if league:
            params["league"] = league
        if team_id:
            params["id"] = team_id
        if sport:
            params["sport"] = sport
        if division:
            params["division"] = division
        if conference:
            params["conference"] = conference
        if include_statsperform_id:
            params["include_statsperform_id"] = include_statsperform_id
        
        # Fetch teams
        result = client.get_teams(paginate=paginate, **params)
        
        # Format response
        formatted = format_teams_response(result, team_name=team_name, league=league)
        return formatted
        
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        return f"Error fetching teams: {str(e)}"


@tool
def query_odds_entries(
    fixture_id: str,
    session_id: Optional[str] = None,
    sportsbook: Optional[str] = None,
    market: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    main_markets_only: bool = False,
) -> str:
    """Query odds entries from the database with filters. Use this for large odds datasets that can't be streamed all at once.
    
    This tool allows efficient querying and chunked retrieval of odds data stored in PostgreSQL.
    Use this when fetch_live_odds returns very large responses (thousands of odds entries).
    
    IMPORTANT: Use this tool when:
    - User asks for odds but the response is too large to stream all at once
    - You need to filter odds by market (e.g., "Moneyline", "Spread", "Total")
    - You need to filter by sportsbook
    - You need to get odds in chunks (use offset and limit for pagination)
    - You only need main markets (Moneyline, Spread, Total) - set main_markets_only=True
    
    Args:
        fixture_id: REQUIRED. Fixture ID to query odds for
        session_id: Optional session identifier. If not provided, uses current session from context.
        sportsbook: Optional sportsbook name to filter (e.g., "DraftKings", "FanDuel")
        market: Optional market name to filter (e.g., "Moneyline", "Spread", "Total", "Player Props")
        limit: Maximum number of entries to return (default: 50, max recommended: 100)
        offset: Offset for pagination (default: 0). Use this to get next chunk.
        main_markets_only: If True, only return main markets (Moneyline, Spread, Total). Faster query.
    
    Returns:
        Formatted string with odds entries. If main_markets_only=True, returns main markets grouped by market type.
        Includes pagination info if there are more entries.
    """
    try:
        from app.core.odds_db import get_odds_entries_chunked, get_main_markets_odds
        import json
        
        # Get session_id from context if not provided
        effective_session_id = session_id or (_current_session_id.get() if _current_session_id.get() else None) or "default"
        
        if main_markets_only:
            # Get main markets only (faster)
            main_markets = get_main_markets_odds(
                fixture_id=fixture_id,
                session_id=effective_session_id,
                sportsbook=sportsbook,
            )
            
            if not main_markets:
                return f"No main markets odds found for fixture_id={fixture_id}" + (
                    f", sportsbook={sportsbook}" if sportsbook else ""
                )
            
            formatted_lines = []
            formatted_lines.append(f"Main markets odds for fixture {fixture_id}:\n")
            
            for market_name, entries in main_markets.items():
                formatted_lines.append(f"\n{market_name}:")
                for entry in entries:
                    selection = entry.get("selection", "")
                    price = entry.get("price")
                    sportsbook_name = entry.get("sportsbook", "")
                    selection_line = entry.get("selection_line")
                    
                    price_str = f"{price:+.0f}" if price else "N/A"
                    line_str = f" ({selection_line})" if selection_line else ""
                    formatted_lines.append(f"  • {selection}{line_str}: {price_str} ({sportsbook_name})")
            
            return "\n".join(formatted_lines)
        else:
            # Get chunked odds entries
            chunk_result = get_odds_entries_chunked(
                fixture_id=fixture_id,
                session_id=effective_session_id,
                sportsbook=sportsbook,
                market=market,
                chunk_size=limit or 50,
                offset=offset or 0,
            )
            
            entries = chunk_result.get("entries", [])
            total = chunk_result.get("total", 0)
            has_more = chunk_result.get("has_more", False)
            next_offset = chunk_result.get("next_offset")
            
            if not entries:
                return f"No odds entries found for fixture_id={fixture_id}" + (
                    f", sportsbook={sportsbook}" if sportsbook else ""
                ) + (
                    f", market={market}" if market else ""
                )
            
            formatted_lines = []
            start_num = (offset or 0) + 1
            end_num = (offset or 0) + len(entries)
            formatted_lines.append(f"Found {len(entries)} odds entries (showing {start_num}-{end_num} of {total}):\n")
            
            # Group by market for better readability
            markets_dict = {}
            for entry in entries:
                market_name = entry.get("market", "Unknown")
                if market_name not in markets_dict:
                    markets_dict[market_name] = []
                markets_dict[market_name].append(entry)
            
            for market_name, market_entries in markets_dict.items():
                formatted_lines.append(f"\n{market_name}:")
                for entry in market_entries:
                    selection = entry.get("selection", "")
                    price = entry.get("price")
                    sportsbook_name = entry.get("sportsbook", "")
                    selection_line = entry.get("selection_line")
                    
                    price_str = f"{price:+.0f}" if price else "N/A"
                    line_str = f" ({selection_line})" if selection_line else ""
                    formatted_lines.append(f"  • {selection}{line_str}: {price_str} ({sportsbook_name})")
            
            if has_more:
                formatted_lines.append(f"\n\nThere are {total - (offset or 0) - len(entries)} more entries available.")
                formatted_lines.append(f"Use query_odds_entries with offset={next_offset} to get the next batch.")
            
            return "\n".join(formatted_lines)
            
    except Exception as e:
        logger.error(f"Error querying odds entries: {e}")
        return f"Error querying odds entries: {str(e)}"


@tool
def filter_odds_from_json(
    json_data: str,
    market: Optional[str] = None,
    sportsbook: Optional[str] = None,
    player_id: Optional[str] = None,
    team_id: Optional[str] = None,
    main_markets_only: bool = False,
    keep_markets: Optional[str] = None,
    remove_markets: Optional[str] = None,
) -> str:
    """Filter odds from JSON data while preserving the complete JSON structure.
    
    This tool intelligently filters odds entries from a JSON response (like from fetch_live_odds)
    while maintaining the full fixture structure. All fixture fields are preserved; only the
    odds arrays within each fixture are filtered.
    
    Use this when:
    - You have a large JSON response with many odds and need to reduce it to only relevant odds
    - You want to keep only specific markets (e.g., "Moneyline", "Spread", "Total")
    - You want to remove specific markets (e.g., remove all player props)
    - You want to filter by sportsbook, player, or team
    - You need to return a clean JSON structure with only the needed odds
    
    IMPORTANT:
    - The input json_data can be a JSON string or a file path
    - All fixture metadata (teams, venue, dates, etc.) is preserved
    - Only the odds arrays are filtered
    - Returns complete, valid JSON with the same structure as input
    
    Args:
        json_data: JSON string containing fixtures with odds, or path to JSON file.
                  Expected format: {"data": [{"id": "...", "odds": [...]}, ...]} or
                  [{"id": "...", "odds": [...]}, ...]
        market: Optional. Filter to keep only this market (e.g., "Moneyline", "Spread", "Total Points")
        sportsbook: Optional. Filter to keep only odds from this sportsbook (e.g., "DraftKings", "FanDuel")
        player_id: Optional. Filter to keep only odds for this player
        team_id: Optional. Filter to keep only odds for this team
        main_markets_only: If True, keep only main markets (Moneyline, Spread/Point Spread, Total Points/Total)
        keep_markets: Optional. Comma-separated list of markets to keep (e.g., "Moneyline,Spread,Total")
        remove_markets: Optional. Comma-separated list of markets to remove (e.g., "Player Props,Anytime Touchdown Scorer")
    
    Returns:
        JSON string with filtered odds, maintaining complete fixture structure.
        Format: Same as input but with filtered odds arrays.
    """
    try:
        import os
        
        # Try to parse json_data as JSON first, if that fails, try as file path
        try:
            data = json.loads(json_data)
        except (json.JSONDecodeError, ValueError):
            # Try as file path
            if os.path.exists(json_data):
                with open(json_data, 'r') as f:
                    data = json.load(f)
            else:
                return f"Error: json_data is not valid JSON and file path '{json_data}' does not exist"
        
        # Normalize data structure - handle both {"data": [...]} and [...] formats
        if isinstance(data, dict) and "data" in data:
            fixtures = data["data"]
            is_wrapped = True
        elif isinstance(data, list):
            fixtures = data
            is_wrapped = False
        else:
            return f"Error: Expected JSON with 'data' array or array of fixtures, got {type(data).__name__}"
        
        # Define main markets
        main_markets = ["Moneyline", "Point Spread", "Spread", "Total Points", "Total", "Run Line", "Total Runs"]
        
        # Parse keep_markets and remove_markets
        keep_markets_list = []
        if keep_markets:
            keep_markets_list = [m.strip() for m in keep_markets.split(",")]
        
        remove_markets_list = []
        if remove_markets:
            remove_markets_list = [m.strip() for m in remove_markets.split(",")]
        
        # Process each fixture
        filtered_fixtures = []
        for fixture in fixtures:
            # Create a copy of the fixture to preserve all fields
            filtered_fixture = fixture.copy()
            
            # Get odds array
            odds = fixture.get("odds", [])
            if not odds:
                # If no odds, keep fixture as-is
                filtered_fixtures.append(filtered_fixture)
                continue
            
            # Filter odds
            filtered_odds = []
            for odd in odds:
                # Apply filters
                keep_odd = True
                
                # Filter by market
                if market:
                    odd_market = odd.get("market", "")
                    if odd_market != market:
                        keep_odd = False
                
                # Filter by sportsbook
                if sportsbook and keep_odd:
                    odd_sportsbook = odd.get("sportsbook", "")
                    if odd_sportsbook.lower() != sportsbook.lower():
                        keep_odd = False
                
                # Filter by player_id
                if player_id and keep_odd:
                    odd_player_id = odd.get("player_id")
                    if str(odd_player_id) != str(player_id):
                        keep_odd = False
                
                # Filter by team_id
                if team_id and keep_odd:
                    odd_team_id = odd.get("team_id")
                    if str(odd_team_id) != str(team_id):
                        keep_odd = False
                
                # Filter by main_markets_only
                if main_markets_only and keep_odd:
                    odd_market = odd.get("market", "")
                    if odd_market not in main_markets:
                        keep_odd = False
                
                # Filter by keep_markets
                if keep_markets_list and keep_odd:
                    odd_market = odd.get("market", "")
                    if odd_market not in keep_markets_list:
                        keep_odd = False
                
                # Filter by remove_markets
                if remove_markets_list and keep_odd:
                    odd_market = odd.get("market", "")
                    # Check if any remove_markets pattern matches
                    for remove_pattern in remove_markets_list:
                        if remove_pattern.lower() in odd_market.lower():
                            keep_odd = False
                            break
                
                if keep_odd:
                    filtered_odds.append(odd)
            
            # Update fixture with filtered odds
            filtered_fixture["odds"] = filtered_odds
            filtered_fixtures.append(filtered_fixture)
        
        # Reconstruct JSON structure
        if is_wrapped:
            result = {"data": filtered_fixtures}
        else:
            result = filtered_fixtures
        
        # Return as formatted JSON string
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error filtering odds from JSON: {e}")
        return f"Error filtering odds from JSON: {str(e)}"


@tool
def query_tool_results(
    session_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    fixture_id: Optional[str] = None,
    field_name: Optional[str] = None,
    field_value: Optional[str] = None,
) -> str:
    """Query stored tool results from the database by session_id, tool_name, fixture_id, or any field.
    
    This tool allows the agent to find related data that was previously fetched and stored.
    For example, if a user selects a fixture_id in the frontend, you can use this tool to find
    all related odds, fixtures, and props that were previously fetched for that fixture.
    
    IMPORTANT: Use this tool when:
    - User selects a fixture_id and you need to find related odds/fixtures from previous queries
    - You want to find all results from a specific tool (e.g., all fetch_live_odds results)
    - You need to search by any field (fixture_id, team_id, player_id, league_id)
    
    Args:
        session_id: Session identifier (user_id or thread_id). If not provided, uses current session from context.
        tool_name: Optional tool name to filter results (e.g., "fetch_live_odds", "fetch_upcoming_games")
        fixture_id: Optional fixture ID to search for - finds all tool results related to this fixture
        field_name: Optional field name to search (fixture_id, team_id, player_id, league_id)
        field_value: Optional field value to search for (used with field_name)
    
    Returns:
        Formatted string with matching tool results, including structured data
    """
    try:
        from app.core.tool_result_db import (
            get_tool_results_by_session,
            get_tool_results_by_fixture_id,
            get_tool_results_by_field,
            search_tool_results
        )
        import json
        
        # Get session_id from context if not provided
        # _current_session_id is already imported at module level
        effective_session_id = session_id or (_current_session_id.get() if _current_session_id.get() else None) or "default"
        
        results = []
        
        # Determine which query function to use
        if fixture_id:
            # Search by fixture_id (most common use case)
            results = get_tool_results_by_fixture_id(effective_session_id, fixture_id)
        elif field_name and field_value:
            # Search by specific field
            results = get_tool_results_by_field(effective_session_id, field_name, field_value)
        elif tool_name or fixture_id or field_name:
            # Use flexible search
            query = {}
            if tool_name:
                query["tool_name"] = tool_name
            if fixture_id:
                query["fixture_id"] = fixture_id
            if field_name and field_value:
                query[field_name] = field_value
            results = search_tool_results(effective_session_id, query)
        else:
            # Get all results for session, optionally filtered by tool_name
            results = get_tool_results_by_session(effective_session_id, tool_name)
        
        if not results:
            return f"No tool results found for session_id={effective_session_id}" + (
                f", tool_name={tool_name}" if tool_name else ""
            ) + (
                f", fixture_id={fixture_id}" if fixture_id else ""
            ) + (
                f", {field_name}={field_value}" if field_name and field_value else ""
            )
        
        # Format results
        formatted_lines = []
        formatted_lines.append(f"Found {len(results)} tool result(s):\n")
        
        for i, result in enumerate(results, 1):
            formatted_lines.append(f"\n{'='*60}")
            formatted_lines.append(f"Result {i}:")
            formatted_lines.append(f"Tool: {result['tool_name']}")
            formatted_lines.append(f"Tool Call ID: {result['tool_call_id']}")
            if result.get('fixture_id'):
                formatted_lines.append(f"Fixture ID: {result['fixture_id']}")
            if result.get('team_id'):
                formatted_lines.append(f"Team ID: {result['team_id']}")
            if result.get('player_id'):
                formatted_lines.append(f"Player ID: {result['player_id']}")
            if result.get('league_id'):
                formatted_lines.append(f"League ID: {result['league_id']}")
            if result.get('created_at'):
                formatted_lines.append(f"Created At: {result['created_at']}")
            
            # Include structured data
            if result.get('structured_data'):
                formatted_lines.append(f"\nStructured Data:")
                try:
                    formatted_lines.append(json.dumps(result['structured_data'], indent=2))
                except (TypeError, ValueError):
                    formatted_lines.append(str(result['structured_data']))
        
        return "\n".join(formatted_lines)
    except Exception as e:
        return f"Error querying tool results: {str(e)}"


# Helper functions for formatting responses

def extract_fixture_id(fixture_input: Optional[str]) -> Optional[str]:
    """Extract fixture_id from either a string ID or a full fixture object (JSON string).
    
    Args:
        fixture_input: Either a fixture_id string, or a JSON string containing a full fixture object
        
    Returns:
        The fixture_id string, or None if not found
    """
    if not fixture_input:
        return None
    
    # Try to parse as JSON first (in case it's a full fixture object)
    try:
        fixture_obj = json.loads(fixture_input)
        
        # If it's a dict, try to get the fixture_id
        if isinstance(fixture_obj, dict):
            # Check for fixture_id at top level
            if "fixture_id" in fixture_obj:
                return str(fixture_obj["fixture_id"])
            # Check for id at top level
            if "id" in fixture_obj:
                return str(fixture_obj["id"])
            # Check for full_fixture nested object
            if "full_fixture" in fixture_obj and isinstance(fixture_obj["full_fixture"], dict):
                full_fixture = fixture_obj["full_fixture"]
                if "id" in full_fixture:
                    return str(full_fixture["id"])
    except (json.JSONDecodeError, ValueError, TypeError):
        # If parsing fails, assume it's just a fixture_id string
        pass
    
    # If it's not JSON or doesn't contain an ID, return as-is (assume it's a fixture_id string)
    return fixture_input


def extract_fixture_ids_from_objects(fixtures_input: Optional[str]) -> List[str]:
    """Extract fixture_ids from multiple fixture objects (array) or single object.
    
    Args:
        fixtures_input: JSON string containing either:
            - A single fixture object
            - An array of fixture objects
            - A single fixture_id string
            - An array of fixture_id strings
            - A mix of fixture objects and fixture_id strings
        
    Returns:
        List of fixture_id strings
    """
    if not fixtures_input:
        return []
    
    fixture_ids = []
    
    try:
        parsed = json.loads(fixtures_input) if isinstance(fixtures_input, str) else fixtures_input
        
        # Handle array of fixtures
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, str):
                    # Try to extract from string (could be JSON or plain ID)
                    extracted = extract_fixture_id(item)
                    if extracted:
                        fixture_ids.append(extracted)
                elif isinstance(item, dict):
                    # Extract from dict object
                    fixture_id = item.get("fixture_id") or item.get("id")
                    if fixture_id:
                        fixture_ids.append(str(fixture_id))
                    elif "full_fixture" in item and isinstance(item["full_fixture"], dict):
                        full_id = item["full_fixture"].get("id")
                        if full_id:
                            fixture_ids.append(str(full_id))
        # Handle single fixture object
        elif isinstance(parsed, dict):
            extracted = extract_fixture_id(fixtures_input if isinstance(fixtures_input, str) else json.dumps(parsed))
            if extracted:
                fixture_ids.append(extracted)
        # Handle plain string (single fixture_id)
        elif isinstance(parsed, str):
            fixture_ids.append(parsed)
            
    except (json.JSONDecodeError, ValueError, TypeError):
        # If parsing fails, try as single fixture_id string
        if isinstance(fixtures_input, str):
            fixture_ids.append(fixtures_input)
    
    return fixture_ids


def format_odds_response(data: Dict[str, Any]) -> str:
    """Format odds response with short summary and full JSON.
    
    Returns a concise summary followed by the complete JSON data in the proper format.
    """
    if not data:
        return "No odds data available - API returned empty response"
    
    fixtures = data.get("data", [])
    
    # Handle case where data might be a single fixture object
    if not isinstance(fixtures, list):
        fixtures = [fixtures] if fixtures else []
    
    # If no fixtures, return early with helpful message
    if not fixtures:
        response_keys = list(data.keys()) if isinstance(data, dict) else []
        error_msg = "No odds data available. The API returned an empty 'data' array.\n"
        error_msg += f"Response structure: {response_keys}\n"
        error_msg += "\nPossible reasons:\n"
        error_msg += "- The fixture(s) don't have odds available yet\n"
        error_msg += "- The sportsbook(s) don't have odds for this fixture\n"
        error_msg += "- The fixture_id(s) may be invalid\n"
        error_msg += "\nTry calling fetch_available_sportsbooks with fixture_id to see which sportsbooks have odds."
        return error_msg
    
    # Count fixtures and markets for summary
    total_markets = set()
    for fixture in fixtures:
        if fixture and isinstance(fixture, dict):
            odds_list = fixture.get("odds", [])
            if isinstance(odds_list, list):
                for odd in odds_list:
                    if isinstance(odd, dict):
                        market = odd.get("market")
                        if market:
                            total_markets.add(market)
    
    # Create short summary
    fixture_count = len(fixtures)
    market_count = len(total_markets)
    summary = f"Here are the odds you requested for {fixture_count} fixture(s) with {market_count} market(s)."
    
    # Return summary only - no JSON markers
    return summary


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
        
        # Extract team names - check home_team_display/away_team_display first, then fall back to competitors arrays
        home_team = fixture.get("home_team_display")
        away_team = fixture.get("away_team_display")
        
        if not home_team:
            home_competitors = fixture.get("home_competitors", [])
            if home_competitors and isinstance(home_competitors, list) and len(home_competitors) > 0:
                home_team = home_competitors[0].get("name") if isinstance(home_competitors[0], dict) else str(home_competitors[0])
        
        if not away_team:
            away_competitors = fixture.get("away_competitors", [])
            if away_competitors and isinstance(away_competitors, list) and len(away_competitors) > 0:
                away_team = away_competitors[0].get("name") if isinstance(away_competitors[0], dict) else str(away_competitors[0])
        
        # Fallback to Unknown if still not found
        home_team = home_team or "Unknown"
        away_team = away_team or "Unknown"
        
        # Parse start_date (ISO format: "2025-11-27T18:00:00Z")
        start_date_str = fixture.get("start_date")
        date_display = None
        time_display = None
        
        if start_date_str:
            try:
                # Parse ISO format datetime - handle 'Z' timezone indicator
                if start_date_str.endswith('Z'):
                    # Replace Z with +00:00 for UTC
                    iso_str = start_date_str.replace('Z', '+00:00')
                else:
                    iso_str = start_date_str
                
                dt = datetime.fromisoformat(iso_str)
                date_display = dt.strftime('%B %d, %Y')
                # Format time with timezone if available
                if dt.tzinfo:
                    time_display = dt.strftime('%I:%M %p %Z')
                else:
                    time_display = dt.strftime('%I:%M %p')
            except (ValueError, AttributeError, TypeError) as e:
                # If parsing fails, use the string as-is
                date_display = start_date_str
                time_display = None
        
        status = fixture.get("status", "Scheduled")
        
        # Extract league information
        league_info = fixture.get("league", {})
        league_name = league_info.get("name", "") if isinstance(league_info, dict) else ""
        league_id = league_info.get("id", "") if isinstance(league_info, dict) else ""
        
        # Extract additional useful fields
        venue_name = fixture.get("venue_name")
        venue_location = fixture.get("venue_location")
        broadcast = fixture.get("broadcast")
        home_record = fixture.get("home_record")
        away_record = fixture.get("away_record")
        season_type = fixture.get("season_type")
        season_year = fixture.get("season_year")
        season_week = fixture.get("season_week")
        is_live = fixture.get("is_live", False)
        has_odds = fixture.get("has_odds", False)
        
        # Format game information for display
        game_line = f"{away_team} @ {home_team}"
        if date_display:
            game_line += f" | {date_display}"
        if time_display:
            game_line += f" | {time_display}"
        if status:
            game_line += f" | Status: {status}"
        
        formatted_lines.append(f"\n{game_line}")
        if fixture_id:
            formatted_lines.append(f"Fixture ID: {fixture_id}")
        if league_name:
            formatted_lines.append(f"League: {league_name}")
        if venue_name:
            venue_info = venue_name
            if venue_location:
                venue_info += f" ({venue_location})"
            formatted_lines.append(f"Venue: {venue_info}")
        if broadcast:
            formatted_lines.append(f"Broadcast: {broadcast}")
        if home_record or away_record:
            record_info = []
            if away_record:
                record_info.append(f"Away: {away_record}")
            if home_record:
                record_info.append(f"Home: {home_record}")
            if record_info:
                formatted_lines.append(f"Records: {', '.join(record_info)}")
        if season_type and season_year:
            season_info = f"{season_type} {season_year}"
            if season_week:
                season_info += f" - Week {season_week}"
            formatted_lines.append(f"Season: {season_info}")
        if is_live:
            formatted_lines.append("🔴 LIVE")
        if has_odds:
            formatted_lines.append("Odds Available")
        
        # Add to structured data - full fixture object is the primary data
        # Frontend will extract all needed fields from the full fixture object
        structured_fixtures.append(fixture)
    
    # Add structured JSON block for frontend parsing
    # This contains the complete fixture objects - frontend extracts what it needs
    if structured_fixtures:
        formatted_lines.append(f"\n\n<!-- FIXTURES_DATA_START -->\n{json.dumps({'fixtures': structured_fixtures}, indent=2)}\n<!-- FIXTURES_DATA_END -->")      
    
    return "\n".join(formatted_lines) if formatted_lines else "No fixtures available"


def format_sports_response(data: Dict[str, Any]) -> str:
    """Format sports response with structured data for frontend parsing."""
    if not data:
        return "No sports data available"
    
    formatted_lines = []
    sports = data.get("data", [])
    
    if not isinstance(sports, list):
        sports = [sports] if sports else []
    
    if not sports:
        return "No active sports found"
    
    formatted_lines.append("Active Sports (with fixtures and odds available):\n")
    
    structured_sports = []
    
    for sport in sports:
        if not sport:
            continue
        
        sport_id = sport.get("id")
        sport_name = sport.get("name", "Unknown")
        sport_slug = sport.get("slug", "")
        
        formatted_lines.append(f"\n{sport_name}")
        if sport_id:
            formatted_lines.append(f"  ID: {sport_id}")
        if sport_slug:
            formatted_lines.append(f"  Slug: {sport_slug}")
        
        structured_sports.append({
            "sport_id": sport_id,
            "sport_name": sport_name,
            "sport_slug": sport_slug,
        })
    
    # Add structured JSON block for frontend parsing
    if structured_sports:
        formatted_lines.append(f"\n\n<!-- SPORTS_DATA_START -->\n{json.dumps({'sports': structured_sports}, indent=2)}\n<!-- SPORTS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No sports available"


def format_leagues_response(data: Dict[str, Any]) -> str:
    """Format leagues response with structured data for frontend parsing."""
    if not data:
        return "No leagues data available"
    
    formatted_lines = []
    leagues = data.get("data", [])
    
    if not isinstance(leagues, list):
        leagues = [leagues] if leagues else []
    
    if not leagues:
        return "No leagues found"
    
    formatted_lines.append("Available Leagues:\n")
    
    structured_leagues = []
    
    for league in leagues:
        if not league:
            continue
        
        league_id = league.get("id")
        league_name = league.get("name", "Unknown")
        league_slug = league.get("slug", "")
        sport_info = league.get("sport", {})
        sport_id = sport_info.get("id") if isinstance(sport_info, dict) else None
        sport_name = sport_info.get("name", "") if isinstance(sport_info, dict) else ""
        
        formatted_lines.append(f"\n{league_name}")
        if league_id:
            formatted_lines.append(f"  League ID: {league_id}")
        if league_slug:
            formatted_lines.append(f"  Slug: {league_slug}")
        if sport_name:
            formatted_lines.append(f"  Sport: {sport_name} (ID: {sport_id})")
        
        structured_leagues.append({
            "league_id": league_id,
            "league_name": league_name,
            "league_slug": league_slug,
            "sport_id": sport_id,
            "sport_name": sport_name,
        })
    
    # Add structured JSON block for frontend parsing
    if structured_leagues:
        formatted_lines.append(f"\n\n<!-- LEAGUES_DATA_START -->\n{json.dumps({'leagues': structured_leagues}, indent=2)}\n<!-- LEAGUES_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No leagues available"


def format_markets_response(data: Dict[str, Any]) -> str:
    """Format markets response with structured data for frontend parsing."""
    if not data:
        return "No markets data available"
    
    formatted_lines = []
    markets = data.get("data", [])
    
    if not isinstance(markets, list):
        markets = [markets] if markets else []
    
    if not markets:
        return "No markets found"
    
    formatted_lines.append("Available Market Names (use these EXACT names in fetch_live_odds):\n")
    formatted_lines.append("=" * 80)
    formatted_lines.append("⚠️ IMPORTANT: Use the 'market_name' field below when calling fetch_live_odds.")
    formatted_lines.append("Do NOT use market_type - that's for reference only.\n")
    
    structured_markets = []
    
    # Group by market_type for easier reading
    player_prop_markets = []
    main_markets = []
    other_markets = []
    
    for market in markets:
        if not market:
            continue
        
        market_id = market.get("id")
        market_name = market.get("name", "Unknown")
        market_type = market.get("market_type", "")
        market_slug = market.get("slug", "")
        
        # Categorize for better organization
        if market_type and market_type.startswith("player_"):
            player_prop_markets.append(market)
        elif market_type in ["moneyline", "spread", "total", "asian_handicap", "asian_total", "team_total"]:
            main_markets.append(market)
        else:
            other_markets.append(market)
        
        structured_markets.append({
            "market_id": market_id,
            "market_name": market_name,  # THIS is what to use in fetch_live_odds
            "market_type": market_type,  # For reference only
            "market_slug": market_slug,
        })
    
    # Format main markets
    if main_markets:
        formatted_lines.append("\n--- Main Markets (use market_name in fetch_live_odds) ---")
        for market in sorted(main_markets, key=lambda x: x.get("name", "")):
            market_name = market.get("name", "Unknown")
            market_type = market.get("market_type", "")
            formatted_lines.append(f"  ✅ {market_name} (market_type: {market_type})")
    
    # Format player prop markets
    if player_prop_markets:
        formatted_lines.append("\n--- Player Prop Markets (use market_name in fetch_live_odds) ---")
        for market in sorted(player_prop_markets, key=lambda x: x.get("name", "")):
            market_name = market.get("name", "Unknown")
            market_type = market.get("market_type", "")
            formatted_lines.append(f"  ✅ {market_name} (market_type: {market_type})")
    
    # Format other markets
    if other_markets:
        formatted_lines.append("\n--- Other Markets (use market_name in fetch_live_odds) ---")
        for market in sorted(other_markets, key=lambda x: x.get("name", "")):
            market_name = market.get("name", "Unknown")
            market_type = market.get("market_type", "")
            formatted_lines.append(f"  ✅ {market_name} (market_type: {market_type})")
        
        structured_markets.append({
            "market_id": market_id,
            "market_name": market_name,
            "market_type": market_type,
            "market_slug": market_slug,
        })
    
    # Add structured JSON block for frontend parsing
    if structured_markets:
        formatted_lines.append(f"\n\n<!-- MARKETS_DATA_START -->\n{json.dumps({'markets': structured_markets}, indent=2)}\n<!-- MARKETS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No markets available"


def format_market_types_response(data: Dict[str, Any]) -> str:
    """Format market types response with structured data for frontend parsing."""
    if not data:
        return "No market types data available"
    
    formatted_lines = []
    market_types = data.get("data", [])
    
    if not isinstance(market_types, list):
        market_types = [market_types] if market_types else []
    
    if not market_types:
        return "No market types found"
    
    formatted_lines.append("Available Market Types:\n")
    formatted_lines.append("=" * 60)
    formatted_lines.append("\nIMPORTANT: Use the exact 'name' field when requesting odds (e.g., 'moneyline', 'spread', 'player_total').")
    formatted_lines.append("Do NOT use display names - use the exact market type name from the 'name' field.\n")
    
    structured_market_types = []
    
    # Group by category for easier reading
    player_prop_types = []
    main_market_types = []
    other_types = []
    
    for market_type in market_types:
        if not market_type:
            continue
        
        market_id = market_type.get("id")
        market_name = market_type.get("name", "Unknown")
        selections = market_type.get("selections", [])
        notes = market_type.get("notes")
        
        # Categorize
        if market_name.startswith("player_"):
            player_prop_types.append(market_type)
        elif market_name in ["moneyline", "spread", "total", "asian_handicap", "asian_total", "team_total"]:
            main_market_types.append(market_type)
        else:
            other_types.append(market_type)
        
        structured_market_types.append({
            "id": market_id,
            "name": market_name,
            "selections": selections,
            "notes": notes,
        })
    
    # Format main markets
    if main_market_types:
        formatted_lines.append("\n--- Main Market Types ---")
        for market_type in sorted(main_market_types, key=lambda x: x.get("id", 0)):
            market_id = market_type.get("id")
            market_name = market_type.get("name", "Unknown")
            selections = market_type.get("selections", [])
            notes = market_type.get("notes")
            
            formatted_lines.append(f"\n{market_name} (ID: {market_id})")
            if selections:
                formatted_lines.append(f"  Selections: {', '.join(selections[:3])}{'...' if len(selections) > 3 else ''}")
            if notes:
                formatted_lines.append(f"  Notes: {notes}")
    
    # Format player prop types
    if player_prop_types:
        formatted_lines.append("\n--- Player Prop Market Types ---")
        for market_type in sorted(player_prop_types, key=lambda x: x.get("id", 0)):
            market_id = market_type.get("id")
            market_name = market_type.get("name", "Unknown")
            selections = market_type.get("selections", [])
            notes = market_type.get("notes")
            
            formatted_lines.append(f"\n{market_name} (ID: {market_id})")
            if selections:
                formatted_lines.append(f"  Selections: {', '.join(selections[:3])}{'...' if len(selections) > 3 else ''}")
            if notes:
                formatted_lines.append(f"  Notes: {notes}")
    
    # Format other types
    if other_types:
        formatted_lines.append("\n--- Other Market Types ---")
        for market_type in sorted(other_types, key=lambda x: x.get("id", 0)):
            market_id = market_type.get("id")
            market_name = market_type.get("name", "Unknown")
            selections = market_type.get("selections", [])
            notes = market_type.get("notes")
            
            formatted_lines.append(f"\n{market_name} (ID: {market_id})")
            if selections:
                formatted_lines.append(f"  Selections: {', '.join(selections[:3])}{'...' if len(selections) > 3 else ''}")
            if notes:
                formatted_lines.append(f"  Notes: {notes}")
    
    # Add structured JSON block for frontend parsing
    if structured_market_types:
        formatted_lines.append(f"\n\n<!-- MARKET_TYPES_DATA_START -->\n{json.dumps({'market_types': structured_market_types}, indent=2)}\n<!-- MARKET_TYPES_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No market types available"


def format_players_response(data: Dict[str, Any], player_name: Optional[str] = None, league: Optional[str] = None) -> str:
    """Format players response with structured data for frontend parsing."""
    if not data:
        return "No players data available"
    
    formatted_lines = []
    players = data.get("data", [])
    
    if not isinstance(players, list):
        players = [players] if players else []
    
    # Filter by player_name if provided (case-insensitive partial match)
    if player_name:
        player_name_lower = player_name.lower()
        players = [
            p for p in players 
            if p and player_name_lower in p.get("name", "").lower()
        ]
    
    if not players:
        if player_name:
            return f"No players found matching '{player_name}'" + (f" in league '{league}'" if league else "")
        return "No players found" + (f" in league '{league}'" if league else "")
    
    # Header
    if player_name:
        formatted_lines.append(f"Players matching '{player_name}':" + (f" (League: {league})" if league else ""))
    else:
        formatted_lines.append("Players:" + (f" (League: {league})" if league else ""))
    
    formatted_lines.append(f"Found {len(players)} player(s)\n")
    
    structured_players = []
    
    for player in players:
        if not player:
            continue
        
        player_id = player.get("id")
        player_name_display = player.get("name", "Unknown")
        numerical_id = player.get("numerical_id")
        
        # Get team info
        team_info = player.get("team")
        team_name = team_info.get("name", "Unknown") if isinstance(team_info, dict) else "Unknown"
        team_id = team_info.get("id") if isinstance(team_info, dict) else None
        
        # Get league info
        league_info = player.get("league")
        league_name = league_info.get("name", "Unknown") if isinstance(league_info, dict) else "Unknown"
        league_id = league_info.get("id") if isinstance(league_info, dict) else None
        
        # Get sport info
        sport_info = player.get("sport")
        sport_name = sport_info.get("name", "Unknown") if isinstance(sport_info, dict) else "Unknown"
        
        # Format player entry
        formatted_lines.append(f"\n{player_name_display}")
        formatted_lines.append(f"  Player ID: {player_id} (LEAGUE-SPECIFIC - use this ID for {league_name or league})")
        if numerical_id:
            formatted_lines.append(f"  Numerical ID: {numerical_id}")
        formatted_lines.append(f"  Team: {team_name}" + (f" (ID: {team_id})" if team_id else ""))
        formatted_lines.append(f"  League: {league_name}" + (f" (ID: {league_id})" if league_id else ""))
        formatted_lines.append(f"  Sport: {sport_name}")
        
        # Additional info
        position = player.get("position")
        if position:
            formatted_lines.append(f"  Position: {position}")
        
        structured_players.append({
            "player_id": player_id,
            "player_name": player_name_display,
            "numerical_id": numerical_id,
            "team": {
                "id": team_id,
                "name": team_name,
            } if team_id else None,
            "league": {
                "id": league_id,
                "name": league_name,
            } if league_id else None,
            "sport": {
                "name": sport_name,
            },
            "position": position,
        })
    
    # Add structured JSON block for frontend parsing
    if structured_players:
        formatted_lines.append(f"\n\n<!-- PLAYERS_DATA_START -->\n{json.dumps({'players': structured_players}, indent=2)}\n<!-- PLAYERS_DATA_END -->")
    
    # Add warning about league-specific IDs
    formatted_lines.append("\n\n⚠️ IMPORTANT: Player IDs are league-specific!")
    formatted_lines.append("When using player_id in fetch_live_odds or fetch_player_props, make sure")
    formatted_lines.append(f"the player_id matches the league you're querying ({league_name or league or 'the specified league'}).")
    
    return "\n".join(formatted_lines) if formatted_lines else "No players available"


def format_teams_response(data: Dict[str, Any], team_name: Optional[str] = None, league: Optional[str] = None) -> str:
    """Format teams response with structured data for frontend parsing."""
    if not data:
        return "No teams data available"
    
    formatted_lines = []
    teams = data.get("data", [])
    
    if not isinstance(teams, list):
        teams = [teams] if teams else []
    
    # Filter by team_name if provided (case-insensitive partial match)
    if team_name:
        team_name_lower = team_name.lower()
        teams = [
            t for t in teams 
            if t and team_name_lower in t.get("name", "").lower()
        ]
    
    if not teams:
        if team_name:
            return f"No teams found matching '{team_name}'" + (f" in league '{league}'" if league else "")
        return "No teams found" + (f" in league '{league}'" if league else "")
    
    # Header
    if team_name:
        formatted_lines.append(f"Teams matching '{team_name}':" + (f" (League: {league})" if league else ""))
    else:
        formatted_lines.append("Teams:" + (f" (League: {league})" if league else ""))
    
    formatted_lines.append(f"Found {len(teams)} team(s)\n")
    
    structured_teams = []
    
    # Group teams by division/conference if applicable
    teams_by_division = {}
    teams_by_conference = {}
    ungrouped_teams = []
    
    for team in teams:
        if not team:
            continue
        
        division = team.get("division")
        conference = team.get("conference")
        
        if division:
            if division not in teams_by_division:
                teams_by_division[division] = []
            teams_by_division[division].append(team)
        elif conference:
            if conference not in teams_by_conference:
                teams_by_conference[conference] = []
            teams_by_conference[conference].append(team)
        else:
            ungrouped_teams.append(team)
    
    # Format teams grouped by division/conference
    def format_team_entry(team):
        team_id = team.get("id")
        team_name_display = team.get("name", "Unknown")
        abbreviation = team.get("abbreviation", "")
        city = team.get("city", "")
        mascot = team.get("mascot", "")
        nickname = team.get("nickname", "")
        numerical_id = team.get("numerical_id")
        base_id = team.get("base_id")
        division = team.get("division")
        conference = team.get("conference")
        logo = team.get("logo", "")
        is_active = team.get("is_active", True)
        
        # Get league info
        league_info = team.get("league")
        league_name = league_info.get("name", "Unknown") if isinstance(league_info, dict) else "Unknown"
        league_id = league_info.get("id") if isinstance(league_info, dict) else None
        
        # Get sport info
        sport_info = team.get("sport")
        sport_name = sport_info.get("name", "Unknown") if isinstance(sport_info, dict) else "Unknown"
        
        # Format team entry
        formatted_lines.append(f"\n{team_name_display}")
        formatted_lines.append(f"  Team ID: {team_id} (LEAGUE-SPECIFIC - use this ID for {league_name or league})")
        if abbreviation:
            formatted_lines.append(f"  Abbreviation: {abbreviation}")
        if city:
            formatted_lines.append(f"  City: {city}")
        if mascot:
            formatted_lines.append(f"  Mascot: {mascot}")
        if nickname and nickname != mascot:
            formatted_lines.append(f"  Nickname: {nickname}")
        if division:
            formatted_lines.append(f"  Division: {division}")
        if conference:
            formatted_lines.append(f"  Conference: {conference}")
        if base_id:
            formatted_lines.append(f"  Base ID: {base_id} (for cross-league linking)")
        if numerical_id:
            formatted_lines.append(f"  Numerical ID: {numerical_id}")
        formatted_lines.append(f"  League: {league_name}" + (f" (ID: {league_id})" if league_id else ""))
        formatted_lines.append(f"  Sport: {sport_name}")
        if logo:
            formatted_lines.append(f"  Logo: {logo}")
        if not is_active:
            formatted_lines.append(f"  Status: Inactive")
        
        structured_teams.append({
            "team_id": team_id,
            "team_name": team_name_display,
            "abbreviation": abbreviation,
            "city": city,
            "mascot": mascot,
            "nickname": nickname,
            "numerical_id": numerical_id,
            "base_id": base_id,
            "division": division,
            "conference": conference,
            "logo": logo,
            "is_active": is_active,
            "league": {
                "id": league_id,
                "name": league_name,
            } if league_id else None,
            "sport": {
                "name": sport_name,
            },
        })
    
    # Display teams grouped by division if available
    if teams_by_division:
        for division, div_teams in sorted(teams_by_division.items()):
            formatted_lines.append(f"\n{'='*60}")
            formatted_lines.append(f"Division: {division}")
            formatted_lines.append(f"{'='*60}")
            for team in div_teams:
                format_team_entry(team)
    
    # Display teams grouped by conference if available (and not already in division)
    if teams_by_conference:
        for conference, conf_teams in sorted(teams_by_conference.items()):
            formatted_lines.append(f"\n{'='*60}")
            formatted_lines.append(f"Conference: {conference}")
            formatted_lines.append(f"{'='*60}")
            for team in conf_teams:
                format_team_entry(team)
    
    # Display ungrouped teams
    if ungrouped_teams:
        if teams_by_division or teams_by_conference:
            formatted_lines.append(f"\n{'='*60}")
            formatted_lines.append("Other Teams")
            formatted_lines.append(f"{'='*60}")
        for team in ungrouped_teams:
            format_team_entry(team)
    
    # Add structured JSON block for frontend parsing
    if structured_teams:
        formatted_lines.append(f"\n\n<!-- TEAMS_DATA_START -->\n{json.dumps({'teams': structured_teams}, indent=2)}\n<!-- TEAMS_DATA_END -->")
    
    # Add warning about league-specific IDs
    formatted_lines.append("\n\n⚠️ IMPORTANT: Team IDs are league-specific!")
    formatted_lines.append("When using team_id in fetch_live_odds or other tools, make sure")
    formatted_lines.append(f"the team_id matches the league you're querying ({league or 'the specified league'}).")
    formatted_lines.append("base_id can help link teams across leagues but isn't 100% reliable for all sports.")
    
    return "\n".join(formatted_lines) if formatted_lines else "No teams available"


def format_sportsbooks_response(data: Dict[str, Any]) -> str:
    """Format sportsbooks response with structured data for frontend parsing."""
    if not data:
        return "No sportsbooks data available"
    
    formatted_lines = []
    sportsbooks = data.get("data", [])
    
    if not isinstance(sportsbooks, list):
        sportsbooks = [sportsbooks] if sportsbooks else []
    
    if not sportsbooks:
        return "No active sportsbooks found"
    
    formatted_lines.append("Available Active Sportsbooks:\n")
    
    structured_sportsbooks = []
    
    # Separate onshore and offshore for better organization
    onshore_sportsbooks = []
    offshore_sportsbooks = []
    
    for sportsbook in sportsbooks:
        if not sportsbook:
            continue
        
        sportsbook_id = sportsbook.get("id")
        sportsbook_name = sportsbook.get("name", "Unknown")
        is_onshore = sportsbook.get("is_onshore", False)
        is_active = sportsbook.get("is_active", True)
        logo = sportsbook.get("logo", "")
        
        # Only include active sportsbooks
        if not is_active:
            continue
        
        sportsbook_info = {
            "id": sportsbook_id,
            "name": sportsbook_name,
            "is_onshore": is_onshore,
            "is_active": is_active,
            "logo": logo,
        }
        
        if is_onshore:
            onshore_sportsbooks.append(sportsbook_info)
        else:
            offshore_sportsbooks.append(sportsbook_info)
        
        structured_sportsbooks.append({
            "sportsbook_id": sportsbook_id,
            "sportsbook_name": sportsbook_name,
            "is_onshore": is_onshore,
            "is_active": is_active,
            "logo": logo,
        })
    
    # Display onshore sportsbooks first (typically more commonly used)
    if onshore_sportsbooks:
        formatted_lines.append("\n📍 Onshore Sportsbooks:")
        for sb in onshore_sportsbooks:
            formatted_lines.append(f"  • {sb['name']} (ID: {sb['id']})")
    
    if offshore_sportsbooks:
        formatted_lines.append("\n🌍 Offshore Sportsbooks:")
        for sb in offshore_sportsbooks:
            formatted_lines.append(f"  • {sb['name']} (ID: {sb['id']})")
    
    formatted_lines.append(f"\nTotal: {len(structured_sportsbooks)} active sportsbook(s)")
    
    # Add structured JSON block for frontend parsing
    if structured_sportsbooks:
        formatted_lines.append(f"\n\n<!-- SPORTSBOOKS_DATA_START -->\n{json.dumps({'sportsbooks': structured_sportsbooks}, indent=2)}\n<!-- SPORTSBOOKS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No sportsbooks available"

