"""
Database operations for storing and retrieving full tool results.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.tool_result import ToolResult

logger = logging.getLogger(__name__)


def save_tool_result_to_db(
    tool_call_id: str,
    session_id: str,
    tool_name: str,
    full_result: str
) -> bool:
    """
    Save full tool result to database.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        session_id: Session identifier
        tool_name: Name of the tool
        full_result: Full result string
        
    Returns:
        True if saved successfully, False otherwise
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        try:
            # Check if result already exists
            existing = db.query(ToolResult).filter(
                ToolResult.tool_call_id == tool_call_id
            ).first()
            
            if existing:
                # Update existing record
                existing.full_result = full_result
                existing.session_id = session_id
                existing.tool_name = tool_name
                logger.debug(f"[ToolResultDB] Updated tool result for tool_call_id={tool_call_id}")
            else:
                # Create new record
                tool_result = ToolResult(
                    tool_call_id=tool_call_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    full_result=full_result
                )
                db.add(tool_result)
                logger.debug(f"[ToolResultDB] Created tool result for tool_call_id={tool_call_id}, size={len(full_result)}")
            
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            # Try to update if duplicate
            existing = db.query(ToolResult).filter(
                ToolResult.tool_call_id == tool_call_id
            ).first()
            if existing:
                existing.full_result = full_result
                existing.session_id = session_id
                existing.tool_name = tool_name
                db.commit()
                logger.debug(f"[ToolResultDB] Updated tool result after IntegrityError for tool_call_id={tool_call_id}")
                return True
            raise
    except Exception as e:
        logger.error(f"[ToolResultDB] Error saving tool result: {e}", exc_info=True)
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()


def get_tool_result_from_db(tool_call_id: str) -> Optional[str]:
    """
    Retrieve full tool result from database.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        
    Returns:
        Full result string or None if not found
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        tool_result = db.query(ToolResult).filter(
            ToolResult.tool_call_id == tool_call_id
        ).first()
        
        if tool_result:
            logger.debug(f"[ToolResultDB] Retrieved tool result for tool_call_id={tool_call_id}, size={len(tool_result.full_result)}")
            return tool_result.full_result
        else:
            logger.debug(f"[ToolResultDB] No tool result found for tool_call_id={tool_call_id}")
            return None
    except Exception as e:
        logger.error(f"[ToolResultDB] Error retrieving tool result: {e}", exc_info=True)
        return None
    finally:
        if db:
            db.close()


def cleanup_old_tool_results(days_old: int = 7) -> int:
    """
    Clean up old tool results from database.
    
    Args:
        days_old: Delete results older than this many days
        
    Returns:
        Number of records deleted
    """
    db: Optional[Session] = None
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        db = SessionLocal()
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        deleted = db.query(ToolResult).filter(
            ToolResult.created_at < cutoff_date
        ).delete()
        
        db.commit()
        logger.info(f"[ToolResultDB] Cleaned up {deleted} old tool results")
        return deleted
    except Exception as e:
        logger.error(f"[ToolResultDB] Error cleaning up tool results: {e}", exc_info=True)
        if db:
            db.rollback()
        return 0
    finally:
        if db:
            db.close()

