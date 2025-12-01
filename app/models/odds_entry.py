"""
Database model for storing individual odds entries in a normalized structure.
This allows efficient querying and filtering of large odds datasets.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

# Use JSONB for PostgreSQL, JSON for SQLite
from sqlalchemy import JSON
if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
    OddsDataType = JSONB
else:
    OddsDataType = JSON


class OddsEntry(Base):
    """Model for storing individual odds entries for efficient querying and chunked retrieval."""
    __tablename__ = "odds_entries"

    id = Column(Integer, primary_key=True, index=True)
    # Reference to tool_result that stored this odds data
    tool_call_id = Column(String, index=True, nullable=False)
    session_id = Column(String, index=True, nullable=False)
    
    # Fixture information
    fixture_id = Column(String, index=True, nullable=False)
    fixture_numerical_id = Column(Integer, index=True, nullable=True)
    
    # Odds entry details
    odds_entry_id = Column(String, index=True, nullable=False)  # Unique ID from API
    sportsbook = Column(String, index=True, nullable=False)
    market = Column(String, index=True, nullable=False)
    market_id = Column(String, index=True, nullable=True)
    selection = Column(String, nullable=False)
    selection_name = Column(String, nullable=True)
    normalized_selection = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)  # American odds price
    is_main = Column(String, nullable=True)  # Store as string for flexibility
    
    # Related entities
    player_id = Column(String, index=True, nullable=True)
    team_id = Column(String, index=True, nullable=True)
    selection_line = Column(String, nullable=True)  # e.g., "+2.5", "Over 49.5"
    points = Column(Numeric(10, 2), nullable=True)
    
    # Full odds entry data as JSONB for complete details
    full_entry_data = Column(OddsDataType, nullable=True)
    
    # Timestamps
    odds_timestamp = Column(Numeric(20, 6), nullable=True)  # Timestamp from API (Unix timestamp with microseconds)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_odds_fixture_sportsbook', 'fixture_id', 'sportsbook'),
        Index('idx_odds_fixture_market', 'fixture_id', 'market'),
        Index('idx_odds_fixture_market_sportsbook', 'fixture_id', 'market', 'sportsbook'),
        Index('idx_odds_session_fixture', 'session_id', 'fixture_id'),
    )

    def __repr__(self):
        return f"<OddsEntry(fixture_id='{self.fixture_id}', sportsbook='{self.sportsbook}', market='{self.market}', selection='{self.selection}')>"

