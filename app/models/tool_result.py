"""
Database model for storing full tool results to prevent truncation.
"""
from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.sql import func

from app.core.database import Base


class ToolResult(Base):
    """Model for storing full tool results."""
    __tablename__ = "tool_results"

    id = Column(Integer, primary_key=True, index=True)
    tool_call_id = Column(String, index=True, nullable=False, unique=True)
    session_id = Column(String, index=True, nullable=False)
    tool_name = Column(String, index=True, nullable=False)
    full_result = Column(Text, nullable=False)  # Store full result as text
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ToolResult(tool_call_id='{self.tool_call_id}', tool_name='{self.tool_name}', session_id='{self.session_id}')>"

