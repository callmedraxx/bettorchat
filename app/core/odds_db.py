"""
Database operations for storing and querying odds entries.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.core.database import SessionLocal
from app.models.odds_entry import OddsEntry
from app.core.config import settings

logger = logging.getLogger(__name__)


def save_odds_to_db(
    tool_call_id: str,
    session_id: str,
    fixture_id: str,
    odds_data: Dict[str, Any],
) -> int:
    """
    Save odds entries from API response to database.
    
    Args:
        tool_call_id: Tool call ID from the tool result
        session_id: Session identifier
        fixture_id: Fixture ID
        odds_data: Full fixture object with odds array from API response
        
    Returns:
        Number of odds entries saved
    """
    db = SessionLocal()
    saved_count = 0
    
    try:
        # Extract fixture details
        fixture_numerical_id = odds_data.get("numerical_id")
        odds_array = odds_data.get("odds", [])
        
        if not isinstance(odds_array, list):
            logger.warning(f"Odds array is not a list for fixture_id={fixture_id}")
            return 0
        
        # Delete existing odds entries for this fixture and tool_call_id to avoid duplicates
        db.query(OddsEntry).filter(
            OddsEntry.tool_call_id == tool_call_id,
            OddsEntry.fixture_id == fixture_id
        ).delete()
        
        # Insert odds entries
        for odds_entry in odds_array:
            if not isinstance(odds_entry, dict):
                continue
            
            try:
                # Extract fields
                odds_entry_id = odds_entry.get("id", "")
                sportsbook = odds_entry.get("sportsbook", "")
                market = odds_entry.get("market", "")
                market_id = odds_entry.get("market_id")
                selection = odds_entry.get("selection") or odds_entry.get("name", "")
                selection_name = odds_entry.get("name")
                normalized_selection = odds_entry.get("normalized_selection")
                price = odds_entry.get("price")
                is_main = odds_entry.get("is_main")
                player_id = odds_entry.get("player_id")
                team_id = odds_entry.get("team_id")
                selection_line = odds_entry.get("selection_line")
                points = odds_entry.get("points")
                odds_timestamp = odds_entry.get("timestamp")
                
                # Convert price to Decimal if it's numeric
                price_decimal = None
                if price is not None:
                    try:
                        price_decimal = Decimal(str(price))
                    except (ValueError, TypeError):
                        pass
                
                # Convert points to Decimal if it's numeric
                points_decimal = None
                if points is not None:
                    try:
                        points_decimal = Decimal(str(points))
                    except (ValueError, TypeError):
                        pass
                
                # Convert timestamp
                timestamp_decimal = None
                if odds_timestamp is not None:
                    try:
                        timestamp_decimal = Decimal(str(odds_timestamp))
                    except (ValueError, TypeError):
                        pass
                
                # Create odds entry
                entry = OddsEntry(
                    tool_call_id=tool_call_id,
                    session_id=session_id,
                    fixture_id=fixture_id,
                    fixture_numerical_id=fixture_numerical_id,
                    odds_entry_id=odds_entry_id,
                    sportsbook=sportsbook,
                    market=market,
                    market_id=market_id,
                    selection=selection,
                    selection_name=selection_name,
                    normalized_selection=normalized_selection,
                    price=price_decimal,
                    is_main=str(is_main) if is_main is not None else None,
                    player_id=player_id,
                    team_id=team_id,
                    selection_line=selection_line,
                    points=points_decimal,
                    full_entry_data=odds_entry,  # Store full entry as JSONB
                    odds_timestamp=timestamp_decimal,
                )
                
                db.add(entry)
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"Error saving odds entry: {e}")
                continue
        
        db.commit()
        logger.info(f"Saved {saved_count} odds entries for fixture_id={fixture_id}, tool_call_id={tool_call_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving odds to database: {e}")
        raise
    finally:
        db.close()
    
    return saved_count


def get_odds_entries(
    fixture_id: Optional[str] = None,
    session_id: Optional[str] = None,
    sportsbook: Optional[str] = None,
    market: Optional[str] = None,
    market_id: Optional[str] = None,
    player_id: Optional[str] = None,
    team_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[OddsEntry]:
    """
    Query odds entries with filters.
    
    Args:
        fixture_id: Filter by fixture ID
        session_id: Filter by session ID
        sportsbook: Filter by sportsbook name
        market: Filter by market name (e.g., "Moneyline", "Spread")
        market_id: Filter by market ID
        player_id: Filter by player ID
        team_id: Filter by team ID
        limit: Maximum number of results
        offset: Offset for pagination
        
    Returns:
        List of OddsEntry objects
    """
    db = SessionLocal()
    try:
        query = db.query(OddsEntry)
        
        # Apply filters
        if fixture_id:
            query = query.filter(OddsEntry.fixture_id == fixture_id)
        if session_id:
            query = query.filter(OddsEntry.session_id == session_id)
        if sportsbook:
            query = query.filter(OddsEntry.sportsbook == sportsbook)
        if market:
            query = query.filter(OddsEntry.market == market)
        if market_id:
            query = query.filter(OddsEntry.market_id == market_id)
        if player_id:
            query = query.filter(OddsEntry.player_id == player_id)
        if team_id:
            query = query.filter(OddsEntry.team_id == team_id)
        
        # Order by created_at descending (most recent first)
        query = query.order_by(desc(OddsEntry.created_at))
        
        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query.all()
    finally:
        db.close()


def get_odds_entries_chunked(
    fixture_id: str,
    session_id: Optional[str] = None,
    sportsbook: Optional[str] = None,
    market: Optional[str] = None,
    chunk_size: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Get odds entries in chunks for streaming.
    
    Args:
        fixture_id: Fixture ID
        session_id: Optional session ID filter
        sportsbook: Optional sportsbook filter
        market: Optional market filter (e.g., "Moneyline", "Spread", "Total")
        chunk_size: Number of entries per chunk
        offset: Offset for pagination
        
    Returns:
        Dictionary with:
        - entries: List of odds entries (as dicts)
        - total: Total count
        - has_more: Whether there are more entries
        - next_offset: Next offset for pagination
    """
    db = SessionLocal()
    try:
        # Build query
        query = db.query(OddsEntry).filter(OddsEntry.fixture_id == fixture_id)
        
        if session_id:
            query = query.filter(OddsEntry.session_id == session_id)
        if sportsbook:
            query = query.filter(OddsEntry.sportsbook == sportsbook)
        if market:
            query = query.filter(OddsEntry.market == market)
        
        # Get total count
        total = query.count()
        
        # Get chunk
        entries = query.order_by(desc(OddsEntry.created_at)).offset(offset).limit(chunk_size).all()
        
        # Convert to dicts
        entries_dicts = []
        for entry in entries:
            entry_dict = {
                "id": entry.odds_entry_id,
                "sportsbook": entry.sportsbook,
                "market": entry.market,
                "market_id": entry.market_id,
                "selection": entry.selection,
                "selection_name": entry.selection_name,
                "price": float(entry.price) if entry.price else None,
                "player_id": entry.player_id,
                "team_id": entry.team_id,
                "selection_line": entry.selection_line,
                "points": float(entry.points) if entry.points else None,
            }
            # Include full entry data if available
            if entry.full_entry_data:
                entry_dict.update(entry.full_entry_data)
            entries_dicts.append(entry_dict)
        
        has_more = (offset + chunk_size) < total
        next_offset = offset + chunk_size if has_more else None
        
        return {
            "entries": entries_dicts,
            "total": total,
            "has_more": has_more,
            "next_offset": next_offset,
            "chunk_size": chunk_size,
        }
    finally:
        db.close()


def get_main_markets_odds(
    fixture_id: str,
    session_id: Optional[str] = None,
    sportsbook: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get main markets (Moneyline, Spread, Total) odds for a fixture.
    
    Args:
        fixture_id: Fixture ID
        session_id: Optional session ID filter
        sportsbook: Optional sportsbook filter
        
    Returns:
        Dictionary with market names as keys and lists of odds entries as values
    """
    main_markets = ["Moneyline", "Spread", "Total", "Run Line", "Total Runs"]
    
    db = SessionLocal()
    try:
        query = db.query(OddsEntry).filter(
            OddsEntry.fixture_id == fixture_id,
            OddsEntry.market.in_(main_markets)
        )
        
        if session_id:
            query = query.filter(OddsEntry.session_id == session_id)
        if sportsbook:
            query = query.filter(OddsEntry.sportsbook == sportsbook)
        
        entries = query.order_by(OddsEntry.market, OddsEntry.selection).all()
        
        # Group by market
        result = {}
        for entry in entries:
            market = entry.market
            if market not in result:
                result[market] = []
            
            entry_dict = {
                "id": entry.odds_entry_id,
                "sportsbook": entry.sportsbook,
                "market": entry.market,
                "selection": entry.selection,
                "price": float(entry.price) if entry.price else None,
                "selection_line": entry.selection_line,
            }
            if entry.full_entry_data:
                entry_dict.update(entry.full_entry_data)
            result[market].append(entry_dict)
        
        return result
    finally:
        db.close()

