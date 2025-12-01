"""
Database operations for storing and querying NFL players.
Optimized for fast team-to-player lookups using PostgreSQL indexes.
"""
import json
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.core.database import SessionLocal
from app.models.nfl_player import NFLPlayer
from app.core.opticodds_client import OpticOddsClient
from app.core.config import settings

logger = logging.getLogger(__name__)

# Directory for JSON storage
JSON_STORAGE_DIR = Path("data/nfl_players")
JSON_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_players_to_json(players_data: List[Dict[str, Any]], page: int) -> str:
    """
    Save players data to JSON file for a specific page.
    
    Args:
        players_data: List of player dictionaries from API
        page: Page number (1-32)
    
    Returns:
        Path to saved JSON file
    """
    file_path = JSON_STORAGE_DIR / f"nfl_players_page_{page}.json"
    
    data = {
        "page": page,
        "total_players": len(players_data),
        "data": players_data
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(players_data)} players to {file_path}")
    return str(file_path)


def save_all_players_to_json(all_players: List[Dict[str, Any]]) -> str:
    """
    Save all players to a combined JSON file.
    
    Args:
        all_players: List of all player dictionaries
    
    Returns:
        Path to saved JSON file
    """
    file_path = JSON_STORAGE_DIR / "nfl_players_all.json"
    
    data = {
        "total_players": len(all_players),
        "data": all_players
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(all_players)} players to combined file {file_path}")
    return str(file_path)


def load_players_from_json(page: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load players from JSON file(s).
    
    Args:
        page: Optional page number. If None, loads all pages.
    
    Returns:
        List of player dictionaries
    """
    if page:
        file_path = JSON_STORAGE_DIR / f"nfl_players_page_{page}.json"
        if not file_path.exists():
            logger.warning(f"JSON file not found: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("data", [])
    else:
        # Load from combined file if it exists, otherwise load all pages
        combined_file = JSON_STORAGE_DIR / "nfl_players_all.json"
        if combined_file.exists():
            with open(combined_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("data", [])
        
        # Load all pages
        all_players = []
        for page_num in range(1, 33):
            page_players = load_players_from_json(page=page_num)
            all_players.extend(page_players)
        
        return all_players


def save_players_to_db(players_data: List[Dict[str, Any]], clear_existing: bool = False) -> int:
    """
    Bulk insert/update players to database.
    Uses PostgreSQL ON CONFLICT for efficient upserts.
    
    Args:
        players_data: List of player dictionaries from API
        clear_existing: If True, delete all existing players before insert
    
    Returns:
        Number of players saved
    """
    db = SessionLocal()
    saved_count = 0
    
    try:
        if clear_existing:
            deleted_count = db.query(NFLPlayer).delete()
            logger.info(f"Cleared {deleted_count} existing players from database")
        
        players_to_insert = []
        
        for player_data in players_data:
            if not isinstance(player_data, dict):
                continue
            
            try:
                # Extract team information
                team_info = player_data.get("team", {})
                team_id = team_info.get("id") if isinstance(team_info, dict) else None
                team_name = team_info.get("name") if isinstance(team_info, dict) else None
                
                if not team_id:
                    logger.warning(f"Player {player_data.get('id')} has no team_id, skipping")
                    continue
                
                # Extract source_ids and other metadata
                source_ids = player_data.get("source_ids", {})
                extra_data = {
                    "sport": player_data.get("sport"),
                    "league": player_data.get("league"),
                }
                
                player = NFLPlayer(
                    id=player_data.get("id"),
                    name=player_data.get("name", ""),
                    first_name=player_data.get("first_name"),
                    last_name=player_data.get("last_name"),
                    position=player_data.get("position"),
                    number=player_data.get("number"),
                    age=player_data.get("age"),
                    height=player_data.get("height"),
                    weight=player_data.get("weight"),
                    experience=player_data.get("experience"),
                    team_id=team_id,
                    team_name=team_name,
                    is_active=player_data.get("is_active", True),
                    numerical_id=player_data.get("numerical_id"),
                    base_id=player_data.get("base_id"),
                    logo=player_data.get("logo"),
                    source_ids=source_ids if source_ids else None,
                    extra_data=extra_data,
                )
                
                players_to_insert.append(player)
                
            except Exception as e:
                logger.error(f"Error processing player {player_data.get('id', 'unknown')}: {e}")
                continue
        
        # Bulk upsert using merge (works for both PostgreSQL and SQLite)
        for player in players_to_insert:
            # Check if exists
            existing = db.query(NFLPlayer).filter(NFLPlayer.id == player.id).first()
            if existing:
                # Update existing
                for key, value in player.__dict__.items():
                    if not key.startswith('_') and key != 'id':
                        setattr(existing, key, value)
            else:
                # Insert new
                db.add(player)
            
            saved_count += 1
        
        db.commit()
        logger.info(f"Saved {saved_count} players to database")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving players to database: {e}")
        raise
    finally:
        db.close()
    
    return saved_count


def get_players_by_team(team_id: str, active_only: bool = True) -> List[NFLPlayer]:
    """
    Get all players for a specific team.
    Uses indexed team_id for hashmap-like fast lookup.
    
    Args:
        team_id: Team ID from nfl_teams
        active_only: If True, only return active players
    
    Returns:
        List of NFLPlayer objects
    """
    db = SessionLocal()
    try:
        query = db.query(NFLPlayer).filter(NFLPlayer.team_id == team_id)
        
        if active_only:
            query = query.filter(NFLPlayer.is_active == True)
        
        players = query.order_by(NFLPlayer.name).all()
        return players
    finally:
        db.close()


def get_player_by_id(player_id: str) -> Optional[NFLPlayer]:
    """
    Get a single player by ID.
    
    Args:
        player_id: Player ID from OpticOdds API
    
    Returns:
        NFLPlayer object or None
    """
    db = SessionLocal()
    try:
        return db.query(NFLPlayer).filter(NFLPlayer.id == player_id).first()
    finally:
        db.close()


def get_player_by_name(
    name: str, 
    team_id: Optional[str] = None,
    active_only: bool = True
) -> List[NFLPlayer]:
    """
    Search players by name with optional team filter.
    Uses composite index for fast team+name lookups.
    
    Args:
        name: Player name (case-insensitive partial match)
        team_id: Optional team ID to filter by
        active_only: If True, only return active players
    
    Returns:
        List of matching NFLPlayer objects
    """
    db = SessionLocal()
    try:
        query = db.query(NFLPlayer)
        
        # Case-insensitive name search
        name_lower = name.lower()
        query = query.filter(func.lower(NFLPlayer.name).contains(name_lower))
        
        if team_id:
            query = query.filter(NFLPlayer.team_id == team_id)
        
        if active_only:
            query = query.filter(NFLPlayer.is_active == True)
        
        players = query.order_by(NFLPlayer.name).limit(50).all()
        return players
    finally:
        db.close()


def get_players_by_position(
    position: str,
    team_id: Optional[str] = None,
    active_only: bool = True
) -> List[NFLPlayer]:
    """
    Get players by position with optional team filter.
    Uses composite index for fast team+position lookups.
    
    Args:
        position: Player position (e.g., "QB", "WR", "RB")
        team_id: Optional team ID to filter by
        active_only: If True, only return active players
    
    Returns:
        List of matching NFLPlayer objects
    """
    db = SessionLocal()
    try:
        query = db.query(NFLPlayer).filter(NFLPlayer.position == position)
        
        if team_id:
            query = query.filter(NFLPlayer.team_id == team_id)
        
        if active_only:
            query = query.filter(NFLPlayer.is_active == True)
        
        players = query.order_by(NFLPlayer.name).all()
        return players
    finally:
        db.close()


def refresh_all_nfl_players(clear_existing: bool = False) -> Dict[str, Any]:
    """
    Main refresh function: Fetch all NFL players from OpticOdds API,
    save to JSON files, and upsert to database.
    
    Args:
        clear_existing: If True, clear existing players before refresh
    
    Returns:
        Dictionary with refresh statistics
    """
    client = OpticOddsClient()
    all_players = []
    total_pages = 32
    
    logger.info(f"Starting NFL players refresh (fetching {total_pages} pages)...")
    
    try:
        # Fetch all pages
        for page in range(1, total_pages + 1):
            logger.info(f"Fetching page {page}/{total_pages}...")
            
            # Fetch specific page - pass page parameter directly to API
            # Use _request directly to have full control over pagination
            params = {
                "league": "nfl",
                "page": page,
            }
            
            result = client._request("GET", "/players", params=params, paginate=False)
            
            if not result or "data" not in result:
                logger.warning(f"No data returned for page {page}")
                continue
            
            page_players = result.get("data", [])
            if not page_players:
                logger.warning(f"Empty data array for page {page}")
                continue
            
            # Save to JSON file
            save_players_to_json(page_players, page)
            
            # Add to combined list
            all_players.extend(page_players)
            
            logger.info(f"Page {page}: Fetched {len(page_players)} players")
        
        # Save combined JSON file
        if all_players:
            save_all_players_to_json(all_players)
        
        # Save to database
        saved_count = save_players_to_db(all_players, clear_existing=clear_existing)
        
        stats = {
            "total_players": len(all_players),
            "saved_to_db": saved_count,
            "pages_fetched": total_pages,
            "json_files_created": total_pages + 1,  # +1 for combined file
        }
        
        logger.info(f"NFL players refresh completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error during NFL players refresh: {e}")
        raise


def clear_all_nfl_players() -> int:
    """
    Clear all NFL players from database.
    
    Returns:
        Number of players deleted
    """
    db = SessionLocal()
    try:
        deleted_count = db.query(NFLPlayer).delete()
        db.commit()
        logger.info(f"Cleared {deleted_count} players from database")
        return deleted_count
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing players: {e}")
        raise
    finally:
        db.close()


def get_player_count() -> int:
    """Get total count of players in database."""
    db = SessionLocal()
    try:
        return db.query(NFLPlayer).count()
    finally:
        db.close()

