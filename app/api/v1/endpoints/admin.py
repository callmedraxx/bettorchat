"""
Admin endpoints for system maintenance and data refresh.
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.core.nfl_players_db import (
    refresh_all_nfl_players,
    get_player_count,
    clear_all_nfl_players,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class RefreshResponse(BaseModel):
    """Response model for refresh operations."""
    success: bool
    message: str
    stats: Dict[str, Any] = {}


@router.post("/refresh-nfl-players", response_model=RefreshResponse)
async def refresh_nfl_players(
    clear_existing: bool = False,
    background: BackgroundTasks = None
):
    """
    Manually trigger refresh of all NFL players from OpticOdds API.
    
    This endpoint:
    1. Fetches all 32 pages of NFL players from OpticOdds API
    2. Saves each page to JSON files in data/nfl_players/
    3. Upserts all players to PostgreSQL database
    
    Args:
        clear_existing: If True, clear existing players before refresh
        background: FastAPI BackgroundTasks for async execution
    
    Returns:
        Refresh statistics and status
    """
    try:
        logger.info("NFL players refresh requested via API endpoint")
        
        # Run in background to avoid timeout
        if background:
            background.add_task(refresh_all_nfl_players, clear_existing=clear_existing)
            return RefreshResponse(
                success=True,
                message="NFL players refresh started in background",
                stats={"status": "processing"}
            )
        else:
            # Run synchronously (may timeout for large datasets)
            stats = refresh_all_nfl_players(clear_existing=clear_existing)
            return RefreshResponse(
                success=True,
                message=f"Successfully refreshed {stats['total_players']} NFL players",
                stats=stats
            )
            
    except Exception as e:
        logger.error(f"Error refreshing NFL players: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error refreshing NFL players: {str(e)}"
        )


@router.get("/nfl-players/count")
async def get_nfl_players_count():
    """
    Get current count of NFL players in database.
    
    Returns:
        Player count
    """
    try:
        count = get_player_count()
        return {
            "success": True,
            "count": count
        }
    except Exception as e:
        logger.error(f"Error getting player count: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting player count: {str(e)}"
        )


@router.delete("/nfl-players/clear")
async def clear_nfl_players():
    """
    Clear all NFL players from database.
    
    WARNING: This will delete all player data!
    
    Returns:
        Number of players deleted
    """
    try:
        deleted_count = clear_all_nfl_players()
        return {
            "success": True,
            "message": f"Cleared {deleted_count} players from database",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error clearing players: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing players: {str(e)}"
        )

