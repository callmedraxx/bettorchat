"""
Fixture database model for storing raw fixture data.
"""
import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

# Use JSONB for PostgreSQL, JSON for SQLite
if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
    FixtureDataType = JSONB
else:
    FixtureDataType = JSON


class Fixture(Base):
    """Fixture model for storing raw fixture data tied to session_id."""
    
    __tablename__ = "fixtures"
    
    __table_args__ = (
        UniqueConstraint('session_id', 'fixture_id', name='uq_session_fixture'),
    )
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True, comment="Session identifier (user_id or thread_id)")
    fixture_id = Column(String(255), nullable=False, index=True, comment="Fixture ID from OpticOdds API")
    fixture_data = Column(FixtureDataType, nullable=False, comment="Raw fixture data as JSON")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="Timestamp when fixture was stored")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="Timestamp when fixture was last updated")
    
    def __repr__(self):
        return f"<Fixture(id={self.id}, session_id={self.session_id}, fixture_id={self.fixture_id})>"
    
    def to_dict(self):
        """Convert fixture to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "fixture_id": self.fixture_id,
            "fixture_data": self.fixture_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

