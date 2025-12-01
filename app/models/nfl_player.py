"""
Database model for storing NFL players.
Optimized for fast team-to-player lookups using PostgreSQL indexes.
"""
from sqlalchemy import Column, String, Integer, Boolean, Numeric, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

# Use JSONB for PostgreSQL, JSON for SQLite
from sqlalchemy import JSON
if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
    PlayerDataType = JSONB
else:
    PlayerDataType = JSON


class NFLPlayer(Base):
    """
    Model for storing NFL players with fast team-to-player lookups.
    
    Indexes are optimized for:
    - Fast team_id lookups (hashmap-like performance)
    - Name searches with team filtering
    - Active player queries
    """
    __tablename__ = "nfl_players"

    # Primary key - player ID from OpticOdds API
    id = Column(String, primary_key=True, index=True)
    
    # Player identification
    name = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    # Player details
    position = Column(String, nullable=True, index=True)
    number = Column(Integer, nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)  # Height in inches
    weight = Column(Integer, nullable=True)  # Weight in pounds
    experience = Column(String, nullable=True)
    
    # Team relationship - CRITICAL for fast lookups
    team_id = Column(String, nullable=False, index=True)  # Team ID from nfl_teams
    team_name = Column(String, nullable=True)  # Denormalized for faster queries
    
    # Status and IDs
    is_active = Column(Boolean, default=True, index=True)
    numerical_id = Column(Integer, nullable=True)
    base_id = Column(Integer, nullable=True)
    
    # Media
    logo = Column(Text, nullable=True)  # Logo URL
    
    # Metadata stored as JSONB for flexibility
    source_ids = Column(PlayerDataType, nullable=True)
    extra_data = Column(PlayerDataType, nullable=True)  # For any additional fields (metadata is reserved in SQLAlchemy)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Composite indexes for common query patterns
    # These provide hashmap-like performance for team-to-player lookups
    __table_args__ = (
        # Fast lookup: Get all players for a team
        Index('idx_players_team_id', 'team_id'),
        # Fast lookup: Get active players for a team
        Index('idx_players_team_active', 'team_id', 'is_active'),
        # Fast lookup: Get players by team and position
        Index('idx_players_team_position', 'team_id', 'position'),
        # Fast lookup: Search by name within a team
        Index('idx_players_team_name', 'team_id', 'name'),
        # Fast lookup: Get active players by position
        Index('idx_players_active_position', 'is_active', 'position'),
    )

    def __repr__(self):
        return f"<NFLPlayer(id='{self.id}', name='{self.name}', team_id='{self.team_id}')>"

