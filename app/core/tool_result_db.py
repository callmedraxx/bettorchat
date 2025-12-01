"""
Database operations for storing and retrieving full tool results.
"""
import logging
import json
from typing import Optional, Dict, Any, List, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.tool_result import ToolResult

logger = logging.getLogger(__name__)


def extract_common_fields(structured_data: Union[Dict, List, None]) -> Dict[str, Optional[str]]:
    """
    Extract common fields (fixture_id, team_id, player_id, league_id) from structured data.
    
    Args:
        structured_data: Dictionary or list containing structured data
        
    Returns:
        Dictionary with extracted common fields
    """
    fields = {
        "fixture_id": None,
        "team_id": None,
        "player_id": None,
        "league_id": None,
    }
    
    if not structured_data:
        return fields
    
    # Handle list of items (e.g., list of fixtures or odds)
    if isinstance(structured_data, list):
        # Extract from first item if available
        if structured_data and isinstance(structured_data[0], dict):
            item = structured_data[0]
            if "id" in item:
                fields["fixture_id"] = str(item["id"])
            if "fixture_id" in item:
                fields["fixture_id"] = str(item["fixture_id"])
            if "team_id" in item:
                fields["team_id"] = str(item["team_id"])
            if "player_id" in item:
                fields["player_id"] = str(item["player_id"])
            if "league_id" in item:
                fields["league_id"] = str(item["league_id"])
            # Check nested structures
            if "league" in item and isinstance(item["league"], dict):
                if "id" in item["league"]:
                    fields["league_id"] = str(item["league"]["id"])
    elif isinstance(structured_data, dict):
        # Handle API response structure: {"data": [...]}
        if "data" in structured_data and isinstance(structured_data["data"], list):
            return extract_common_fields(structured_data["data"])
        
        # Extract from top-level dict
        if "id" in structured_data:
            fields["fixture_id"] = str(structured_data["id"])
        if "fixture_id" in structured_data:
            fields["fixture_id"] = str(structured_data["fixture_id"])
        if "team_id" in structured_data:
            fields["team_id"] = str(structured_data["team_id"])
        if "player_id" in structured_data:
            fields["player_id"] = str(structured_data["player_id"])
        if "league_id" in structured_data:
            fields["league_id"] = str(structured_data["league_id"])
        
        # Check nested structures
        if "league" in structured_data and isinstance(structured_data["league"], dict):
            if "id" in structured_data["league"]:
                fields["league_id"] = str(structured_data["league"]["id"])
        
        # For odds responses, extract fixture_id from nested fixtures
        if "data" in structured_data:
            data = structured_data["data"]
            if isinstance(data, list) and data:
                first_item = data[0]
                if isinstance(first_item, dict) and "id" in first_item:
                    fields["fixture_id"] = str(first_item["id"])
    
    return fields


def save_tool_result_to_db(
    tool_call_id: str,
    session_id: str,
    tool_name: str,
    full_result: str,
    structured_data: Optional[Union[Dict, List]] = None
) -> bool:
    """
    Save full tool result to database.
    
    Args:
        tool_call_id: Unique identifier for the tool call
        session_id: Session identifier
        tool_name: Name of the tool
        full_result: Full result string (for chat stream compatibility)
        structured_data: Optional structured data (dict/list) for querying. If None, will try to parse from full_result.
        
    Returns:
        True if saved successfully, False otherwise
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        
        # Parse structured_data if not provided
        parsed_structured_data = structured_data
        if parsed_structured_data is None:
            # Try to parse JSON from full_result as fallback
            try:
                parsed_structured_data = json.loads(full_result)
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, structured_data remains None
                parsed_structured_data = None
        
        # Extract common fields from structured data
        common_fields = extract_common_fields(parsed_structured_data) if parsed_structured_data else {}
        
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
                existing.structured_data = parsed_structured_data
                existing.fixture_id = common_fields.get("fixture_id")
                existing.team_id = common_fields.get("team_id")
                existing.player_id = common_fields.get("player_id")
                existing.league_id = common_fields.get("league_id")
                logger.debug(f"[ToolResultDB] Updated tool result for tool_call_id={tool_call_id}")
            else:
                # Create new record
                tool_result = ToolResult(
                    tool_call_id=tool_call_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    full_result=full_result,
                    structured_data=parsed_structured_data,
                    fixture_id=common_fields.get("fixture_id"),
                    team_id=common_fields.get("team_id"),
                    player_id=common_fields.get("player_id"),
                    league_id=common_fields.get("league_id")
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
                existing.structured_data = parsed_structured_data
                existing.fixture_id = common_fields.get("fixture_id")
                existing.team_id = common_fields.get("team_id")
                existing.player_id = common_fields.get("player_id")
                existing.league_id = common_fields.get("league_id")
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


def get_tool_results_by_session(
    session_id: str,
    tool_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve tool results by session_id, optionally filtered by tool_name.
    
    Args:
        session_id: Session identifier
        tool_name: Optional tool name to filter results
        
    Returns:
        List of dictionaries containing structured data from tool results
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        query = db.query(ToolResult).filter(ToolResult.session_id == session_id)
        
        if tool_name:
            query = query.filter(ToolResult.tool_name == tool_name)
        
        results = query.order_by(ToolResult.created_at.desc()).all()
        
        tool_results = []
        for result in results:
            if result.structured_data:
                tool_results.append({
                    "tool_call_id": result.tool_call_id,
                    "tool_name": result.tool_name,
                    "session_id": result.session_id,
                    "structured_data": result.structured_data,
                    "fixture_id": result.fixture_id,
                    "team_id": result.team_id,
                    "player_id": result.player_id,
                    "league_id": result.league_id,
                    "created_at": result.created_at.isoformat() if result.created_at else None
                })
        
        logger.debug(f"[ToolResultDB] Retrieved {len(tool_results)} tool results for session_id={session_id}, tool_name={tool_name}")
        return tool_results
    except Exception as e:
        logger.error(f"[ToolResultDB] Error retrieving tool results by session: {e}", exc_info=True)
        return []
    finally:
        if db:
            db.close()


def get_tool_results_by_fixture_id(
    session_id: str,
    fixture_id: str
) -> List[Dict[str, Any]]:
    """
    Retrieve tool results by fixture_id for a given session.
    
    Args:
        session_id: Session identifier
        fixture_id: Fixture ID to search for
        
    Returns:
        List of dictionaries containing structured data from tool results
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        
        # Query by indexed fixture_id column
        results = db.query(ToolResult).filter(
            ToolResult.session_id == session_id,
            ToolResult.fixture_id == fixture_id
        ).order_by(ToolResult.created_at.desc()).all()
        
        # Also search in structured_data JSON for cases where fixture_id wasn't extracted
        # This is especially useful for PostgreSQL JSONB queries
        from sqlalchemy import or_, cast, String
        from app.core.config import settings
        
        if settings.ENVIRONMENT == "production" and settings.DATABASE_URL and "postgresql" in settings.DATABASE_URL:
            try:
                # PostgreSQL JSONB query - search in nested structures
                # Try to find fixture_id in various locations within the JSON
                from sqlalchemy.dialects.postgresql import JSONB
                
                jsonb_results = db.query(ToolResult).filter(
                    ToolResult.session_id == session_id,
                    ToolResult.structured_data.isnot(None),
                    or_(
                        # Direct fixture_id at top level
                        cast(ToolResult.structured_data['id'], String) == fixture_id,
                        cast(ToolResult.structured_data['fixture_id'], String) == fixture_id,
                        # Search in data array
                        ToolResult.structured_data['data'].op('@>')(json.dumps([{"id": fixture_id}])),
                        ToolResult.structured_data['data'].op('@>')(json.dumps([{"fixture_id": fixture_id}]))
                    )
                ).order_by(ToolResult.created_at.desc()).all()
                
                # Combine results, avoiding duplicates
                result_ids = {r.tool_call_id for r in results}
                for r in jsonb_results:
                    if r.tool_call_id not in result_ids:
                        results.append(r)
            except Exception as jsonb_error:
                # If JSONB query fails, just use the indexed column results
                logger.debug(f"[ToolResultDB] JSONB query failed, using indexed results only: {jsonb_error}")
        
        tool_results = []
        for result in results:
            if result.structured_data:
                tool_results.append({
                    "tool_call_id": result.tool_call_id,
                    "tool_name": result.tool_name,
                    "session_id": result.session_id,
                    "structured_data": result.structured_data,
                    "fixture_id": result.fixture_id,
                    "team_id": result.team_id,
                    "player_id": result.player_id,
                    "league_id": result.league_id,
                    "created_at": result.created_at.isoformat() if result.created_at else None
                })
        
        logger.debug(f"[ToolResultDB] Retrieved {len(tool_results)} tool results for fixture_id={fixture_id}, session_id={session_id}")
        return tool_results
    except Exception as e:
        logger.error(f"[ToolResultDB] Error retrieving tool results by fixture_id: {e}", exc_info=True)
        return []
    finally:
        if db:
            db.close()


def get_tool_results_by_field(
    session_id: str,
    field_name: str,
    field_value: Any
) -> List[Dict[str, Any]]:
    """
    Retrieve tool results by a specific field value.
    
    Args:
        session_id: Session identifier
        field_name: Name of the field to search (fixture_id, team_id, player_id, league_id)
        field_value: Value to search for
        
    Returns:
        List of dictionaries containing structured data from tool results
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        
        # Map field names to column attributes
        field_map = {
            "fixture_id": ToolResult.fixture_id,
            "team_id": ToolResult.team_id,
            "player_id": ToolResult.player_id,
            "league_id": ToolResult.league_id,
        }
        
        if field_name not in field_map:
            logger.warning(f"[ToolResultDB] Unknown field_name: {field_name}")
            return []
        
        column = field_map[field_name]
        results = db.query(ToolResult).filter(
            ToolResult.session_id == session_id,
            column == str(field_value)
        ).order_by(ToolResult.created_at.desc()).all()
        
        tool_results = []
        for result in results:
            if result.structured_data:
                tool_results.append({
                    "tool_call_id": result.tool_call_id,
                    "tool_name": result.tool_name,
                    "session_id": result.session_id,
                    "structured_data": result.structured_data,
                    "fixture_id": result.fixture_id,
                    "team_id": result.team_id,
                    "player_id": result.player_id,
                    "league_id": result.league_id,
                    "created_at": result.created_at.isoformat() if result.created_at else None
                })
        
        logger.debug(f"[ToolResultDB] Retrieved {len(tool_results)} tool results for {field_name}={field_value}, session_id={session_id}")
        return tool_results
    except Exception as e:
        logger.error(f"[ToolResultDB] Error retrieving tool results by field: {e}", exc_info=True)
        return []
    finally:
        if db:
            db.close()


def search_tool_results(
    session_id: str,
    query: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Flexible search for tool results using multiple criteria.
    
    Args:
        session_id: Session identifier
        query: Dictionary with search criteria:
            - tool_name: Optional tool name filter
            - fixture_id: Optional fixture ID filter
            - team_id: Optional team ID filter
            - player_id: Optional player ID filter
            - league_id: Optional league ID filter
            
    Returns:
        List of dictionaries containing structured data from tool results
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        db_query = db.query(ToolResult).filter(ToolResult.session_id == session_id)
        
        # Apply filters
        if query.get("tool_name"):
            db_query = db_query.filter(ToolResult.tool_name == query["tool_name"])
        if query.get("fixture_id"):
            db_query = db_query.filter(ToolResult.fixture_id == str(query["fixture_id"]))
        if query.get("team_id"):
            db_query = db_query.filter(ToolResult.team_id == str(query["team_id"]))
        if query.get("player_id"):
            db_query = db_query.filter(ToolResult.player_id == str(query["player_id"]))
        if query.get("league_id"):
            db_query = db_query.filter(ToolResult.league_id == str(query["league_id"]))
        
        results = db_query.order_by(ToolResult.created_at.desc()).all()
        
        tool_results = []
        for result in results:
            if result.structured_data:
                tool_results.append({
                    "tool_call_id": result.tool_call_id,
                    "tool_name": result.tool_name,
                    "session_id": result.session_id,
                    "structured_data": result.structured_data,
                    "fixture_id": result.fixture_id,
                    "team_id": result.team_id,
                    "player_id": result.player_id,
                    "league_id": result.league_id,
                    "created_at": result.created_at.isoformat() if result.created_at else None
                })
        
        logger.debug(f"[ToolResultDB] Retrieved {len(tool_results)} tool results for query={query}, session_id={session_id}")
        return tool_results
    except Exception as e:
        logger.error(f"[ToolResultDB] Error searching tool results: {e}", exc_info=True)
        return []
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

