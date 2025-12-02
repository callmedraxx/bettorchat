"""
Timezone utility functions for converting timestamps to EST.
All timestamps are stored in UTC in the database, but converted to EST
for frontend and agent responses to avoid confusion.
"""
from datetime import datetime
from typing import Optional, Any, Dict, List
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


def convert_to_est(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert datetime to EST timezone.
    
    Args:
        dt: Datetime object (can be None, timezone-aware or timezone-naive)
        
    Returns:
        Datetime in EST timezone, or None if input is None
    """
    if dt is None:
        return None
    
    # If timezone-naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    
    # Convert to EST
    return dt.astimezone(ZoneInfo("America/New_York"))


def convert_dict_timestamps_to_est(data: Dict[str, Any], timestamp_fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convert timestamp fields in a dictionary to EST.
    
    Args:
        data: Dictionary containing timestamp fields
        timestamp_fields: List of field names to convert. If None, uses default fields.
        
    Returns:
        Dictionary with timestamp fields converted to EST
    """
    if not isinstance(data, dict):
        return data
    
    if timestamp_fields is None:
        timestamp_fields = [
            "start_date",
            "timestamp",
            "created_at",
            "updated_at",
            "odds_timestamp"
        ]
    
    result = data.copy()
    
    for field in timestamp_fields:
        if field in result and result[field] is not None:
            value = result[field]
            
            # Handle string timestamps (ISO format)
            if isinstance(value, str):
                try:
                    # Try parsing ISO format
                    if value.endswith("Z"):
                        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    else:
                        dt = datetime.fromisoformat(value)
                    result[field] = convert_to_est(dt).isoformat()
                except (ValueError, AttributeError):
                    # If parsing fails, leave as-is
                    pass
            # Handle datetime objects
            elif isinstance(value, datetime):
                result[field] = convert_to_est(value)
            # Handle numeric timestamps (Unix timestamp)
            elif isinstance(value, (int, float)):
                try:
                    dt = datetime.fromtimestamp(value, tz=ZoneInfo("UTC"))
                    result[field] = convert_to_est(dt).isoformat()
                except (ValueError, OSError):
                    # If conversion fails, leave as-is
                    pass
    
    return result


def convert_list_timestamps_to_est(data_list: List[Dict[str, Any]], timestamp_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Convert timestamp fields in a list of dictionaries to EST.
    
    Args:
        data_list: List of dictionaries containing timestamp fields
        timestamp_fields: List of field names to convert. If None, uses default fields.
        
    Returns:
        List of dictionaries with timestamp fields converted to EST
    """
    return [convert_dict_timestamps_to_est(item, timestamp_fields) for item in data_list]

