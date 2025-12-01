"""
Helper functions to query NFL odds from the database.
Used by tools to fetch odds data from local database instead of OpticOdds API.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.database import SessionLocal
from app.models.nfl_odds import NFLOdds
from app.models.nfl_fixture import NFLFixture

logger = logging.getLogger(__name__)


def query_odds_from_db(
    fixture_id: Optional[List[str]] = None,
    sportsbook: Optional[str] = None,
    market_id: Optional[str] = None,
    market: Optional[str] = None,
    market_category: Optional[str] = None,
    player_id: Optional[str] = None,
    team_id: Optional[str] = None,
    selection: Optional[str] = None,
    normalized_selection: Optional[str] = None,
    is_main: Optional[bool] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    points_min: Optional[float] = None,
    points_max: Optional[float] = None,
    limit: int = 1000,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Query odds from the database with various filters.
    
    Returns data in OpticOdds API format (grouped by fixture).
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
        if market_category:
            query = query.filter(NFLOdds.market_category == market_category.lower())
        if player_id:
            query = query.filter(NFLOdds.player_id == player_id)
        if team_id:
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
        
        # Group by fixture to match OpticOdds API format
        fixtures_dict: Dict[str, Dict[str, Any]] = {}
        
        for odds_entry in odds_entries:
            fixture_id_str = odds_entry.fixture_id
            
            if fixture_id_str not in fixtures_dict:
                # Get fixture data
                fixture = db.query(NFLFixture).filter(NFLFixture.id == fixture_id_str).first()
                if fixture:
                    fixture_dict = fixture.to_dict()
                    fixture_dict["odds"] = []
                    fixtures_dict[fixture_id_str] = fixture_dict
                else:
                    # Create minimal fixture structure if not found
                    fixtures_dict[fixture_id_str] = {
                        "id": fixture_id_str,
                        "odds": []
                    }
            
            # Add odds entry
            odds_dict = odds_entry.to_dict()
            if odds_dict:
                fixtures_dict[fixture_id_str]["odds"].append(odds_dict)
        
        # Convert to list
        fixture_data = list(fixtures_dict.values())
        
        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        
        return {
            "data": fixture_data,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "total_pages": total_pages
        }
        
    except Exception as e:
        logger.error(f"Error querying odds from database: {e}", exc_info=True)
        raise
    finally:
        db.close()

