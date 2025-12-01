#!/usr/bin/env python3
"""
Script to fetch all NFL players from OpticOdds API and store them in JSON files and database.

Usage:
    python app/scripts/fetch_nfl_players.py

This script:
1. Fetches all 32 pages of NFL players from OpticOdds API
2. Saves each page to JSON files in data/nfl_players/
3. Upserts all players to PostgreSQL database
"""
import sys
import os
import logging
from pathlib import Path

# Add /app to path to import app modules (when running from container)
# The script is in /app/app/scripts/, so we need /app in the path
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from app.core.nfl_players_db import refresh_all_nfl_players
from app.core.database import engine, Base
from app.models.nfl_player import NFLPlayer  # Import to register model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to fetch and store NFL players."""
    logger.info("Starting NFL players fetch script...")
    
    # Ensure database table exists
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Database table verified/created")
    except Exception as e:
        logger.warning(f"Table creation check: {e}")
        # Continue anyway - table might already exist
    
    try:
        # Ask user if they want to clear existing data
        clear_existing = False
        if len(sys.argv) > 1 and sys.argv[1] == "--clear":
            clear_existing = True
            logger.info("Will clear existing players before refresh")
        
        # Refresh all NFL players
        stats = refresh_all_nfl_players(clear_existing=clear_existing)
        
        logger.info("=" * 60)
        logger.info("NFL Players Fetch Complete!")
        logger.info("=" * 60)
        logger.info(f"Total players fetched: {stats['total_players']}")
        logger.info(f"Players saved to database: {stats['saved_to_db']}")
        logger.info(f"Pages fetched: {stats['pages_fetched']}")
        logger.info(f"JSON files created: {stats['json_files_created']}")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error fetching NFL players: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

