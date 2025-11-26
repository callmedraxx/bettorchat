"""
Fixture storage service for saving fixtures to PostgreSQL database.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.fixture import Fixture
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def save_fixtures_to_db(session_id: str, fixtures: List[Dict[str, Any]]) -> bool:
    """
    Save fixtures to PostgreSQL database.
    
    Args:
        session_id: Session identifier (user_id or thread_id)
        fixtures: List of fixture objects to save
        
    Returns:
        True if successful, False otherwise
    """
    if not fixtures:
        logger.warning(f"[FixtureStorage] No fixtures to save for session_id={session_id}")
        return False
    
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        saved_count = 0
        
        for fixture_data in fixtures:
            try:
                # Extract fixture_id from fixture data
                fixture_id = fixture_data.get("id") or fixture_data.get("fixture_id")
                if not fixture_id:
                    logger.warning(f"[FixtureStorage] Skipping fixture without id: {fixture_data}")
                    continue
                
                # Check if fixture already exists for this session_id
                existing = db.query(Fixture).filter(
                    Fixture.session_id == session_id,
                    Fixture.fixture_id == str(fixture_id)
                ).first()
                
                if existing:
                    # Update existing fixture
                    existing.fixture_data = fixture_data
                    logger.debug(f"[FixtureStorage] Updated fixture {fixture_id} for session_id={session_id}")
                else:
                    # Create new fixture
                    fixture = Fixture(
                        session_id=session_id,
                        fixture_id=str(fixture_id),
                        fixture_data=fixture_data
                    )
                    db.add(fixture)
                    logger.debug(f"[FixtureStorage] Created fixture {fixture_id} for session_id={session_id}")
                
                saved_count += 1
                
            except Exception as e:
                logger.error(f"[FixtureStorage] Error saving fixture {fixture_data.get('id', 'unknown')}: {e}", exc_info=True)
                continue
        
        # Commit all changes
        db.commit()
        logger.info(f"[FixtureStorage] Saved {saved_count}/{len(fixtures)} fixtures to database for session_id={session_id}")
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"[FixtureStorage] Database error saving fixtures: {e}", exc_info=True)
        if db:
            db.rollback()
        return False
    except Exception as e:
        logger.error(f"[FixtureStorage] Unexpected error saving fixtures: {e}", exc_info=True)
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()


def get_fixtures_from_db(session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieve fixtures from database for a session.
    
    Args:
        session_id: Session identifier
        limit: Optional limit on number of fixtures to return
        
    Returns:
        List of fixture dictionaries
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        query = db.query(Fixture).filter(Fixture.session_id == session_id).order_by(Fixture.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        fixtures = query.all()
        result = [fixture.fixture_data for fixture in fixtures]
        
        logger.info(f"[FixtureStorage] Retrieved {len(result)} fixtures from database for session_id={session_id}")
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"[FixtureStorage] Database error retrieving fixtures: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"[FixtureStorage] Unexpected error retrieving fixtures: {e}", exc_info=True)
        return []
    finally:
        if db:
            db.close()

