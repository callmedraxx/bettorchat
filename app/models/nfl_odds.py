"""
NFL Odds database model for storing odds data from OpticOdds API.
This model stores all odds entries with comprehensive indexes for fast querying.
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, DateTime, Integer, Float, Boolean, JSON,
    Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

# Use JSONB for PostgreSQL, JSON for SQLite
if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
    OddsDataType = JSONB
else:
    OddsDataType = JSON  # SQLite supports JSON type in SQLAlchemy


class NFLOdds(Base):
    """NFL Odds model for storing odds entries from OpticOdds API."""
    
    __tablename__ = "nfl_odds"
    
    __table_args__ = (
        UniqueConstraint('id', name='uq_nfl_odds_id'),
        # Comprehensive indexes for fast querying
        Index('idx_nfl_odds_id', 'id'),
        Index('idx_nfl_odds_fixture_id', 'fixture_id'),
        Index('idx_nfl_odds_sportsbook', 'sportsbook'),
        Index('idx_nfl_odds_market_id', 'market_id'),
        Index('idx_nfl_odds_market', 'market'),
        Index('idx_nfl_odds_player_id', 'player_id'),
        Index('idx_nfl_odds_team_id', 'team_id'),
        Index('idx_nfl_odds_selection', 'selection'),
        Index('idx_nfl_odds_normalized_selection', 'normalized_selection'),
        Index('idx_nfl_odds_price', 'price'),
        Index('idx_nfl_odds_timestamp', 'timestamp'),
        Index('idx_nfl_odds_is_main', 'is_main'),
        Index('idx_nfl_odds_points', 'points'),
        Index('idx_nfl_odds_created_at', 'created_at'),
        Index('idx_nfl_odds_updated_at', 'updated_at'),
        # Composite indexes for common queries
        Index('idx_nfl_odds_fixture_sportsbook', 'fixture_id', 'sportsbook'),
        Index('idx_nfl_odds_fixture_market', 'fixture_id', 'market_id'),
        Index('idx_nfl_odds_sportsbook_market', 'sportsbook', 'market_id'),
        Index('idx_nfl_odds_fixture_team', 'fixture_id', 'team_id'),
        Index('idx_nfl_odds_fixture_player', 'fixture_id', 'player_id'),
        Index('idx_nfl_odds_team_market', 'team_id', 'market_id'),
        Index('idx_nfl_odds_player_market', 'player_id', 'market_id'),
        Index('idx_nfl_odds_fixture_sportsbook_market', 'fixture_id', 'sportsbook', 'market_id'),
        Index('idx_nfl_odds_sportsbook_market_selection', 'sportsbook', 'market_id', 'normalized_selection'),
        # Additional indexes for market category queries
        Index('idx_nfl_odds_market_category', 'market_category'),
        Index('idx_nfl_odds_fixture_market_category', 'fixture_id', 'market_category'),
        Index('idx_nfl_odds_sportsbook_market_category', 'sportsbook', 'market_category'),
        Index('idx_nfl_odds_fixture_sportsbook_market_category', 'fixture_id', 'sportsbook', 'market_category'),
        Index('idx_nfl_odds_team_market_category', 'team_id', 'market_category'),
        Index('idx_nfl_odds_player_market_category', 'player_id', 'market_category'),
        Index('idx_nfl_odds_fixture_team_market_category', 'fixture_id', 'team_id', 'market_category'),
        Index('idx_nfl_odds_fixture_player_market_category', 'fixture_id', 'player_id', 'market_category'),
    )
    
    # Primary key
    db_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # OpticOdds odds identifier (unique)
    id = Column(String(500), nullable=False, unique=True, index=True, comment="Odds ID from OpticOdds API")
    
    # Foreign key to fixture
    fixture_id = Column(String(255), nullable=False, index=True, comment="Fixture ID from OpticOdds API")
    
    # Sportsbook information
    sportsbook = Column(String(100), nullable=True, index=True, comment="Sportsbook name (e.g., BetMGM, FanDuel)")
    
    # Market information
    market = Column(String(255), nullable=True, index=True, comment="Market name (e.g., Moneyline, Point Spread)")
    market_id = Column(String(255), nullable=True, index=True, comment="Market ID (e.g., moneyline, point_spread)")
    market_category = Column(String(100), nullable=True, index=True, comment="Market category (e.g., moneyline, spread, total, player_prop, team_total)")
    
    # Selection information
    name = Column(String(500), nullable=True, comment="Full name of the selection")
    selection = Column(String(255), nullable=True, index=True, comment="Selection (e.g., team name, player name)")
    normalized_selection = Column(String(255), nullable=True, index=True, comment="Normalized selection name")
    selection_line = Column(String(100), nullable=True, comment="Selection line (e.g., +3.5, Over 45.5)")
    
    # Entity references
    player_id = Column(String(255), nullable=True, index=True, comment="Player ID if this is a player prop")
    team_id = Column(String(255), nullable=True, index=True, comment="Team ID if this is a team-based bet")
    
    # Odds information
    price = Column(Integer, nullable=True, index=True, comment="Odds price (e.g., -110, +150)")
    points = Column(Float, nullable=True, index=True, comment="Points/spread value (e.g., -3.5, 45.5)")
    is_main = Column(Boolean, default=False, index=True, comment="Whether this is the main line")
    
    # Metadata
    timestamp = Column(Float, nullable=True, index=True, comment="Timestamp when odds were last updated")
    grouping_key = Column(String(255), nullable=True, comment="Grouping key for related odds")
    
    # Full odds data stored as JSON/JSONB
    odds_data = Column(OddsDataType, nullable=False, comment="Complete odds entry data as JSON from OpticOdds API")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True, comment="Timestamp when odds were first stored")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True, comment="Timestamp when odds were last updated")
    
    @staticmethod
    def get_market_category(market_id: Optional[str]) -> Optional[str]:
        """
        Categorize market_id into a market category for easier querying.
        
        Args:
            market_id: Market ID from OpticOdds API
            
        Returns:
            Market category string (e.g., 'moneyline', 'spread', 'total', 'player_prop', 'team_total')
        """
        if not market_id:
            return None
        
        market_id_lower = market_id.lower()
        
        # Main game markets
        if 'moneyline' in market_id_lower:
            return 'moneyline'
        elif 'point_spread' in market_id_lower or 'spread' in market_id_lower:
            return 'spread'
        elif 'total_points' in market_id_lower or 'total' in market_id_lower:
            if 'team_total' in market_id_lower:
                return 'team_total'
            return 'total'
        elif 'team_total' in market_id_lower:
            return 'team_total'
        # Player props
        elif market_id_lower.startswith('player_') or 'player_' in market_id_lower:
            return 'player_prop'
        # Anytime/First/Last touchdown scorer
        elif 'touchdown_scorer' in market_id_lower or 'td_scorer' in market_id_lower:
            return 'player_prop'
        # Quarter/Half specific markets
        elif 'quarter' in market_id_lower or 'half' in market_id_lower:
            if 'moneyline' in market_id_lower:
                return 'moneyline'
            elif 'point_spread' in market_id_lower or 'spread' in market_id_lower:
                return 'spread'
            elif 'total' in market_id_lower:
                if 'team_total' in market_id_lower:
                    return 'team_total'
                return 'total'
        
        return 'other'
    
    def __repr__(self):
        return f"<NFLOdds(id={self.id}, fixture_id={self.fixture_id}, sportsbook={self.sportsbook}, market={self.market_id})>"
    
    def to_dict(self):
        """Convert odds entry to dictionary matching OpticOdds API format."""
        # SQLAlchemy's JSON/JSONB types automatically deserialize to dict
        if isinstance(self.odds_data, dict):
            return self.odds_data
        elif isinstance(self.odds_data, str):
            # Fallback for any edge cases where it's still a string
            try:
                return json.loads(self.odds_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        else:
            return {}

