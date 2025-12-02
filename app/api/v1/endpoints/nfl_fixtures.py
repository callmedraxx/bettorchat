"""
NFL Fixtures API endpoints.
Provides endpoints for fetching NFL fixtures stored in the database.
Returns data in the same format as OpticOdds API.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.core.database import SessionLocal
from app.core.timezone_utils import convert_dict_timestamps_to_est, convert_list_timestamps_to_est
from app.models.nfl_fixture import NFLFixture

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/nfl/fixtures",
    summary="Get NFL Fixtures",
    description="""
    Get NFL fixtures from the database in the same format as OpticOdds API.
    
    This endpoint returns fixtures that are stored locally, allowing fast queries
    with various filters. The response format matches the OpticOdds API structure.
    
    **Query Parameters:**
    - `id`: Filter by specific fixture ID
    - `game_id`: Filter by game ID
    - `home_team`: Filter by home team name (partial match)
    - `away_team`: Filter by away team name (partial match)
    - `status`: Filter by game status (unplayed, live, finished, etc.)
    - `season_year`: Filter by season year
    - `season_week`: Filter by season week
    - `season_type`: Filter by season type (Regular Season, Playoffs, etc.)
    - `has_odds`: Filter by whether odds are available (true/false)
    - `is_live`: Filter by whether game is live (true/false)
    - `start_date_from`: Filter by start date (ISO format, inclusive)
    - `start_date_to`: Filter by start date (ISO format, inclusive)
    - `limit`: Maximum number of results to return (default: 1000)
    - `offset`: Number of results to skip (default: 0)
    
    **Response Format:**
    The response matches the OpticOdds API format:
    ```json
    {
      "data": [
        {
          "id": "202512029BE1BA5B",
          "numerical_id": 258752,
          "game_id": "37240-37430-25-48",
          "start_date": "2025-12-02T01:15:00Z",
          "home_competitors": [...],
          "away_competitors": [...],
          ...
        }
      ],
      "page": 1,
      "total_pages": 1
    }
    ```
    """,
    tags=["nfl-fixtures"]
)
async def get_nfl_fixtures(
    id: Optional[str] = Query(None, description="Filter by fixture ID"),
    game_id: Optional[str] = Query(None, description="Filter by game ID"),
    home_team: Optional[str] = Query(None, description="Filter by home team name (partial match)"),
    away_team: Optional[str] = Query(None, description="Filter by away team name (partial match)"),
    status: Optional[str] = Query(None, description="Filter by game status"),
    season_year: Optional[str] = Query(None, description="Filter by season year"),
    season_week: Optional[str] = Query(None, description="Filter by season week"),
    season_type: Optional[str] = Query(None, description="Filter by season type"),
    has_odds: Optional[bool] = Query(None, description="Filter by whether odds are available"),
    is_live: Optional[bool] = Query(None, description="Filter by whether game is live"),
    start_date_from: Optional[str] = Query(None, description="Filter by start date from (ISO format)"),
    start_date_to: Optional[str] = Query(None, description="Filter by start date to (ISO format)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    Get NFL fixtures from database with various filters.
    
    Returns fixtures in the same format as OpticOdds API.
    """
    db = SessionLocal()
    try:
        # Build query
        query = db.query(NFLFixture)
        
        # Apply filters
        if id:
            query = query.filter(NFLFixture.id == id)
        if game_id:
            query = query.filter(NFLFixture.game_id == game_id)
        if home_team:
            query = query.filter(NFLFixture.home_team_display.ilike(f"%{home_team}%"))
        if away_team:
            query = query.filter(NFLFixture.away_team_display.ilike(f"%{away_team}%"))
        if status:
            query = query.filter(NFLFixture.status == status)
        if season_year:
            query = query.filter(NFLFixture.season_year == season_year)
        if season_week:
            query = query.filter(NFLFixture.season_week == season_week)
        if season_type:
            query = query.filter(NFLFixture.season_type == season_type)
        if has_odds is not None:
            query = query.filter(NFLFixture.has_odds == has_odds)
        if is_live is not None:
            query = query.filter(NFLFixture.is_live == is_live)
        if start_date_from:
            try:
                from_date = datetime.fromisoformat(start_date_from.replace("Z", "+00:00"))
                query = query.filter(NFLFixture.start_date >= from_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date_from format. Use ISO format.")
        if start_date_to:
            try:
                to_date = datetime.fromisoformat(start_date_to.replace("Z", "+00:00"))
                query = query.filter(NFLFixture.start_date <= to_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date_to format. Use ISO format.")
        
        # Order by start_date
        query = query.order_by(NFLFixture.start_date.asc())
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        fixtures = query.offset(offset).limit(limit).all()
        
        # Convert to OpticOdds API format
        fixture_data = []
        for fixture in fixtures:
            fixture_dict = fixture.to_dict()
            if fixture_dict:
                # Convert timestamps to EST
                fixture_dict = convert_dict_timestamps_to_est(fixture_dict)
                fixture_data.append(fixture_dict)
        
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
        logger.error(f"Error fetching NFL fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching fixtures: {str(e)}")
    finally:
        db.close()


@router.get(
    "/nfl/fixtures/{fixture_id}",
    summary="Get Single NFL Fixture",
    description="""
    Get a single NFL fixture by ID.
    
    Returns the fixture in the same format as OpticOdds API.
    """,
    tags=["nfl-fixtures"]
)
async def get_nfl_fixture(
    fixture_id: str
):
    """
    Get a single NFL fixture by ID.
    """
    db = SessionLocal()
    try:
        fixture = db.query(NFLFixture).filter(NFLFixture.id == fixture_id).first()
        
        if not fixture:
            raise HTTPException(status_code=404, detail=f"Fixture with ID {fixture_id} not found")
        
        fixture_dict = fixture.to_dict()
        if not fixture_dict:
            raise HTTPException(status_code=500, detail="Error converting fixture to dict")
        
        # Convert timestamps to EST
        fixture_dict = convert_dict_timestamps_to_est(fixture_dict)
        
        return {
            "data": [fixture_dict],
            "page": 1,
            "total_pages": 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching NFL fixture {fixture_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching fixture: {str(e)}")
    finally:
        db.close()

