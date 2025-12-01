"""
Polling service for fetching and storing NFL odds from OpticOdds API.
Runs every 24 hours to keep the database up to date with odds for all NFL fixtures.
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.nfl_fixture import NFLFixture
from app.models.nfl_odds import NFLOdds

logger = logging.getLogger(__name__)


class NFLOddsPollingService:
    """Service for polling OpticOdds API and storing NFL odds."""
    
    def __init__(self):
        self.api_key = settings.OPTICODDS_API_KEY
        self.api_url = "https://api.opticodds.com/api/v3/fixtures/odds"
        self.sportsbooks = ["fanduel", "betmgm", "draftkings", "caesars", "betrivers"]
        self.polling_interval = 86400  # 24 hours in seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.batch_size = 5  # Maximum fixture IDs per request
    
    def get_all_fixture_ids(self, db: Session) -> List[str]:
        """
        Get all fixture IDs from the NFL fixtures database.
        
        Args:
            db: Database session
            
        Returns:
            List of fixture IDs
        """
        fixtures = db.query(NFLFixture.id).all()
        fixture_ids = [fixture.id for fixture in fixtures]
        logger.info(f"Found {len(fixture_ids)} fixtures in database")
        return fixture_ids
    
    def batch_fixture_ids(self, fixture_ids: List[str]) -> List[List[str]]:
        """
        Batch fixture IDs into groups of batch_size.
        
        Args:
            fixture_ids: List of fixture IDs
            
        Returns:
            List of batches, each containing up to batch_size fixture IDs
        """
        batches = []
        for i in range(0, len(fixture_ids), self.batch_size):
            batch = fixture_ids[i:i + self.batch_size]
            batches.append(batch)
        logger.info(f"Batched {len(fixture_ids)} fixture IDs into {len(batches)} batches")
        return batches
    
    async def fetch_odds_from_api(self, fixture_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch odds for multiple fixtures from OpticOdds API.
        
        Args:
            fixture_ids: List of fixture IDs (up to 5)
            
        Returns:
            List of fixture data with odds from the API
        """
        try:
            headers = {
                "X-Api-Key": self.api_key,
                "accept": "application/json"
            }
            
            # Build query string manually to support multiple values for same parameter
            # httpx params don't handle multiple values well, so we build URL manually
            from urllib.parse import urlencode
            query_parts = []
            for sportsbook in self.sportsbooks:
                query_parts.append(("sportsbook", sportsbook))
            for fixture_id in fixture_ids:
                query_parts.append(("fixture_id", fixture_id))
            
            query_string = urlencode(query_parts)
            url = f"{self.api_url}?{query_string}"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Extract fixtures from response
                fixtures = data.get("data", [])
                logger.info(f"Fetched odds for {len(fixtures)} fixtures from OpticOdds API (requested {len(fixture_ids)})")
                return fixtures
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching odds from OpticOdds API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching odds from OpticOdds API: {e}", exc_info=True)
            raise
    
    def extract_odds_fields(self, odds_entry: Dict[str, Any], fixture_id: str) -> Dict[str, Any]:
        """
        Extract individual fields from odds entry for indexing.
        
        Args:
            odds_entry: Complete odds entry data from OpticOdds API
            fixture_id: The fixture ID this odds entry belongs to
            
        Returns:
            Dictionary of extracted fields
        """
        market_id = odds_entry.get("market_id")
        market_category = NFLOdds.get_market_category(market_id)
        
        return {
            "id": odds_entry.get("id"),
            "fixture_id": fixture_id,
            "sportsbook": odds_entry.get("sportsbook"),
            "market": odds_entry.get("market"),
            "market_id": market_id,
            "market_category": market_category,
            "name": odds_entry.get("name"),
            "selection": odds_entry.get("selection"),
            "normalized_selection": odds_entry.get("normalized_selection"),
            "selection_line": odds_entry.get("selection_line"),
            "player_id": odds_entry.get("player_id"),
            "team_id": odds_entry.get("team_id"),
            "price": odds_entry.get("price"),
            "points": odds_entry.get("points"),
            "is_main": odds_entry.get("is_main", False),
            "timestamp": odds_entry.get("timestamp"),
            "grouping_key": odds_entry.get("grouping_key"),
        }
    
    def store_odds_for_fixture(self, db: Session, fixture_data: Dict[str, Any]) -> Tuple[int, int]:
        """
        Store or update all odds entries for a fixture.
        
        Args:
            db: Database session
            fixture_data: Complete fixture data with odds from OpticOdds API
            
        Returns:
            Tuple of (stored_count, updated_count)
        """
        fixture_id = fixture_data.get("id")
        if not fixture_id:
            raise ValueError("Fixture data missing 'id' field")
        
        odds_entries = fixture_data.get("odds", [])
        if not odds_entries:
            logger.debug(f"No odds entries found for fixture {fixture_id}")
            return 0, 0
        
        stored_count = 0
        updated_count = 0
        
        for odds_entry in odds_entries:
            odds_id = odds_entry.get("id")
            if not odds_id:
                logger.warning(f"Skipping odds entry with missing ID: {odds_entry}")
                continue
            
            # Extract fields for indexing
            fields = self.extract_odds_fields(odds_entry, fixture_id)
            
            # SQLAlchemy's JSON/JSONB types handle dict serialization automatically
            stored_data = odds_entry
            
            # Try to find existing odds entry first
            existing = db.query(NFLOdds).filter(NFLOdds.id == odds_id).first()
            
            if existing:
                # Update existing odds entry
                for key, value in fields.items():
                    setattr(existing, key, value)
                existing.odds_data = stored_data
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Try to create new odds entry
                try:
                    new_odds = NFLOdds(
                        odds_data=stored_data,
                        **fields
                    )
                    db.add(new_odds)
                    db.flush()  # Flush to trigger any IntegrityError immediately
                    stored_count += 1
                except IntegrityError:
                    # Race condition: odds entry was inserted by another process/thread
                    # Rollback the failed insert and fetch the existing one
                    db.rollback()
                    existing = db.query(NFLOdds).filter(NFLOdds.id == odds_id).first()
                    if existing:
                        # Update the existing odds entry
                        for key, value in fields.items():
                            setattr(existing, key, value)
                        existing.odds_data = stored_data
                        existing.updated_at = datetime.utcnow()
                        updated_count += 1
                    else:
                        # This shouldn't happen, but handle it
                        logger.error(f"Odds entry {odds_id} not found after IntegrityError")
        
        return stored_count, updated_count
    
    def get_last_update_time(self, db: Session) -> Optional[datetime]:
        """
        Get the timestamp of the last odds update from the database.
        
        Args:
            db: Database session
            
        Returns:
            Last update datetime or None if no odds exist
        """
        try:
            from sqlalchemy import func
            last_update = db.query(func.max(NFLOdds.updated_at)).scalar()
            return last_update
        except Exception as e:
            logger.warning(f"Error getting last update time: {e}")
            return None
    
    async def poll_and_store(self) -> Dict[str, Any]:
        """
        Poll OpticOdds API and store odds in database for all NFL fixtures.
        
        Returns:
            Dictionary with polling statistics
        """
        db = SessionLocal()
        try:
            logger.info("Starting NFL odds polling...")
            
            # Get all fixture IDs from database
            fixture_ids = self.get_all_fixture_ids(db)
            
            if not fixture_ids:
                logger.warning("No fixtures found in database")
                return {
                    "success": True,
                    "fixtures_processed": 0,
                    "odds_stored": 0,
                    "odds_updated": 0,
                    "errors": 0
                }
            
            # Batch fixture IDs
            batches = self.batch_fixture_ids(fixture_ids)
            
            total_stored = 0
            total_updated = 0
            total_errors = 0
            fixtures_processed = 0
            
            # Process each batch
            for batch_idx, batch in enumerate(batches):
                logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} with {len(batch)} fixture IDs")
                
                try:
                    # Fetch odds for this batch
                    fixtures_with_odds = await self.fetch_odds_from_api(batch)
                    
                    # Store odds for each fixture
                    for fixture_data in fixtures_with_odds:
                        fixture_id = fixture_data.get("id")
                        if not fixture_id:
                            logger.warning(f"Skipping fixture with missing ID: {fixture_data}")
                            continue
                        
                        try:
                            stored, updated = self.store_odds_for_fixture(db, fixture_data)
                            total_stored += stored
                            total_updated += updated
                            fixtures_processed += 1
                            
                            if stored > 0 or updated > 0:
                                logger.debug(f"Fixture {fixture_id}: stored {stored} new odds, updated {updated} existing odds")
                                
                        except Exception as e:
                            total_errors += 1
                            db.rollback()
                            logger.error(f"Error storing odds for fixture {fixture_id}: {e}", exc_info=True)
                            continue
                    
                    # Commit after each batch
                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error committing batch {batch_idx + 1}: {e}", exc_info=True)
                        total_errors += len(batch)
                        continue
                    
                    # Small delay between batches to avoid rate limiting
                    if batch_idx < len(batches) - 1:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    total_errors += len(batch)
                    db.rollback()
                    logger.error(f"Error processing batch {batch_idx + 1}: {e}", exc_info=True)
                    continue
            
            stats = {
                "success": True,
                "fixtures_processed": fixtures_processed,
                "total_fixtures": len(fixture_ids),
                "odds_stored": total_stored,
                "odds_updated": total_updated,
                "errors": total_errors,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"NFL odds polling completed: {stats}")
            return stats
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in NFL odds polling: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            db.close()
    
    async def start_polling(self):
        """Start the polling service in the background."""
        if self.is_running:
            logger.warning("Odds polling service is already running")
            return
        
        self.is_running = True
        logger.info("Starting NFL odds polling service...")
        
        # Check when the database was last updated
        db = SessionLocal()
        try:
            last_update = self.get_last_update_time(db)
            if last_update:
                # Normalize timezone for comparison
                # Database returns timezone-aware datetime, convert to UTC naive for comparison
                if last_update.tzinfo is not None:
                    last_update_naive = last_update.replace(tzinfo=None)
                else:
                    last_update_naive = last_update
                
                now = datetime.utcnow()
                time_since_update = (now - last_update_naive).total_seconds()
                hours_since_update = time_since_update / 3600
                
                logger.info(f"Last odds update: {last_update} ({hours_since_update:.2f} hours ago)")
                
                if time_since_update < self.polling_interval:
                    # Less than 24 hours since last update, wait for remaining time
                    time_to_wait = self.polling_interval - time_since_update
                    hours_to_wait = time_to_wait / 3600
                    logger.info(f"Last update was {hours_since_update:.2f} hours ago. Waiting {hours_to_wait:.2f} hours before next poll.")
                    
                    # Schedule initial poll after remaining time
                    async def delayed_initial_poll():
                        await asyncio.sleep(time_to_wait)
                        if self.is_running:
                            await self.poll_and_store()
                    
                    asyncio.create_task(delayed_initial_poll())
                else:
                    # 24 hours or more since last update, poll immediately
                    logger.info(f"Last update was {hours_since_update:.2f} hours ago. Polling immediately.")
                    await self.poll_and_store()
            else:
                # No odds in database yet, poll immediately
                logger.info("No odds found in database. Polling immediately.")
                await self.poll_and_store()
        except Exception as e:
            logger.error(f"Error checking last update time: {e}", exc_info=True)
            # If we can't check, poll immediately to be safe
            logger.info("Unable to check last update time. Polling immediately.")
            await self.poll_and_store()
        finally:
            db.close()
        
        # Then poll every 24 hours
        async def polling_loop():
            while self.is_running:
                try:
                    await asyncio.sleep(self.polling_interval)
                    if self.is_running:
                        await self.poll_and_store()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in odds polling loop: {e}", exc_info=True)
                    # Continue polling even if there's an error
                    await asyncio.sleep(3600)  # Wait 1 hour before retrying
        
        self._task = asyncio.create_task(polling_loop())
        logger.info("NFL odds polling service started")
    
    async def stop_polling(self):
        """Stop the polling service."""
        if not self.is_running:
            return
        
        logger.info("Stopping NFL odds polling service...")
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("NFL odds polling service stopped")


# Global instance
nfl_odds_polling_service = NFLOddsPollingService()

