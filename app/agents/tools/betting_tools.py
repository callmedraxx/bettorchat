"""
MCP-compatible betting tools wrapping OpticOdds API.
"""
import json
import base64
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


def get_user_timezone(user_id: Optional[str] = None, timezone_override: Optional[str] = None) -> ZoneInfo:
    """Get user's timezone from cache/preferences, defaulting to EST/EDT.
    
    Args:
        user_id: Optional user ID to look up preferences
        timezone_override: Optional timezone string to use (e.g., "America/Los_Angeles")
    
    Returns:
        ZoneInfo object for the user's timezone
    """
    # Default to Eastern Time
    default_tz = ZoneInfo("America/New_York")
    
    # If timezone override provided, use it
    if timezone_override:
        try:
            return ZoneInfo(timezone_override)
        except Exception:
            return default_tz
    
    # Try to get from cache if user_id provided
    if user_id and user_id in _user_timezone_cache:
        try:
            return ZoneInfo(_user_timezone_cache[user_id])
        except Exception:
            return default_tz
    
    return default_tz


def set_user_timezone(user_id: str, timezone: str) -> bool:
    """Set user's timezone in cache.
    
    Args:
        user_id: User ID
        timezone: Timezone string (e.g., "America/Los_Angeles")
    
    Returns:
        True if successful
    """
    try:
        # Validate timezone
        ZoneInfo(timezone)
        _user_timezone_cache[user_id] = timezone
        return True
    except Exception:
        return False


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
def get_current_datetime(user_id: Optional[str] = None, timezone: Optional[str] = None) -> str:
    """Get the current date, time, timezone, and day of week in the user's timezone.
    
    This tool should be called whenever the user mentions dates like "today", "tomorrow", 
    "next week", or any relative date references. Always use this tool to get the current 
    date before interpreting date-related queries.
    
    The timezone is determined by:
    1. timezone parameter (if provided)
    2. User's saved timezone preference (if user_id provided and preference exists)
    3. Default to Eastern Time (EST/EDT) if no preference
    
    Args:
        user_id: Optional user ID to look up timezone preference
        timezone: Optional timezone string (e.g., "America/Los_Angeles", "America/New_York")
    
    Returns:
        Formatted string with current date, time, timezone, and day of week
    """
    # Get user's timezone (defaults to EST/EDT)
    tz = get_user_timezone(user_id, timezone)
    now = datetime.now(tz)
    
    # Get timezone name for display
    tz_name = str(tz).split("/")[-1].replace("_", " ")
    tz_abbr = now.strftime('%Z')
    
    # Format date and time information
    formatted = f"""Current Date and Time Information ({tz_abbr}):

Date: {now.strftime('%A, %B %d, %Y')}
Time: {now.strftime('%I:%M %p')} {tz_abbr}
Timezone: {tz_abbr} ({tz_name}) (UTC{now.strftime('%z')})
Day of Week: {now.strftime('%A')}
ISO Format: {now.isoformat()}

Use this information to interpret relative dates:
- "Today" = {now.strftime('%B %d, %Y')}
- "Tomorrow" = {(now + timedelta(days=1)).strftime('%B %d, %Y')}
- "This week" = Week of {now.strftime('%B %d, %Y')}

Note: Times are displayed in your local timezone ({tz_abbr}). If you'd like to change your timezone, use the detect_user_location tool or set it in your preferences.
"""
    
    return formatted


@tool
def detect_user_location(ip_address: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """Detect user's location and timezone from IP address or set location preference.
    
    This tool detects the user's location using IP geolocation and automatically sets
    their timezone preference. If IP address is not provided, it will use a free
    geolocation service to detect from the current request.
    
    Args:
        ip_address: Optional IP address to geolocate. If not provided, attempts to detect automatically.
        user_id: Optional user ID to save location/timezone preference
    
    Returns:
        Formatted string with detected location and timezone information
    """
    try:
        # Use a free IP geolocation service
        if ip_address:
            # Use ip-api.com (free, no API key required)
            geo_url = f"http://ip-api.com/json/{ip_address}"
        else:
            # Get location from current IP
            geo_url = "http://ip-api.com/json/"
        
        response = httpx.get(geo_url, timeout=5.0)
        response.raise_for_status()
        geo_data = response.json()
        
        if geo_data.get("status") == "fail":
            error_msg = geo_data.get("message", "Unknown error")
            return f"Error detecting location: {error_msg}. Defaulting to Eastern Time (EST/EDT)."
        
        # Extract location data
        city = geo_data.get("city", "Unknown")
        region = geo_data.get("regionName", geo_data.get("region", "Unknown"))
        country = geo_data.get("country", "Unknown")
        country_code = geo_data.get("countryCode", "")
        timezone_str = geo_data.get("timezone", "America/New_York")
        lat = geo_data.get("lat")
        lon = geo_data.get("lon")
        
        # Convert timezone string to ZoneInfo
        try:
            tz = ZoneInfo(timezone_str)
        except Exception:
            # Fallback to EST if timezone is invalid
            tz = ZoneInfo("America/New_York")
            timezone_str = "America/New_York"
        
        # Get current time in detected timezone
        now = datetime.now(tz)
        tz_abbr = now.strftime('%Z')
        
        location_info = {
            "city": city,
            "region": region,
            "country": country,
            "country_code": country_code,
            "timezone": timezone_str,
            "latitude": lat,
            "longitude": lon,
        }
        
        # Save timezone to cache if user_id provided
        if user_id:
            set_user_timezone(user_id, timezone_str)
        
        formatted = f"""Location Detected:

City: {city}
Region/State: {region}
Country: {country}
Timezone: {tz_abbr} ({timezone_str})
Current Time: {now.strftime('%I:%M %p %Z')} on {now.strftime('%B %d, %Y')}

Your timezone preference has been set to {tz_abbr}. All times will now be displayed in your local timezone.
"""
        
        # Add structured data for agent to save to preferences
        formatted += f"\n\n<!-- LOCATION_DATA_START -->\n{json.dumps(location_info, indent=2)}\n<!-- LOCATION_DATA_END -->"
        
        return formatted
        
    except Exception as e:
        return f"Error detecting location: {str(e)}. Defaulting to Eastern Time (EST/EDT). You can manually set your timezone preference."


@tool
def fetch_live_odds(
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,
    fixtures: Optional[str] = None,
    league_id: Optional[str] = None,
    sport_id: Optional[str] = None,
    sportsbook_ids: Optional[str] = None,
    market_types: Optional[str] = None,
) -> str:
    """Fetch live betting odds for fixtures using OpticOdds /fixtures/odds endpoint.
    
    IMPORTANT: The OpticOdds API requires at least 1 sportsbook to be specified (max 5).
    If sportsbook_ids is not provided, the tool will automatically fetch available sportsbooks 
    from the API and use the first 3-5 as defaults. This ensures valid sportsbook IDs/names 
    are used. Results are cached for 1 hour to avoid repeated API calls.
    
    Args:
        fixture_id: Specific fixture ID to get odds for (string ID)
        fixture: Full fixture object as JSON string (alternative to fixture_id). 
                 If provided, fixture_id will be extracted from it.
        fixtures: JSON string containing multiple full fixture objects (array).
                 If provided, odds will be fetched for all fixtures. Can be used for bet slip building.
        league_id: Filter by league ID. Can also be extracted from fixture object if provided.
        sport_id: Filter by sport ID (e.g., 'NBA' = 1). Used to filter available sportsbooks if sportsbook_ids not provided.
        sportsbook_ids: Comma-separated list of sportsbook IDs or names (REQUIRED by API, max 5).
                       If not provided, automatically fetches available sportsbooks from API.
                       Use fetch_available_sportsbooks to get valid sportsbook IDs manually.
        market_types: Comma-separated list of market types (e.g., 'moneyline,spread,total')
    
    Returns:
        Formatted string with odds from multiple sportsbooks
    """
    try:
        client = get_client()
        
        # Convert comma-separated market_types string to list if needed
        resolved_market_types = None
        if market_types:
            if isinstance(market_types, str) and ',' in market_types:
                # Split comma-separated string into list
                resolved_market_types = [mt.strip() for mt in market_types.split(',') if mt.strip()]
            elif isinstance(market_types, str):
                resolved_market_types = [market_types.strip()]
            else:
                resolved_market_types = market_types
        
        # Convert comma-separated sportsbook_ids string to list if needed
        # IMPORTANT: OpticOdds API requires at least 1 sportsbook (max 5) for /fixtures/odds endpoint
        resolved_sportsbook_ids = None
        if sportsbook_ids:
            if isinstance(sportsbook_ids, str) and ',' in sportsbook_ids:
                # Split comma-separated string into list
                resolved_sportsbook_ids = [sb.strip() for sb in sportsbook_ids.split(',') if sb.strip()]
            elif isinstance(sportsbook_ids, str):
                resolved_sportsbook_ids = [sportsbook_ids.strip()]
            else:
                resolved_sportsbook_ids = sportsbook_ids
        
        # Extract league_id early if we have fixture object (needed for sportsbook filtering)
        resolved_league_id = league_id
        if fixture:
            try:
                fixture_obj = json.loads(fixture) if isinstance(fixture, str) else fixture
                if isinstance(fixture_obj, dict):
                    league_info = fixture_obj.get("league") or fixture_obj.get("full_fixture", {}).get("league", {})
                    if isinstance(league_info, dict) and not resolved_league_id:
                        resolved_league_id = league_info.get("id") or league_info.get("numerical_id")
            except Exception:
                pass
        
        # If no sportsbook_ids provided, fetch available sportsbooks from API and use as defaults
        # This ensures we use valid sportsbook IDs/names that are actually available
        if not resolved_sportsbook_ids:
            try:
                # Fetch default sportsbooks (cached, with fallback)
                # Filter by sport_id if available for better results
                resolved_sportsbook_ids = get_default_sportsbooks(
                    sport_id=sport_id if sport_id else None,
                    league_id=resolved_league_id if resolved_league_id else None
                )
            except Exception:
                # Fallback to hardcoded defaults if fetching fails
                resolved_sportsbook_ids = ["DraftKings", "FanDuel", "BetMGM"]
        
        # Handle multiple fixtures (for bet slip building)
        if fixtures:
            fixture_ids = extract_fixture_ids_from_objects(fixtures)
            if fixture_ids:
                # Fetch odds for all fixtures and combine results
                all_results = []
                for fid in fixture_ids:
                    try:
                        result = client.get_fixture_odds(
                            fixture_id=fid,
                            sport_id=sport_id if sport_id else None,
                            league_id=league_id if league_id else None,
                            sportsbook=resolved_sportsbook_ids,
                            market_types=resolved_market_types,
                        )
                        if result and result.get("data"):
                            all_results.extend(result.get("data", []))
                    except Exception:
                        continue
                
                if all_results:
                    # Combine results
                    combined_result = {"data": all_results}
                    formatted = format_odds_response(combined_result)
                    return formatted
                else:
                    return "No odds data found for the provided fixtures"
        
        # Handle single fixture object or fixture_id
        resolved_fixture_id = None
        
        if fixture:
            fixture_obj = json.loads(fixture) if isinstance(fixture, str) else fixture
            if isinstance(fixture_obj, dict):
                # Extract fixture_id
                resolved_fixture_id = extract_fixture_id(fixture if isinstance(fixture, str) else json.dumps(fixture_obj))
                # Extract league_id if not provided (already done above, but ensure it's set)
                if not resolved_league_id:
                    league_info = fixture_obj.get("league") or fixture_obj.get("full_fixture", {}).get("league", {})
                    if isinstance(league_info, dict):
                        resolved_league_id = league_info.get("id") or league_info.get("numerical_id")
        
        # Use provided fixture_id if fixture object not provided
        if not resolved_fixture_id:
            resolved_fixture_id = extract_fixture_id(fixture_id)
        
        # Convert to correct parameter format
        # Pass sport_id and league_id directly to the client method
        result = client.get_fixture_odds(
            fixture_id=resolved_fixture_id,
            sport_id=sport_id if sport_id else None,
            league_id=resolved_league_id if resolved_league_id else None,
            sportsbook=resolved_sportsbook_ids,
            market_types=resolved_market_types,
        )
        
        # Format response for frontend
        formatted = format_odds_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching live odds: {str(e)}"


@tool
def fetch_upcoming_games(
    sport: Optional[str] = None,
    sport_id: Optional[str] = None,
    league: Optional[str] = None,
    league_id: Optional[str] = None,
    fixture_id: Optional[str] = None,
    team_id: Optional[str] = None,
    start_date: Optional[str] = None,
    start_date_after: Optional[str] = None,
    start_date_before: Optional[str] = None,
    paginate: bool = True,
) -> str:
    """Fetch upcoming game schedules/fixtures using OpticOdds /fixtures endpoint.
    
    This is the PRIMARY tool for getting game schedules. Use this before falling back to web search.
    
    IMPORTANT: Use as many filters as possible to narrow down results:
    - Always specify sport/league when possible
    - Use date filters (start_date_after) to get only upcoming games
    - Use team_id to filter by specific team
    - Use sport_id/league_id for more precise filtering (preferred over names)
    
    Args:
        sport: Sport name (e.g., 'basketball') - use if sport_id not available
        sport_id: Sport ID (e.g., '1' for basketball) - preferred over sport name for precision
        league: League name (e.g., 'nba', 'nfl', 'mlb') - use if league_id not available
        league_id: League ID - preferred over league name for precision
        fixture_id: Optional specific fixture ID (if provided, other filters are ignored)
        team_id: Optional team ID to filter games for a specific team
        start_date: Specific date (YYYY-MM-DD format). Cannot be used with start_date_after/start_date_before
        start_date_after: Get fixtures after this date (YYYY-MM-DD format). Defaults to today if no date params provided.
        start_date_before: Get fixtures before this date (YYYY-MM-DD format)
        paginate: Whether to fetch all pages of results (default: True to get complete data)
    
    Returns:
        Formatted string with upcoming game schedules including teams, dates, times, and fixture IDs
    """
    try:
        client = get_client()
        
        # Build parameters dict - use all available filters to narrow results
        params = {}
        
        # If fixture_id is provided, use only that (most specific filter)
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        else:
            # Use sport_id if provided (more precise), otherwise fall back to sport name
            if sport_id:
                params["sport_id"] = str(sport_id)
            elif sport:
                params["sport"] = str(sport)
            
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
            if start_date:
                # Specific date - most precise filter
                params["start_date"] = str(start_date)
            elif start_date_after or start_date_before:
                # Date range filters
                if start_date_after:
                    params["start_date_after"] = str(start_date_after)
                if start_date_before:
                    params["start_date_before"] = str(start_date_before)
            else:
                # Default: Only get upcoming games (from today onwards)
                # This prevents getting games from 3 days ago (API default)
                today = datetime.now(get_user_timezone()).date()
                params["start_date_after"] = today.isoformat()
        
        # Get fixtures from OpticOdds API with all filters applied
        result = client.get_fixtures(
            paginate=paginate,
            **params
        )
        
        # Format response
        formatted = format_fixtures_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching upcoming games: {str(e)}"


@tool
def emit_fixture_objects(
    fixtures: Optional[str] = None,
    fixture_ids: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Emit full fixture JSON objects to frontend via SSE stream.
    
    This tool filters and emits complete fixture objects that were already retrieved
    from previous tool calls (like fetch_upcoming_games). It pushes the filtered JSON data
    to an SSE endpoint which streams it to the frontend.
    
    IMPORTANT: Extract fixture objects from previous tool responses (e.g., from the 
    <!-- FIXTURES_DATA_START --> block in fetch_upcoming_games response) and pass them here.
    The tool will filter/validate the data and push it to the SSE stream.
    
    Args:
        fixtures: JSON string containing full fixture objects extracted from previous tool responses.
                 This should be the complete fixture objects from fetch_upcoming_games or other tools.
                 Can be a single object or array of objects.
                 Example: '[{"id": "20251127E5C64DE0", "numerical_id": 258739, ...}, {...}]'
        fixture_ids: Comma-separated string of fixture IDs. If provided, you must extract the 
                    corresponding fixture objects from previous tool responses and pass them 
                    in the fixtures parameter. This parameter is mainly for reference.
        session_id: Optional session identifier (user_id or thread_id). If not provided, uses "default".
                    Frontend should connect to /api/v1/fixtures/stream?session_id=<same_id> to receive data.
    
    Returns:
        Confirmation message indicating that fixture data has been pushed to the SSE stream.
        The frontend will receive the full JSON data via Server-Sent Events.
    
    Examples:
        - emit_fixture_objects(fixtures='[{{"id": "20251127E5C64DE0", ...}}]', session_id='user123')
        - Extract fixtures from fetch_upcoming_games response, then call emit_fixture_objects(fixtures=extracted_fixtures)
    """
    try:
        fixture_objects = []
        
        if not fixtures:
            if fixture_ids:
                return f"Error: When using fixture_ids parameter, you must extract the corresponding fixture objects from previous tool responses and pass them in the 'fixtures' parameter. The fixture_ids '{fixture_ids}' are for reference only - extract the full objects from fetch_upcoming_games response."
            return "Error: Must provide 'fixtures' parameter with full fixture objects extracted from previous tool responses."
        
        # Parse fixtures JSON
        try:
            fixtures_data = json.loads(fixtures) if isinstance(fixtures, str) else fixtures
            
            # Handle array of fixtures
            if isinstance(fixtures_data, list):
                for fixture_obj in fixtures_data:
                    if isinstance(fixture_obj, dict):
                        fixture_objects.append(fixture_obj)
            # Handle single fixture object
            elif isinstance(fixtures_data, dict):
                fixture_objects.append(fixtures_data)
            else:
                return f"Error: Invalid fixtures format. Expected JSON object or array of objects, got {type(fixtures_data)}"
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return f"Error parsing fixtures JSON: {str(e)}. Please provide valid JSON with full fixture objects from previous tool responses."
        
        if not fixture_objects:
            return "Error: No valid fixture objects found in the provided fixtures parameter."
        
        # Push filtered fixture data to SSE stream
        session = session_id or "default"
        success = fixture_stream_manager.push_fixtures_sync(session, fixture_objects)
        
        if not success:
            return f"Error: Failed to push fixture data to SSE stream. Data was filtered but could not be streamed."
        
        # Return confirmation message
        return (
            f"Successfully pushed {len(fixture_objects)} fixture object(s) to SSE stream.\n"
            f"Frontend connected to /api/v1/fixtures/stream?session_id={session} will receive the full JSON data.\n"
            f"The fixture data has been filtered and is ready for streaming."
        )
    except Exception as e:
        return f"Error emitting fixture objects: {str(e)}"


@tool
def fetch_player_props(
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,
    player_id: Optional[str] = None,
    league_id: Optional[str] = None,
) -> str:
    """Fetch player proposition odds using OpticOdds /fixtures/player-results and player markets.
    
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
        client = get_client()
        
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
def fetch_available_markets() -> str:
    """Fetch available market types using OpticOdds /markets/active endpoint.
    
    This tool returns market types that are currently available.
    Use this to discover valid market_types parameter values (e.g., 'moneyline', 'spread', 'total').
    
    Returns:
        Formatted string with markets information including IDs, names, and market types
    """
    try:
        client = get_client()
        result = client.get_active_markets()
        formatted = format_markets_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching available markets: {str(e)}"


@tool
def fetch_available_sportsbooks(sport: Optional[str] = None) -> str:
    """Fetch available sportsbooks using OpticOdds /sportsbooks/active endpoint.
    
    This tool returns sportsbooks that are currently active.
    Use this to discover valid sportsbook IDs and names for use in other endpoints.
    
    Args:
        sport: Optional sport name or ID to filter sportsbooks by sport
    
    Returns:
        Formatted string with sportsbooks information including IDs and names
    """
    try:
        client = get_client()
        if sport:
            result = client.get_active_sportsbooks(sport=sport)
        else:
            result = client.get_active_sportsbooks()
        formatted = format_sportsbooks_response(result)
        return formatted
    except Exception as e:
        return f"Error fetching available sportsbooks: {str(e)}"


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
    
    formatted_lines.append("Available Market Types:\n")
    
    structured_markets = []
    
    for market in markets:
        if not market:
            continue
        
        market_id = market.get("id")
        market_name = market.get("name", "Unknown")
        market_type = market.get("market_type", "")
        market_slug = market.get("slug", "")
        
        formatted_lines.append(f"\n{market_name}")
        if market_type:
            formatted_lines.append(f"  Market Type: {market_type}")
        if market_id:
            formatted_lines.append(f"  Market ID: {market_id}")
        if market_slug:
            formatted_lines.append(f"  Slug: {market_slug}")
        
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


def format_sportsbooks_response(data: Dict[str, Any]) -> str:
    """Format sportsbooks response with structured data for frontend parsing."""
    if not data:
        return "No sportsbooks data available"
    
    formatted_lines = []
    sportsbooks = data.get("data", [])
    
    if not isinstance(sportsbooks, list):
        sportsbooks = [sportsbooks] if sportsbooks else []
    
    if not sportsbooks:
        return "No sportsbooks found"
    
    formatted_lines.append("Available Sportsbooks:\n")
    
    structured_sportsbooks = []
    
    for sportsbook in sportsbooks:
        if not sportsbook:
            continue
        
        sportsbook_id = sportsbook.get("id")
        sportsbook_name = sportsbook.get("name", "Unknown")
        sportsbook_slug = sportsbook.get("slug", "")
        
        formatted_lines.append(f"\n{sportsbook_name}")
        if sportsbook_id:
            formatted_lines.append(f"  Sportsbook ID: {sportsbook_id}")
        if sportsbook_slug:
            formatted_lines.append(f"  Slug: {sportsbook_slug}")
        
        structured_sportsbooks.append({
            "sportsbook_id": sportsbook_id,
            "sportsbook_name": sportsbook_name,
            "sportsbook_slug": sportsbook_slug,
        })
    
    # Add structured JSON block for frontend parsing
    if structured_sportsbooks:
        formatted_lines.append(f"\n\n<!-- SPORTSBOOKS_DATA_START -->\n{json.dumps({'sportsbooks': structured_sportsbooks}, indent=2)}\n<!-- SPORTSBOOKS_DATA_END -->")
    
    return "\n".join(formatted_lines) if formatted_lines else "No sportsbooks available"

