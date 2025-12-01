"""
NFL Odds API endpoints.
Provides endpoints for fetching NFL odds stored in the database.
Returns data in the same format as OpticOdds API.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.core.database import SessionLocal
from app.models.nfl_odds import NFLOdds
from app.models.nfl_fixture import NFLFixture

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/nfl/odds",
    summary="Get NFL Odds",
    description="""
    Get NFL odds from the database in the same format as OpticOdds API.
    
    This endpoint returns odds that are stored locally, allowing fast queries
    with various filters. The response format matches the OpticOdds API structure.
    
    **Query Parameters:**
    - `fixture_id`: Filter by specific fixture ID (can specify multiple)
    - `sportsbook`: Filter by sportsbook name (e.g., BetMGM, FanDuel)
    - `market_id`: Filter by market ID (e.g., moneyline, point_spread, total_points)
    - `market`: Filter by market name (e.g., Moneyline, Point Spread)
    - `market_category`: Filter by market category: 'moneyline', 'spread', 'total', 'team_total', 'player_prop', 'other'
    - `market_type`: Alias for market_category (same functionality)
    - `player_id`: Filter by player ID
    - `team_id`: Filter by team ID
    - `selection`: Filter by selection name (partial match)
    - `normalized_selection`: Filter by normalized selection name
    - `is_main`: Filter by whether this is the main line (true/false)
    - `price_min`: Filter by minimum price (e.g., -200)
    - `price_max`: Filter by maximum price (e.g., 200)
    - `points_min`: Filter by minimum points/spread value
    - `points_max`: Filter by maximum points/spread value
    - `limit`: Maximum number of results to return (default: 1000)
    - `offset`: Number of results to skip (default: 0)
    - `group_by_fixture`: Group results by fixture (default: false)
    
    **Response Format:**
    The response matches the OpticOdds API format when `group_by_fixture=true`:
    ```json
    {
      "data": [
        {
          "id": "202512029BE1BA5B",
          "odds": [
            {
              "id": "37240-37430-25-48:betmgm:moneyline:new_england_patriots",
              "sportsbook": "BetMGM",
              "market": "Moneyline",
              ...
            }
          ]
        }
      ],
      "page": 1,
      "total_pages": 1
    }
    ```
    
    When `group_by_fixture=false`, returns flat list of odds entries.
    """,
    tags=["nfl-odds"]
)
async def get_nfl_odds(
    fixture_id: Optional[List[str]] = Query(None, description="Filter by fixture ID (can specify multiple)"),
    sportsbook: Optional[str] = Query(None, description="Filter by sportsbook name"),
    market_id: Optional[str] = Query(None, description="Filter by market ID (e.g., moneyline, point_spread, total_points)"),
    market: Optional[str] = Query(None, description="Filter by market name (e.g., Moneyline, Point Spread)"),
    market_category: Optional[List[str]] = Query(None, description="Filter by market category (can specify multiple with OR logic): moneyline, spread, total, team_total, player_prop, other"),
    market_type: Optional[List[str]] = Query(None, description="Alias for market_category (same functionality, can specify multiple)"),
    player_id: Optional[List[str]] = Query(None, description="Filter by player ID (can specify multiple)"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    selection: Optional[str] = Query(None, description="Filter by selection name (partial match)"),
    normalized_selection: Optional[str] = Query(None, description="Filter by normalized selection name"),
    is_main: Optional[bool] = Query(None, description="Filter by whether this is the main line"),
    price_min: Optional[int] = Query(None, description="Filter by minimum price"),
    price_max: Optional[int] = Query(None, description="Filter by maximum price"),
    points_min: Optional[float] = Query(None, description="Filter by minimum points/spread value"),
    points_max: Optional[float] = Query(None, description="Filter by maximum points/spread value"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    group_by_fixture: bool = Query(False, description="Group results by fixture (matches OpticOdds API format)")
):
    """
    Get NFL odds from database with various filters.
    
    Returns odds in the same format as OpticOdds API when group_by_fixture=true.
    """
    db = SessionLocal()
    try:
        # Build query
        query = db.query(NFLOdds)
        
        # Apply filters
        if fixture_id:
            if isinstance(fixture_id, list):
                query = query.filter(NFLOdds.fixture_id.in_(fixture_id))
            else:
                query = query.filter(NFLOdds.fixture_id == fixture_id)
        if sportsbook:
            query = query.filter(NFLOdds.sportsbook == sportsbook)
        if market_id:
            query = query.filter(NFLOdds.market_id == market_id)
        if market:
            query = query.filter(NFLOdds.market.ilike(f"%{market}%"))
        # Handle market_category or market_type (they're the same)
        # Support multiple categories with OR logic
        market_cat = market_category or market_type
        if market_cat:
            if isinstance(market_cat, list):
                # Multiple categories - use OR logic
                from sqlalchemy import or_
                market_cat_lower = [cat.lower() if isinstance(cat, str) else str(cat).lower() for cat in market_cat]
                query = query.filter(or_(*[NFLOdds.market_category == cat for cat in market_cat_lower]))
            else:
                query = query.filter(NFLOdds.market_category == market_cat.lower())
        
        # Handle player_id filter - need special logic for mixed queries
        # If we have both market_category (with moneyline) and player_id, we need:
        # (moneyline entries with NULL player_id) OR (player_prop entries with matching player_id)
        if player_id:
            from sqlalchemy import or_
            player_ids_list = player_id if isinstance(player_id, list) else [player_id]
            
            # Check if we're querying for moneyline (which has NULL player_id)
            has_moneyline = False
            if market_cat:
                market_cats = market_cat if isinstance(market_cat, list) else [market_cat]
                has_moneyline = any(cat.lower() == "moneyline" for cat in market_cats)
            
            if has_moneyline and isinstance(market_cat, list) and len(market_cat) > 1:
                # Mixed query: moneyline (NULL player_id) OR player_prop (matching player_id)
                query = query.filter(
                    or_(
                        NFLOdds.player_id.is_(None),  # Moneyline entries
                        NFLOdds.player_id.in_(player_ids_list)  # Player prop entries
                    )
                )
            else:
                # Only player props or single category - filter by player_id normally
                query = query.filter(NFLOdds.player_id.in_(player_ids_list))
        if team_id:
            # Check if team_id looks like a team name (not a UUID/hex ID)
            # Team IDs from OpticOdds are typically hex strings like "ACC49FC634EE" (12 chars, all hex)
            # Team names are typically lowercase strings like "giants", "lions", etc.
            original_team_id = team_id
            is_team_name = len(team_id) < 20 and not all(c in '0123456789ABCDEFabcdef' for c in team_id.replace('-', '').replace('_', ''))
            
            if is_team_name:
                # Look up team ID from NFL fixtures by team name
                from sqlalchemy import or_
                team_name_lower = team_id.lower()
                resolved_team_id = None
                
                # Try to find team ID by searching fixtures for matching team names
                team_fixtures = db.query(NFLFixture).filter(
                    or_(
                        NFLFixture.home_team_display.ilike(f"%{team_id}%"),
                        NFLFixture.away_team_display.ilike(f"%{team_id}%")
                    )
                ).all()
                
                if team_fixtures:
                    # Extract team ID from first fixture's fixture_data JSONB
                    fixture_dict = team_fixtures[0].to_dict()
                    if fixture_dict:
                        # Check home_competitors
                        home_competitors = fixture_dict.get("home_competitors", [])
                        away_competitors = fixture_dict.get("away_competitors", [])
                        
                        # Check if team name matches home team
                        for competitor in home_competitors:
                            if isinstance(competitor, dict):
                                comp_name = competitor.get("name", "").lower()
                                if team_name_lower in comp_name or comp_name in team_name_lower:
                                    resolved_team_id = competitor.get("id")
                                    break
                        
                        # If not found in home, check away
                        if not resolved_team_id:
                            for competitor in away_competitors:
                                if isinstance(competitor, dict):
                                    comp_name = competitor.get("name", "").lower()
                                    if team_name_lower in comp_name or comp_name in team_name_lower:
                                        resolved_team_id = competitor.get("id")
                                        break
                
                if resolved_team_id:
                    # Use the resolved team_id
                    query = query.filter(NFLOdds.team_id == resolved_team_id)
                elif team_fixtures:
                    # Fallback: If we found fixtures but couldn't extract team_id, query by fixture_ids
                    # This will get all odds for games involving this team
                    fixture_ids = [f.id for f in team_fixtures]
                    query = query.filter(NFLOdds.fixture_id.in_(fixture_ids))
                else:
                    # Last resort: Search by selection name in odds table (team name might be in selection field)
                    query = query.filter(NFLOdds.selection.ilike(f"%{original_team_id}%"))
            else:
                # It's already a team ID, use it directly
                query = query.filter(NFLOdds.team_id == team_id)
        if selection:
            query = query.filter(NFLOdds.selection.ilike(f"%{selection}%"))
        if normalized_selection:
            query = query.filter(NFLOdds.normalized_selection == normalized_selection)
        if is_main is not None:
            query = query.filter(NFLOdds.is_main == is_main)
        if price_min is not None:
            query = query.filter(NFLOdds.price >= price_min)
        if price_max is not None:
            query = query.filter(NFLOdds.price <= price_max)
        if points_min is not None:
            query = query.filter(NFLOdds.points >= points_min)
        if points_max is not None:
            query = query.filter(NFLOdds.points <= points_max)
        
        # Order by fixture_id, then by sportsbook, then by market_id
        query = query.order_by(NFLOdds.fixture_id.asc(), NFLOdds.sportsbook.asc(), NFLOdds.market_id.asc())
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        odds_entries = query.offset(offset).limit(limit).all()
        
        if group_by_fixture:
            # Group by fixture to match OpticOdds API format
            fixtures_dict: Dict[str, Dict[str, Any]] = {}
            
            for odds_entry in odds_entries:
                fixture_id = odds_entry.fixture_id
                
                if fixture_id not in fixtures_dict:
                    # Get fixture data
                    fixture = db.query(NFLFixture).filter(NFLFixture.id == fixture_id).first()
                    if fixture:
                        fixture_dict = fixture.to_dict()
                        fixture_dict["odds"] = []
                        fixtures_dict[fixture_id] = fixture_dict
                    else:
                        # Create minimal fixture structure if not found
                        fixtures_dict[fixture_id] = {
                            "id": fixture_id,
                            "odds": []
                        }
                
                # Add odds entry
                odds_dict = odds_entry.to_dict()
                if odds_dict:
                    fixtures_dict[fixture_id]["odds"].append(odds_dict)
            
            # Convert to list
            fixture_data = list(fixtures_dict.values())
        else:
            # Return flat list of odds entries
            fixture_data = []
            for odds_entry in odds_entries:
                odds_dict = odds_entry.to_dict()
                if odds_dict:
                    fixture_data.append(odds_dict)
        
        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        
        return {
            "data": fixture_data,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "total_pages": total_pages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching NFL odds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching odds: {str(e)}")
    finally:
        db.close()


@router.get(
    "/nfl/odds/fixture/{fixture_id}",
    summary="Get NFL Odds for Fixture",
    description="""
    Get all odds for a specific NFL fixture.
    
    Returns odds in the same format as OpticOdds API (grouped by fixture).
    """,
    tags=["nfl-odds"]
)
async def get_nfl_odds_for_fixture(
    fixture_id: str,
    sportsbook: Optional[str] = Query(None, description="Filter by sportsbook name"),
    market_id: Optional[str] = Query(None, description="Filter by market ID")
):
    """
    Get all odds for a specific NFL fixture.
    """
    db = SessionLocal()
    try:
        # Get fixture data
        fixture = db.query(NFLFixture).filter(NFLFixture.id == fixture_id).first()
        
        if not fixture:
            raise HTTPException(status_code=404, detail=f"Fixture with ID {fixture_id} not found")
        
        # Get odds for this fixture
        query = db.query(NFLOdds).filter(NFLOdds.fixture_id == fixture_id)
        
        if sportsbook:
            query = query.filter(NFLOdds.sportsbook == sportsbook)
        if market_id:
            query = query.filter(NFLOdds.market_id == market_id)
        
        # Order by sportsbook, then by market_id
        query = query.order_by(NFLOdds.sportsbook.asc(), NFLOdds.market_id.asc())
        
        odds_entries = query.all()
        
        # Build response in OpticOdds API format
        fixture_dict = fixture.to_dict()
        fixture_dict["odds"] = []
        
        for odds_entry in odds_entries:
            odds_dict = odds_entry.to_dict()
            if odds_dict:
                fixture_dict["odds"].append(odds_dict)
        
        return {
            "data": [fixture_dict],
            "page": 1,
            "total_pages": 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching NFL odds for fixture {fixture_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching odds: {str(e)}")
    finally:
        db.close()

