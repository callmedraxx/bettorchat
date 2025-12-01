"""
Helper functions to build OpticOdds API URLs from tool calls.
Replicates the exact parameter processing logic from the tools to ensure accuracy.

Note: This module now generates proxy URLs (e.g., /api/v1/opticodds/proxy/{endpoint})
instead of direct OpticOdds URLs, allowing the frontend to call through the backend
to avoid CORS issues. The proxy endpoint automatically adds the API key.
"""
import json
import re
from typing import Dict, Any, Optional, List


def extract_fixture_id(fixture_json: str) -> Optional[str]:
    """Extract fixture ID from fixture JSON string (same logic as in betting_tools.py)."""
    try:
        if isinstance(fixture_json, str):
            data = json.loads(fixture_json)
        else:
            data = fixture_json
        
        if isinstance(data, dict):
            # Try different possible keys
            for key in ["id", "fixture_id", "fixtureId"]:
                if key in data:
                    return str(data[key])
        
        # Try to find ID in string if JSON parsing didn't work
        if isinstance(fixture_json, str):
            # Look for pattern like "id": "20251127E5C64DE0"
            match = re.search(r'"id"\s*:\s*"([^"]+)"', fixture_json)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def build_opticodds_url_from_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> Optional[str]:
    """Build OpticOdds API URL from a tool name and its arguments.
    
    This function replicates the exact parameter processing logic from the tool functions
    to ensure the URL is accurate and will give the desired result.
    
    Args:
        tool_name: Name of the tool being called
        tool_args: Dictionary of tool arguments
    
    Returns:
        Proxy URL string (relative path) or None if tool doesn't map to OpticOdds API or URL cannot be built
        Format: /api/v1/opticodds/proxy/{endpoint}?params...
        Note: API key is NOT included in the URL (proxy endpoint adds it automatically)
    """
    # Map tool names to OpticOdds endpoints
    tool_endpoint_map = {
        "fetch_live_odds": "/fixtures/odds",
        "fetch_upcoming_games": "/fixtures",
        "fetch_player_props": "/fixtures/odds",
        "fetch_live_game_stats": "/fixtures/results",
        "fetch_injury_reports": "/injuries",
        "fetch_futures": "/futures",
        "fetch_grader": "/grader/odds",
        "fetch_historical_odds": "/fixtures/odds/historical",
        "fetch_available_sports": "/sports/active",
        "fetch_available_leagues": "/leagues/active",
        "fetch_available_markets": "/markets/active",
        "fetch_available_sportsbooks": "/sportsbooks/active",
        "fetch_players": "/players",
        "fetch_teams": "/teams",
    }
    
    endpoint = tool_endpoint_map.get(tool_name)
    if not endpoint:
        return None
    
    # Build params from tool arguments - replicate exact logic from tools
    params = {}
    
    if tool_name == "fetch_live_odds":
        # Process sportsbook - REQUIRED per OpticOdds API, max 5, must be lowercase
        # Replicate exact logic from fetch_live_odds tool
        if "sportsbook" in tool_args and tool_args["sportsbook"]:
            sportsbook = tool_args["sportsbook"]
            if isinstance(sportsbook, str) and ',' in sportsbook:
                resolved_sportsbook = [sb.strip().lower() for sb in sportsbook.split(',') if sb.strip()][:5]
            elif isinstance(sportsbook, str):
                resolved_sportsbook = [sportsbook.strip().lower()]
            else:
                resolved_sportsbook = [str(sb).strip().lower() for sb in (list(sportsbook)[:5] if isinstance(sportsbook, (list, tuple)) else [sportsbook])]
        else:
            # User didn't specify - use comprehensive list of popular sportsbooks (API limit is 5 per request)
            # Use top 5 most popular to show all odds from major sportsbooks
            resolved_sportsbook = ["draftkings", "fanduel", "betmgm", "caesars", "betrivers"]
        
        if not resolved_sportsbook:
            # Fallback to comprehensive list
            resolved_sportsbook = ["draftkings", "fanduel", "betmgm", "caesars", "betrivers"]
        
        # OpticOdds API requirement: sportsbook is REQUIRED, max 5, lowercase
        params["sportsbook"] = resolved_sportsbook
        
        # Process market parameter - OPTIONAL per OpticOdds API
        # If user specifies, use exactly; otherwise omit to get all markets
        # NOTE: "Player Props" and market type names (like "player_total", "player_yes_no") are not valid market names
        # Player props are identified by market_type in the response, not by market name
        # When these are requested, we should NOT filter by market to get all markets, then filter by market_type
        resolved_market = None
        if "market" in tool_args and tool_args["market"]:
            market = tool_args["market"]
            if isinstance(market, str) and ',' in market:
                resolved_market = [m.strip() for m in market.split(',') if m.strip()]
            elif isinstance(market, str):
                resolved_market = [market.strip()]
            else:
                resolved_market = market if isinstance(market, list) else [str(market)]
            
            # Import market types to check if a market name is actually a market type
            from app.core.market_types import get_market_type_by_name, is_player_prop_market_type
            
            # Filter out invalid market names:
            # 1. "Player Props" (generic category)
            # 2. Market type names (like "player_total", "player_yes_no", "player_only")
            # These are not valid market names - the API expects actual market names like "Player Points", "Player Receptions"
            # When these are requested, we should NOT send them as market parameters
            # Instead, fetch all markets and filter by market_type in the response
            filtered_markets = []
            has_player_props_or_types = False
            for m in resolved_market:
                m_str = m.strip()
                m_lower = m_str.lower()
                
                # Check for variations of "Player Props" (generic category)
                if m_lower in ["player props", "player_props", "player-props", "playerprops"]:
                    has_player_props_or_types = True
                    # Don't add to market filter - we'll filter by market_type in response
                # Check if it's a market type name (not a market name)
                elif get_market_type_by_name(m_str) or is_player_prop_market_type(m_str):
                    # This is a market type name, not a market name
                    # Market type names like "player_total", "player_yes_no" are not valid market names for the API
                    has_player_props_or_types = True
                    # Don't add to market filter - we'll filter by market_type in response
                else:
                    # It's a valid market name - keep it
                    filtered_markets.append(m_str)
            
            # Only add market parameter if there are valid market names (not market types or "Player Props")
            if filtered_markets:
                params["market"] = filtered_markets
            # If only "Player Props" or market types were requested, don't add market parameter - fetch all markets
            # The response will need to be filtered by market_type on the frontend/backend
        # If user didn't specify market, don't add it to params - this will fetch all available markets per OpticOdds API
        
        # Collect fixture IDs (up to 5) - same logic as tool
        fixture_ids_list: List[str] = []
        
        # Extract from fixtures parameter (JSON array of fixture objects)
        if "fixtures" in tool_args and tool_args["fixtures"]:
            try:
                fixtures_data = json.loads(tool_args["fixtures"]) if isinstance(tool_args["fixtures"], str) else tool_args["fixtures"]
                if isinstance(fixtures_data, list):
                    for fixture_obj in fixtures_data[:5]:
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
        if "fixture" in tool_args and tool_args["fixture"] and not fixture_ids_list:
            try:
                fixture_obj = json.loads(tool_args["fixture"]) if isinstance(tool_args["fixture"], str) else tool_args["fixture"]
                if isinstance(fixture_obj, dict):
                    fid = extract_fixture_id(json.dumps(tool_args["fixture"]) if isinstance(tool_args["fixture"], str) else json.dumps(fixture_obj))
                    if fid:
                        fixture_ids_list.append(fid)
            except Exception:
                pass
        
        # Extract from fixture_id parameter (single or comma-separated)
        if "fixture_id" in tool_args and tool_args["fixture_id"]:
            fixture_id = tool_args["fixture_id"]
            if isinstance(fixture_id, str) and ',' in fixture_id:
                ids = [fid.strip() for fid in fixture_id.split(',') if fid.strip()][:5]
                for fid in ids:
                    if fid not in fixture_ids_list:
                        fixture_ids_list.append(fid)
            else:
                # Try to extract from JSON first, but if it fails, use the value directly
                # (it might already be a fixture ID string)
                fid = extract_fixture_id(fixture_id) if fixture_id else None
                if not fid and fixture_id:
                    # If extract_fixture_id returned None, the fixture_id might already be a plain ID string
                    # Check if it looks like a valid fixture ID (alphanumeric, typically starts with date)
                    if isinstance(fixture_id, str) and fixture_id.strip():
                        fid = fixture_id.strip()
                if fid and fid not in fixture_ids_list:
                    fixture_ids_list.append(fid)
        
        # Limit to 5 fixture IDs per API requirement
        fixture_ids_list = fixture_ids_list[:5]
        
        # API requires at least one of: fixture_id, team_id, or player_id
        # Priority: fixture_id > team_id > player_id (most specific to least specific)
        # If user specified player_id, use it (player props)
        # If user specified team_id but no fixture_id, use team_id (team-level odds)
        # If user specified fixture_id, use it (game-specific odds)
        
        has_fixture = bool(fixture_ids_list)
        has_team = "team_id" in tool_args and tool_args["team_id"]
        has_player = "player_id" in tool_args and tool_args["player_id"]
        
        # If none provided, we can't build a valid URL
        if not has_fixture and not has_team and not has_player:
            return None
        
        # OpticOdds API requirement: At least one of fixture_id, team_id, or player_id is required
        # Add parameters in priority order (most specific first)
        # Match exact format from OpticOddsClient.get_fixture_odds()
        if has_fixture:
            # User specified fixture(s) - most specific, get game-level odds
            # OpticOdds API: fixture_id can be single value or list (up to 5)
            if len(fixture_ids_list) > 1:
                # Multiple fixture_ids - pass as list (API creates multiple query params)
                params["fixture_id"] = fixture_ids_list[:5]  # Enforce max 5 limit
            else:
                # Single fixture_id - pass as string
                params["fixture_id"] = str(fixture_ids_list[0])
            # If user also specified player_id, include it for player props
            if has_player:
                params["player_id"] = str(tool_args["player_id"])
        elif has_team:
            # User specified team but no fixture - get team-level odds
            params["team_id"] = str(tool_args["team_id"])
            # If user also specified player_id, include it for player props
            if has_player:
                params["player_id"] = str(tool_args["player_id"])
        elif has_player:
            # Only player_id specified - valid for player props (API only requires sportsbook + player_id)
            params["player_id"] = str(tool_args["player_id"])
    
    elif tool_name == "fetch_upcoming_games":
        # Check if this is for NFL - if so, we'll use the local endpoint
        is_nfl = False
        league_value = None
        if "league" in tool_args and tool_args["league"]:
            league_value = str(tool_args["league"]).lower()
            is_nfl = league_value == "nfl"
        elif "league_id" in tool_args and tool_args["league_id"]:
            league_value = str(tool_args["league_id"]).lower()
            is_nfl = league_value == "nfl" or league_value == "367"  # NFL league ID is 367
        
        # Priority: fixture_id (most specific) > league/league_id + team_id + dates > league/league_id + dates > league/league_id
        if "fixture_id" in tool_args and tool_args["fixture_id"]:
            # Most specific - single fixture
            if is_nfl:
                # For NFL, use local endpoint with id parameter
                params["id"] = str(tool_args["fixture_id"])
            else:
                params["fixture_id"] = str(tool_args["fixture_id"])
        else:
            if is_nfl:
                # For NFL, map to local endpoint parameters
                # Local endpoint uses: id, home_team, away_team, status, season_year, season_week, 
                # start_date_from, start_date_to, etc.
                # Note: team_id from OpticOdds needs to be converted to team name lookup
                # For now, we'll use the league filter and let the endpoint handle it
                pass  # League is already handled by the endpoint path
            else:
                # Use league filter (prefer league_id over league name) for non-NFL
                if "league_id" in tool_args and tool_args["league_id"]:
                    params["league"] = str(tool_args["league_id"])
                elif "league" in tool_args and tool_args["league"]:
                    params["league"] = str(tool_args["league"])
            
            # Add team filter if specified (for non-NFL, use team_id; for NFL, we'd need team name)
            if "team_id" in tool_args and tool_args["team_id"]:
                if not is_nfl:
                    params["team_id"] = str(tool_args["team_id"])
                # For NFL, team_id would need to be converted to team name - skip for now
            
            # Add date filters if specified
            if "start_date_after" in tool_args and tool_args["start_date_after"]:
                if is_nfl:
                    params["start_date_from"] = str(tool_args["start_date_after"])
                else:
                    params["start_date_after"] = str(tool_args["start_date_after"])
            if "start_date_before" in tool_args and tool_args["start_date_before"]:
                if is_nfl:
                    params["start_date_to"] = str(tool_args["start_date_before"])
                else:
                    params["start_date_before"] = str(tool_args["start_date_before"])
    
    elif tool_name == "fetch_player_props":
        # Player props uses same endpoint as fetch_live_odds (/fixtures/odds)
        # Replicate exact logic from fetch_live_odds for consistency
        # OpticOdds API requirements: sportsbook REQUIRED (max 5, lowercase), at least fixture_id or player_id
        if "sportsbook" in tool_args and tool_args["sportsbook"]:
            sportsbook = tool_args["sportsbook"]
            if isinstance(sportsbook, str) and ',' in sportsbook:
                resolved_sportsbook = [sb.strip().lower() for sb in sportsbook.split(',') if sb.strip()][:5]
            elif isinstance(sportsbook, str):
                resolved_sportsbook = [sportsbook.strip().lower()]
            else:
                resolved_sportsbook = [str(sb).strip().lower() for sb in (list(sportsbook)[:5] if isinstance(sportsbook, (list, tuple)) else [sportsbook])]
        else:
            # Default to multiple popular sportsbooks if not specified (max 5 per OpticOdds API)
            resolved_sportsbook = ["draftkings", "fanduel", "betmgm", "caesars", "betrivers"]
        
        if not resolved_sportsbook:
            resolved_sportsbook = ["draftkings", "fanduel", "betmgm", "caesars", "betrivers"]
        
        params["sportsbook"] = resolved_sportsbook
        
        # Player props needs fixture_id (for specific game) or player_id (for player across games)
        # Per OpticOdds API: at least one is required
        if "fixture_id" in tool_args and tool_args["fixture_id"]:
            # OpticOdds API: fixture_id can be string or list (up to 5)
            # Match format from OpticOddsClient.get_fixture_odds()
            fixture_id = tool_args["fixture_id"]
            if isinstance(fixture_id, str) and ',' in fixture_id:
                params["fixture_id"] = [fid.strip() for fid in fixture_id.split(',') if fid.strip()][:5]
            else:
                params["fixture_id"] = str(fixture_id)
        if "player_id" in tool_args and tool_args["player_id"]:
            params["player_id"] = str(tool_args["player_id"])
    
    elif tool_name == "fetch_live_game_stats":
        if "fixture_id" in tool_args and tool_args["fixture_id"]:
            params["fixture_id"] = str(tool_args["fixture_id"])
        if "player_id" in tool_args and tool_args["player_id"]:
            params["player_id"] = str(tool_args["player_id"])
    
    elif tool_name == "fetch_injury_reports":
        if "sport_id" in tool_args and tool_args["sport_id"]:
            params["sport_id"] = str(tool_args["sport_id"])
        if "league_id" in tool_args and tool_args["league_id"]:
            params["league_id"] = str(tool_args["league_id"])
        if "team_id" in tool_args and tool_args["team_id"]:
            params["team_id"] = str(tool_args["team_id"])
    
    elif tool_name == "fetch_available_sportsbooks":
        if "sport" in tool_args and tool_args["sport"]:
            params["sport"] = str(tool_args["sport"])
        if "league" in tool_args and tool_args["league"]:
            params["league"] = str(tool_args["league"])
        if "fixture_id" in tool_args and tool_args["fixture_id"]:
            params["fixture_id"] = str(tool_args["fixture_id"])
    
    elif tool_name == "fetch_players":
        if "league" in tool_args and tool_args["league"]:
            params["league"] = str(tool_args["league"])
        if "player_id" in tool_args and tool_args["player_id"]:
            params["id"] = str(tool_args["player_id"])
        if "base_id" in tool_args and tool_args["base_id"]:
            # base_id is the fastest way to get specific player info
            # Can be single value or list
            base_id = tool_args["base_id"]
            if isinstance(base_id, (list, tuple)):
                params["base_id"] = [str(bid) for bid in base_id]
            else:
                params["base_id"] = str(base_id)
        if "player_name" in tool_args and tool_args["player_name"]:
            # Note: player_name filtering is done client-side, not in URL
            pass
    
    elif tool_name == "fetch_teams":
        if "league" in tool_args and tool_args["league"]:
            params["league"] = str(tool_args["league"])
        if "team_id" in tool_args and tool_args["team_id"]:
            params["id"] = str(tool_args["team_id"])
        if "team_name" in tool_args and tool_args["team_name"]:
            # Note: team_name filtering is done client-side, not in URL
            pass
    
    # Validate that we have required parameters before building URL
    # This ensures the URL will be valid and functional per OpticOdds API requirements
    
    # Validate based on OpticOdds API endpoint requirements
    if tool_name == "fetch_live_odds":
        # OpticOdds API requirements for /fixtures/odds:
        # 1. sportsbook is REQUIRED (at least 1, max 5)
        # 2. At least one of: fixture_id, team_id, or player_id is REQUIRED
        if "sportsbook" not in params or not params["sportsbook"]:
            return None  # Sportsbook is required per OpticOdds API
        # Validate sportsbook count (max 5)
        sportsbook_list = params["sportsbook"]
        if isinstance(sportsbook_list, list) and len(sportsbook_list) > 5:
            params["sportsbook"] = sportsbook_list[:5]  # Enforce max 5 limit
        if "fixture_id" not in params and "team_id" not in params and "player_id" not in params:
            return None  # Need at least one identifier per OpticOdds API requirement
    
    elif tool_name == "fetch_player_props":
        # Requires: sportsbook (already set) AND at least one of: fixture_id or player_id
        if "sportsbook" not in params or not params["sportsbook"]:
            return None
        if "fixture_id" not in params and "player_id" not in params:
            return None  # Need at least fixture_id or player_id
    
    elif tool_name == "fetch_upcoming_games":
        # At least one filter should be present for a useful query
        # But API doesn't strictly require it, so we allow it
        pass
    
    elif tool_name == "fetch_players":
        # Requires at least one of: league, player_id (id), base_id, or sport
        # base_id + league is the fastest route for specific player info
        if "league" not in params and "id" not in params and "base_id" not in params:
            return None  # Need at least league, player_id, or base_id
    
    elif tool_name == "fetch_teams":
        # Requires at least one of: league, team_id, or sport
        if "league" not in params and "id" not in params:
            return None  # Need at least league or team_id
    
    # Check if this is for NFL fixtures - if so, use local endpoint instead of OpticOdds proxy
    is_nfl_fixtures = (
        tool_name == "fetch_upcoming_games" and 
        ("league" in params and str(params["league"]).lower() == "nfl") or
        ("league" in tool_args and str(tool_args.get("league", "")).lower() == "nfl") or
        ("league_id" in tool_args and str(tool_args.get("league_id", "")).lower() in ["nfl", "367"])
    )
    
    # Check if this is for NFL odds - if so, use local endpoint instead of OpticOdds proxy
    # For NFL, we can detect by checking if fixture_id exists and is NFL, or if player_id is provided and league is NFL
    is_nfl_odds = False
    if tool_name == "fetch_live_odds" or tool_name == "fetch_player_props":
        # Check if fixture_id is provided and if it's an NFL fixture
        fixture_ids_to_check = []
        if "fixture_id" in params:
            if isinstance(params["fixture_id"], list):
                fixture_ids_to_check = params["fixture_id"]
            else:
                fixture_ids_to_check = [params["fixture_id"]]
        elif "fixture_id" in tool_args:
            fixture_id = tool_args["fixture_id"]
            if isinstance(fixture_id, str) and ',' in fixture_id:
                fixture_ids_to_check = [fid.strip() for fid in fixture_id.split(',') if fid.strip()]
            else:
                fixture_ids_to_check = [str(fixture_id)]
        
        # If we have fixture_ids, check if they're NFL fixtures
        if fixture_ids_to_check:
            try:
                from app.core.database import SessionLocal
                from app.models.nfl_fixture import NFLFixture
                db = SessionLocal()
                try:
                    nfl_fixture = db.query(NFLFixture).filter(NFLFixture.id.in_(fixture_ids_to_check[:1])).first()
                    if nfl_fixture:
                        is_nfl_odds = True
                finally:
                    db.close()
            except Exception:
                # If check fails, assume not NFL (fallback to API)
                pass
        # If no fixture_id but player_id is provided and it's fetch_player_props, we can't easily check
        # In this case, we'll let it go to the API (or we could check league parameter if provided)
        # For now, if fixture_id is not provided, we won't use the database
    
    # Build the proxy URL instead of direct OpticOdds URL
    # This allows the frontend to call through the backend to avoid CORS issues
    # For NFL fixtures, use local endpoint instead
    try:
        from app.core.config import settings
        
        if is_nfl_fixtures:
            # Use local NFL fixtures endpoint
            # Format: /api/v1/nfl/fixtures?params...
            proxy_params = {}
            for key, value in params.items():
                if isinstance(value, list):
                    proxy_params[key] = value
                else:
                    proxy_params[key] = value
            
            # Build local endpoint URL
            proxy_url = f"{settings.API_V1_STR}/nfl/fixtures"
        elif is_nfl_odds:
            # Use local NFL odds endpoint
            # Format: /api/v1/nfl/odds?params...
            proxy_params = {}
            # Map parameters to our endpoint format
            if "fixture_id" in params:
                if isinstance(params["fixture_id"], list):
                    proxy_params["fixture_id"] = params["fixture_id"]
                else:
                    proxy_params["fixture_id"] = [params["fixture_id"]]
            if "sportsbook" in params:
                # Convert to proper format (capitalize first letter)
                sportsbook_list = params["sportsbook"] if isinstance(params["sportsbook"], list) else [params["sportsbook"]]
                # Map lowercase to proper case (e.g., "draftkings" -> "DraftKings")
                sportsbook_map = {
                    "draftkings": "DraftKings",
                    "fanduel": "FanDuel",
                    "betmgm": "BetMGM",
                    "caesars": "Caesars",
                    "betrivers": "BetRivers"
                }
                resolved_sportsbooks = [sportsbook_map.get(sb.lower(), sb.title()) for sb in sportsbook_list]
                if len(resolved_sportsbooks) == 1:
                    proxy_params["sportsbook"] = resolved_sportsbooks[0]
            if "market" in params:
                market_list = params["market"] if isinstance(params["market"], list) else [params["market"]]
                if len(market_list) == 1:
                    proxy_params["market"] = market_list[0]
            if "player_id" in params:
                # Support multiple player_ids
                if isinstance(params["player_id"], list):
                    proxy_params["player_id"] = params["player_id"]
                else:
                    proxy_params["player_id"] = [params["player_id"]]
            if "team_id" in params:
                proxy_params["team_id"] = params["team_id"]
            
            # Always group by fixture for OpticOdds API format
            proxy_params["group_by_fixture"] = "true"
            
            # Build local endpoint URL
            proxy_url = f"{settings.API_V1_STR}/nfl/odds"
        else:
            # Build query parameters for the proxy endpoint
            # We'll pass all params except the API key (proxy will add it)
            proxy_params = {}
            for key, value in params.items():
                if key != "key":  # Don't include API key in proxy URL
                    if isinstance(value, list):
                        # For lists, we'll pass them as multiple query params
                        proxy_params[key] = value
                    else:
                        proxy_params[key] = value
            
            # Build the proxy endpoint URL
            # Format: /api/v1/opticodds/proxy/{endpoint}?params...
            # Remove leading slash from endpoint if present
            endpoint_clean = endpoint.lstrip("/")
            
            # Build proxy URL with query parameters
            proxy_url = f"{settings.API_V1_STR}/opticodds/proxy/{endpoint_clean}"
        
        # Build query string from params
        if proxy_params:
            from urllib.parse import urlencode
            query_parts = []
            for key, value in proxy_params.items():
                if isinstance(value, list):
                    # Handle list parameters (multiple values for same key)
                    for v in value:
                        query_parts.append((key, str(v)))
                else:
                    query_parts.append((key, str(value)))
            
            if query_parts:
                query_string = urlencode(query_parts)
                proxy_url = f"{proxy_url}?{query_string}"
        
        return proxy_url
    except Exception as e:
        # If URL building fails, return None
        return None

