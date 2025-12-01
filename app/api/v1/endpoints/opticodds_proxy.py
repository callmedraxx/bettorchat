"""
Proxy endpoint for OpticOdds API to avoid CORS issues.
Allows frontend to call OpticOdds API through the backend.
"""
import logging
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional, List
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/opticodds/proxy")
async def proxy_opticodds(
    request: Request,
    endpoint: str = Query(..., description="OpticOdds API endpoint (e.g., 'fixtures', 'fixtures/odds')"),
    # Common query parameters
    league: Optional[str] = None,
    sport: Optional[str] = None,
    fixture_id: Optional[List[str]] = Query(None, description="Fixture ID(s) - can be multiple"),
    sportsbook: Optional[List[str]] = Query(None, description="Sportsbook(s) - can be multiple"),
    market: Optional[List[str]] = Query(None, description="Market(s) - can be multiple"),
    player_id: Optional[str] = None,
    team_id: Optional[str] = None,
    start_date_after: Optional[str] = None,
    start_date_before: Optional[str] = None,
    # Allow any other query parameters
    **kwargs
):
    """
    Proxy endpoint for OpticOdds API requests.
    
    This endpoint forwards requests to OpticOdds API and returns the response,
    allowing the frontend to access OpticOdds data without CORS issues.
    
    Args:
        endpoint: OpticOdds API endpoint path (e.g., 'fixtures', 'fixtures/odds', 'sportsbooks/active')
        All other query parameters are forwarded to OpticOdds API
    
    Returns:
        JSON response from OpticOdds API
    """
    try:
        # Get API key from settings
        api_key = settings.OPTICODDS_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="OPTICODDS_API_KEY not configured")
        
        # Build base URL
        base_url = "https://api.opticodds.com/api/v3"
        
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        # Build query parameters from request
        params = {}
        
        # Add common parameters
        if league:
            params["league"] = league
        if sport:
            params["sport"] = sport
        if fixture_id:
            # Handle multiple fixture_ids (OpticOdds supports up to 5)
            if isinstance(fixture_id, list):
                params["fixture_id"] = fixture_id[:5]  # Limit to 5
            else:
                params["fixture_id"] = fixture_id
        if sportsbook:
            # Handle multiple sportsbooks (OpticOdds supports up to 5)
            if isinstance(sportsbook, list):
                params["sportsbook"] = [sb.lower() for sb in sportsbook[:5]]  # Normalize to lowercase
            else:
                params["sportsbook"] = sportsbook.lower()
        if market:
            # Handle multiple markets
            if isinstance(market, list):
                params["market"] = market
            else:
                params["market"] = market
        if player_id:
            params["player_id"] = player_id
        if team_id:
            params["team_id"] = team_id
        if start_date_after:
            params["start_date_after"] = start_date_after
        if start_date_before:
            params["start_date_before"] = start_date_before
        
        # Add any other query parameters from kwargs
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        # Add API key
        params["key"] = api_key
        
        # Make request to OpticOdds API
        url = f"{base_url}{endpoint}"
        
        logger.info(f"[opticodds_proxy] Proxying request to: {url} with params: {list(params.keys())}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            
            # Return the JSON response
            return JSONResponse(
                content=response.json(),
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"[opticodds_proxy] HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpticOdds API error: {e.response.text[:200]}"
        )
    except httpx.RequestError as e:
        logger.error(f"[opticodds_proxy] Request error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to OpticOdds API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[opticodds_proxy] Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/opticodds/proxy/{endpoint:path}")
async def proxy_opticodds_path(
    endpoint: str,
    request: Request
):
    """
    Proxy endpoint for OpticOdds API requests using full path.
    
    This endpoint accepts the full OpticOdds API path and forwards all query parameters.
    Example: /api/v1/opticodds/proxy/fixtures?league=nfl&start_date_after=2025-11-27T00:00:00Z
    
    Args:
        endpoint: Full OpticOdds API endpoint path (e.g., 'fixtures', 'fixtures/odds')
        All query parameters from the request are forwarded to OpticOdds API
    
    Returns:
        JSON response from OpticOdds API
    """
    try:
        # Get API key from settings
        api_key = settings.OPTICODDS_API_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="OPTICODDS_API_KEY not configured")
        
        # Build base URL
        base_url = "https://api.opticodds.com/api/v3"
        
        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        
        # Get all query parameters from the request
        # Handle multiple values for the same parameter (e.g., sportsbook=draftkings&sportsbook=fanduel)
        params = {}
        for key, value in request.query_params.multi_items():
            if key in params:
                # If key already exists, convert to list
                if not isinstance(params[key], list):
                    params[key] = [params[key]]
                params[key].append(value)
            else:
                params[key] = value
        
        # Convert single values to lists for parameters that support multiple values
        # This ensures httpx sends them as multiple query params
        # Note: fixture_id can be single or multiple, so we keep it as-is if it's a single value
        multi_value_params = ["sportsbook", "market"]
        for key in multi_value_params:
            if key in params and not isinstance(params[key], list):
                params[key] = [params[key]]
        
        # Normalize sportsbook values to lowercase (OpticOdds API requirement)
        if "sportsbook" in params:
            if isinstance(params["sportsbook"], list):
                params["sportsbook"] = [sb.lower() if isinstance(sb, str) else str(sb).lower() for sb in params["sportsbook"]]
            else:
                params["sportsbook"] = params["sportsbook"].lower() if isinstance(params["sportsbook"], str) else str(params["sportsbook"]).lower()
        
        # Handle market type filtering - some market names are not valid API market names
        # but represent market types that need to be filtered from the response
        # Examples: "Player Props" -> filter by market_type="player_props"
        # IMPORTANT: 
        # - Market names like "player_points", "player_receptions" are VALID market names and should be sent to the API
        # - Market type names like "player_total", "player_yes_no" are NOT valid market names and should be filtered
        # - Generic categories like "Player Props" should also be filtered
        from app.core.market_types import normalize_market_name, is_player_prop_market_type, get_market_type_by_name
        
        market_type_filters = {}  # Map of market_type name -> True
        has_specific_markets = False  # Track if we have specific market names to send
        if "market" in params:
            market_list = params["market"] if isinstance(params["market"], list) else [params["market"]]
            filtered_markets = []
            for m in market_list:
                m_str = str(m).strip()
                m_lower = m_str.lower()
                
                # Check if it's a generic category that needs filtering (not a specific market name)
                if m_lower in ["player props", "player_props", "player-props", "playerprops"]:
                    # Generic "Player Props" category - add all player prop market types to filter
                    from app.core.market_types import get_player_prop_market_types
                    player_prop_types = get_player_prop_market_types()
                    for pt in player_prop_types:
                        market_type_filters[pt.get("name")] = True
                    # Don't add to market parameter - we'll filter by market_type instead
                # Check if it's a market type name (not a market name)
                elif get_market_type_by_name(m_str) or is_player_prop_market_type(m_str):
                    # This is a market type name (like "player_total", "player_yes_no"), not a market name
                    # Market type names are not valid market names for the API
                    # Add to market_type_filters so we can filter the response
                    market_type_filters[m_str] = True
                    # Don't add to market parameter - we'll filter by market_type instead
                else:
                    # It's a specific market name (like "player_points", "moneyline", etc.)
                    # Send it to the API as-is - don't filter it
                    filtered_markets.append(m_str)
                    has_specific_markets = True
            
            # Update market parameter
            if filtered_markets:
                params["market"] = filtered_markets if len(filtered_markets) > 1 else filtered_markets[0]
            elif market_type_filters:
                # If only market type filters were requested (no specific market names),
                # remove market parameter entirely and filter by market_type in response
                params.pop("market", None)
        
        # Add API key (will override if 'key' is already in params)
        params["key"] = api_key
        
        # Make request to OpticOdds API
        url = f"{base_url}{endpoint}"
        
        # Log parameter details for debugging
        param_details = {k: (v if not isinstance(v, list) or len(v) <= 3 else f"[{len(v)} items]") for k, v in params.items() if k != "key"}
        logger.info(f"[opticodds_proxy] Proxying request to: {url} with params: {param_details}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            
            # Get the JSON response
            response_data = response.json()
            
            # Only apply market type filtering if we have market_type_filters AND no specific market names were sent
            # If specific market names were sent (like "player_points"), the API already filtered them,
            # so we don't need to filter the response again
            # Only filter when a generic category like "Player Props" was requested
            if market_type_filters and not has_specific_markets and isinstance(response_data, dict) and "data" in response_data:
                filtered_data = []
                for fixture in response_data.get("data", []):
                    if isinstance(fixture, dict):
                        # Check both "markets" and "odds" arrays (API might use either structure)
                        markets = fixture.get("markets", [])
                        odds = fixture.get("odds", [])
                        
                        # Helper function to check if a market/odds item matches any of the requested market types
                        def matches_market_type(item: dict) -> bool:
                            """Check if an item matches any of the requested market types."""
                            if not isinstance(item, dict):
                                return False
                            
                            # Check nested market.market_type or market.name
                            market_obj = item.get("market", {})
                            if isinstance(market_obj, dict):
                                market_type = market_obj.get("market_type")
                                market_name = market_obj.get("name", "")
                                
                                # Check by market_type (exact match)
                                if market_type and market_type in market_type_filters:
                                    return True
                                # Check by market name (exact match)
                                if market_name and market_name in market_type_filters:
                                    return True
                            
                            # Check direct market_type field (exact match)
                            direct_market_type = item.get("market_type")
                            if direct_market_type and direct_market_type in market_type_filters:
                                return True
                            
                            # Check market name field directly (exact match)
                            market_name = item.get("market", "")
                            if isinstance(market_name, str) and market_name in market_type_filters:
                                return True
                            
                            return False
                        
                        # Filter markets if present
                        filtered_markets_list = []
                        if isinstance(markets, list):
                            filtered_markets_list = [
                                market for market in markets
                                if matches_market_type(market)
                            ]
                        
                        # Filter odds if present
                        filtered_odds = []
                        if isinstance(odds, list):
                            filtered_odds = [
                                odds_item for odds_item in odds
                                if matches_market_type(odds_item)
                            ]
                        
                        # Create a copy of fixture with filtered markets/odds
                        filtered_fixture = fixture.copy()
                        if filtered_markets_list:
                            filtered_fixture["markets"] = filtered_markets_list
                        if filtered_odds:
                            filtered_fixture["odds"] = filtered_odds
                        
                        # Only include fixture if it has matching markets or odds
                        if filtered_markets_list or filtered_odds:
                            filtered_data.append(filtered_fixture)
                    else:
                        filtered_data.append(fixture)
                
                response_data["data"] = filtered_data
                filter_types_str = ", ".join(market_type_filters.keys())
                logger.info(f"[opticodds_proxy] Filtered response by market types ({filter_types_str}): {len(filtered_data)} fixtures with matching markets/odds")
            
            # Return the JSON response
            return JSONResponse(
                content=response_data,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"[opticodds_proxy] HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpticOdds API error: {e.response.text[:200]}"
        )
    except httpx.RequestError as e:
        logger.error(f"[opticodds_proxy] Request error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to OpticOdds API: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[opticodds_proxy] Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.options("/opticodds/proxy")
@router.options("/opticodds/proxy/{endpoint:path}")
async def proxy_opticodds_options():
    """Handle CORS preflight requests for /opticodds/proxy endpoint."""
    from fastapi import Response
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

