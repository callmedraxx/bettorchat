"""
Database model for storing full tool results to prevent truncation.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings

# Use JSONB for PostgreSQL, JSON for SQLite
if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
    StructuredDataType = JSONB
else:
    StructuredDataType = JSON


class ToolResult(Base):
    """Model for storing full tool results with structured data for querying."""
    __tablename__ = "tool_results"

    id = Column(Integer, primary_key=True, index=True)
    tool_call_id = Column(String, index=True, nullable=False, unique=True)
    session_id = Column(String, index=True, nullable=False)
    tool_name = Column(String, index=True, nullable=False)
    full_result = Column(Text, nullable=False)  # Store full result as text (for chat stream)
    structured_data = Column(StructuredDataType, nullable=True)  # Store structured JSON for querying
    # Common fields extracted for fast lookups
    fixture_id = Column(String, index=True, nullable=True)
    team_id = Column(String, index=True, nullable=True)
    player_id = Column(String, index=True, nullable=True)
    league_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ToolResult(tool_call_id='{self.tool_call_id}', tool_name='{self.tool_name}', session_id='{self.session_id}')>"

