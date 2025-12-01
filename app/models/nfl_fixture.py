"""
NFL Fixture database model for storing active NFL games from OpticOdds API.
This model stores all active NFL fixtures with comprehensive indexes for fast querying.
"""
import json
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Integer, Boolean, JSON,
    Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

# Use JSONB for PostgreSQL, JSON for SQLite
if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
    FixtureDataType = JSONB
else:
    FixtureDataType = JSON  # SQLite supports JSON type in SQLAlchemy


class NFLFixture(Base):
    """NFL Fixture model for storing active NFL games from OpticOdds API."""
    
    __tablename__ = "nfl_fixtures"
    
    __table_args__ = (
        UniqueConstraint('id', name='uq_nfl_fixture_id'),
        # Comprehensive indexes for fast querying
        Index('idx_nfl_fixture_id', 'id'),
        Index('idx_nfl_fixture_numerical_id', 'numerical_id'),
        Index('idx_nfl_fixture_game_id', 'game_id'),
        Index('idx_nfl_fixture_start_date', 'start_date'),
        Index('idx_nfl_fixture_status', 'status'),
        Index('idx_nfl_fixture_is_live', 'is_live'),
        Index('idx_nfl_fixture_season_year', 'season_year'),
        Index('idx_nfl_fixture_season_week', 'season_week'),
        Index('idx_nfl_fixture_season_type', 'season_type'),
        Index('idx_nfl_fixture_league_id', 'league_id'),
        Index('idx_nfl_fixture_sport_id', 'sport_id'),
        Index('idx_nfl_fixture_home_team_display', 'home_team_display'),
        Index('idx_nfl_fixture_away_team_display', 'away_team_display'),
        Index('idx_nfl_fixture_venue_name', 'venue_name'),
        Index('idx_nfl_fixture_has_odds', 'has_odds'),
        Index('idx_nfl_fixture_created_at', 'created_at'),
        Index('idx_nfl_fixture_updated_at', 'updated_at'),
        # Composite indexes for common queries
        Index('idx_nfl_fixture_status_date', 'status', 'start_date'),
        Index('idx_nfl_fixture_season_week_year', 'season_year', 'season_week'),
        Index('idx_nfl_fixture_teams', 'home_team_display', 'away_team_display'),
    )
    
    # Primary key
    db_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # OpticOdds fixture identifiers
    id = Column(String(255), nullable=False, unique=True, index=True, comment="Fixture ID from OpticOdds API")
    numerical_id = Column(Integer, nullable=True, index=True, comment="Numerical fixture ID")
    game_id = Column(String(255), nullable=True, index=True, comment="Game ID")
    
    # Game timing
    start_date = Column(DateTime(timezone=True), nullable=True, index=True, comment="Game start date/time")
    
    # Teams
    home_team_display = Column(String(255), nullable=True, index=True, comment="Home team display name")
    away_team_display = Column(String(255), nullable=True, index=True, comment="Away team display name")
    
    # Game status
    status = Column(String(50), nullable=True, index=True, comment="Game status (unplayed, live, finished, etc.)")
    is_live = Column(Boolean, default=False, index=True, comment="Whether the game is currently live")
    
    # Season information
    season_type = Column(String(50), nullable=True, index=True, comment="Season type (Regular Season, Playoffs, etc.)")
    season_year = Column(String(10), nullable=True, index=True, comment="Season year")
    season_week = Column(String(10), nullable=True, index=True, comment="Season week number")
    
    # Venue
    venue_name = Column(String(255), nullable=True, index=True, comment="Venue name")
    venue_location = Column(String(255), nullable=True, comment="Venue location")
    venue_neutral = Column(Boolean, default=False, comment="Whether venue is neutral")
    
    # League and sport
    league_id = Column(String(50), nullable=True, index=True, comment="League ID (e.g., 'nfl')")
    league_name = Column(String(100), nullable=True, comment="League name")
    league_numerical_id = Column(Integer, nullable=True, comment="League numerical ID")
    sport_id = Column(String(50), nullable=True, index=True, comment="Sport ID (e.g., 'football')")
    sport_name = Column(String(100), nullable=True, comment="Sport name")
    sport_numerical_id = Column(Integer, nullable=True, comment="Sport numerical ID")
    
    # Team records and rotation numbers
    home_record = Column(String(50), nullable=True, comment="Home team record")
    home_seed = Column(Integer, nullable=True, comment="Home team seed")
    home_rotation_number = Column(Integer, nullable=True, comment="Home team rotation number")
    away_record = Column(String(50), nullable=True, comment="Away team record")
    away_seed = Column(Integer, nullable=True, comment="Away team seed")
    away_rotation_number = Column(Integer, nullable=True, comment="Away team rotation number")
    
    # Odds and broadcast
    has_odds = Column(Boolean, default=False, index=True, comment="Whether odds are available")
    broadcast = Column(String(255), nullable=True, comment="Broadcast information")
    
    # Full fixture data stored as JSON/JSONB
    fixture_data = Column(FixtureDataType, nullable=False, comment="Complete fixture data as JSON from OpticOdds API")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True, comment="Timestamp when fixture was first stored")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True, comment="Timestamp when fixture was last updated")
    
    def __repr__(self):
        return f"<NFLFixture(id={self.id}, home={self.home_team_display}, away={self.away_team_display}, start={self.start_date})>"
    
    def to_dict(self):
        """Convert fixture to dictionary matching OpticOdds API format."""
        # SQLAlchemy's JSON/JSONB types automatically deserialize to dict
        if isinstance(self.fixture_data, dict):
            return self.fixture_data
        elif isinstance(self.fixture_data, str):
            # Fallback for any edge cases where it's still a string
            try:
                return json.loads(self.fixture_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        else:
            return {}

