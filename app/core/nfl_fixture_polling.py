"""
Polling service for fetching and storing NFL fixtures from OpticOdds API.
Runs every hour to keep the database up to date with active NFL games.
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

logger = logging.getLogger(__name__)


class NFLFixturePollingService:
    """Service for polling OpticOdds API and storing NFL fixtures."""
    
    def __init__(self):
        self.api_key = settings.OPTICODDS_API_KEY
        self.api_url = "https://api.opticodds.com/api/v3/fixtures/active"
        self.league = "nfl"
        self.polling_interval = 3600  # 1 hour in seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    async def fetch_fixtures_from_api(self) -> List[Dict[str, Any]]:
        """
        Fetch active NFL fixtures from OpticOdds API.
        
        Returns:
            List of fixture dictionaries from the API
        """
        try:
            headers = {
                "X-Api-Key": self.api_key,
                "accept": "application/json"
            }
            params = {"league": self.league}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.api_url,
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract fixtures from response
                fixtures = data.get("data", [])
                logger.info(f"Fetched {len(fixtures)} NFL fixtures from OpticOdds API")
                return fixtures
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching fixtures from OpticOdds API: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching fixtures from OpticOdds API: {e}", exc_info=True)
            raise
    
    def extract_fixture_fields(self, fixture_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract individual fields from fixture data for indexing.
        
        Args:
            fixture_data: Complete fixture data from OpticOdds API
            
        Returns:
            Dictionary of extracted fields
        """
        # Extract nested data
        sport = fixture_data.get("sport", {})
        league = fixture_data.get("league", {})
        home_competitors = fixture_data.get("home_competitors", [])
        away_competitors = fixture_data.get("away_competitors", [])
        
        # Parse start_date
        start_date_str = fixture_data.get("start_date")
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return {
            "id": fixture_data.get("id"),
            "numerical_id": fixture_data.get("numerical_id"),
            "game_id": fixture_data.get("game_id"),
            "start_date": start_date,
            "home_team_display": fixture_data.get("home_team_display"),
            "away_team_display": fixture_data.get("away_team_display"),
            "status": fixture_data.get("status"),
            "is_live": fixture_data.get("is_live", False),
            "season_type": fixture_data.get("season_type"),
            "season_year": fixture_data.get("season_year"),
            "season_week": fixture_data.get("season_week"),
            "venue_name": fixture_data.get("venue_name"),
            "venue_location": fixture_data.get("venue_location"),
            "venue_neutral": fixture_data.get("venue_neutral", False),
            "league_id": league.get("id"),
            "league_name": league.get("name"),
            "league_numerical_id": league.get("numerical_id"),
            "sport_id": sport.get("id"),
            "sport_name": sport.get("name"),
            "sport_numerical_id": sport.get("numerical_id"),
            "home_record": fixture_data.get("home_record"),
            "home_seed": fixture_data.get("home_seed"),
            "home_rotation_number": fixture_data.get("home_rotation_number"),
            "away_record": fixture_data.get("away_record"),
            "away_seed": fixture_data.get("away_seed"),
            "away_rotation_number": fixture_data.get("away_rotation_number"),
            "has_odds": fixture_data.get("has_odds", False),
            "broadcast": fixture_data.get("broadcast"),
        }
    
    def store_fixture(self, db: Session, fixture_data: Dict[str, Any]) -> Tuple[NFLFixture, bool]:
        """
        Store or update a fixture in the database using upsert pattern.
        
        Args:
            db: Database session
            fixture_data: Complete fixture data from OpticOdds API
            
        Returns:
            Tuple of (NFLFixture instance, is_new: bool)
        """
        fixture_id = fixture_data.get("id")
        if not fixture_id:
            raise ValueError("Fixture data missing 'id' field")
        
        # Extract fields for indexing
        fields = self.extract_fixture_fields(fixture_data)
        
        # SQLAlchemy's JSON/JSONB types handle dict serialization automatically
        stored_data = fixture_data
        
        # Try to find existing fixture first
        existing = db.query(NFLFixture).filter(NFLFixture.id == fixture_id).first()
        
        if existing:
            # Update existing fixture
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.fixture_data = stored_data
            existing.updated_at = datetime.utcnow()
            return existing, False
        else:
            # Try to create new fixture
            # If it fails due to duplicate key (race condition), fetch and update
            try:
                new_fixture = NFLFixture(
                    fixture_data=stored_data,
                    **fields
                )
                db.add(new_fixture)
                db.flush()  # Flush to trigger any IntegrityError immediately
                return new_fixture, True
            except IntegrityError:
                # Race condition: fixture was inserted by another process/thread
                # Rollback the failed insert and fetch the existing one
                db.rollback()
                existing = db.query(NFLFixture).filter(NFLFixture.id == fixture_id).first()
                if existing:
                    # Update the existing fixture
                    for key, value in fields.items():
                        setattr(existing, key, value)
                    existing.fixture_data = stored_data
                    existing.updated_at = datetime.utcnow()
                    return existing, False
                else:
                    # This shouldn't happen, but handle it
                    raise ValueError(f"Fixture {fixture_id} not found after IntegrityError")
    
    async def poll_and_store(self) -> Dict[str, Any]:
        """
        Poll OpticOdds API and store fixtures in database.
        
        Returns:
            Dictionary with polling statistics
        """
        db = SessionLocal()
        try:
            logger.info("Starting NFL fixture polling...")
            
            # Fetch fixtures from API
            fixtures = await self.fetch_fixtures_from_api()
            
            if not fixtures:
                logger.warning("No fixtures returned from API")
                return {
                    "success": True,
                    "fetched": 0,
                    "stored": 0,
                    "updated": 0,
                    "errors": 0
                }
            
            # Store fixtures
            stored_count = 0
            updated_count = 0
            error_count = 0
            
            for fixture_data in fixtures:
                fixture_id = fixture_data.get("id")
                if not fixture_id:
                    error_count += 1
                    logger.warning(f"Skipping fixture with missing ID: {fixture_data}")
                    continue
                
                try:
                    # Store or update the fixture (handles upsert internally)
                    fixture, is_new = self.store_fixture(db, fixture_data)
                    
                    # Track counts
                    if is_new:
                        stored_count += 1
                    else:
                        updated_count += 1
                        
                except IntegrityError as e:
                    # This should be rare now since store_fixture handles it, but keep as safety net
                    error_count += 1
                    db.rollback()
                    logger.warning(f"Duplicate key violation for fixture {fixture_id}, attempting to update instead")
                    
                    # Try to update the existing fixture
                    try:
                        existing = db.query(NFLFixture).filter(
                            NFLFixture.id == fixture_id
                        ).first()
                        if existing:
                            # Update existing fixture
                            fields = self.extract_fixture_fields(fixture_data)
                            for key, value in fields.items():
                                setattr(existing, key, value)
                            existing.fixture_data = fixture_data
                            existing.updated_at = datetime.utcnow()
                            updated_count += 1
                            error_count -= 1  # Not really an error, just a race condition
                        else:
                            logger.error(f"Fixture {fixture_id} not found after duplicate key error")
                    except Exception as update_error:
                        logger.error(f"Error updating fixture {fixture_id} after duplicate key error: {update_error}")
                        db.rollback()
                        
                except Exception as e:
                    error_count += 1
                    # Rollback the current transaction to allow processing of remaining fixtures
                    db.rollback()
                    logger.error(f"Error storing fixture {fixture_id}: {e}", exc_info=True)
                    # Continue processing other fixtures
                    continue
            
            # Commit all changes
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Error committing fixture changes: {e}", exc_info=True)
                raise
            
            # Remove fixtures that are no longer in the API response (optional - you may want to keep historical data)
            # For now, we'll keep all fixtures and just update them
            
            stats = {
                "success": True,
                "fetched": len(fixtures),
                "stored": stored_count,
                "updated": updated_count,
                "errors": error_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"NFL fixture polling completed: {stats}")
            return stats
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in NFL fixture polling: {e}", exc_info=True)
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
            logger.warning("Polling service is already running")
            return
        
        self.is_running = True
        logger.info("Starting NFL fixture polling service...")
        
        # Run initial poll immediately
        await self.poll_and_store()
        
        # Then poll every hour
        async def polling_loop():
            while self.is_running:
                try:
                    await asyncio.sleep(self.polling_interval)
                    if self.is_running:
                        await self.poll_and_store()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in polling loop: {e}", exc_info=True)
                    # Continue polling even if there's an error
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
        
        self._task = asyncio.create_task(polling_loop())
        logger.info("NFL fixture polling service started")
    
    async def stop_polling(self):
        """Stop the polling service."""
        if not self.is_running:
            return
        
        logger.info("Stopping NFL fixture polling service...")
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("NFL fixture polling service stopped")


# Global instance
nfl_fixture_polling_service = NFLFixturePollingService()

