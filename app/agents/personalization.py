"""
User personalization system for sports betting agent.
"""
import json
from typing import Dict, Any, Optional
from pathlib import Path


def get_user_preferences_path(user_id: str) -> str:
    """Get path for user preferences in memory filesystem."""
    return f"/memories/user_preferences/{user_id}/preferences.json"


def get_betting_history_path(user_id: str) -> str:
    """Get path for betting history in memory filesystem."""
    return f"/memories/user_preferences/{user_id}/betting_history.json"


def get_communication_style_path(user_id: str) -> str:
    """Get path for communication style in memory filesystem."""
    return f"/memories/user_preferences/{user_id}/communication_style.json"


def load_user_preferences(user_id: str, read_file_func) -> Dict[str, Any]:
    """Load user preferences from persistent storage.
    
    Args:
        user_id: User identifier
        read_file_func: Function to read file (from agent's filesystem tools)
    
    Returns:
        Dictionary with user preferences
    """
    try:
        path = get_user_preferences_path(user_id)
        content = read_file_func(path)
        if content and not content.startswith("Error"):
            return json.loads(content)
    except Exception:
        pass
    
    # Return default preferences
    return {
        "favorite_teams": [],
        "favorite_players": [],
        "preferred_sportsbooks": [],
        "betting_style": "moderate",  # conservative, moderate, aggressive
        "preferred_markets": [],  # moneyline, spread, total, props, etc.
        "timezone": "America/New_York",  # Default to EST/EDT
        "location": None,  # {"city": str, "region": str, "country": str, "timezone": str}
    }


def save_user_preferences(user_id: str, preferences: Dict[str, Any], write_file_func) -> bool:
    """Save user preferences to persistent storage.
    
    Args:
        user_id: User identifier
        preferences: Dictionary with user preferences
        write_file_func: Function to write file (from agent's filesystem tools)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        path = get_user_preferences_path(user_id)
        content = json.dumps(preferences, indent=2)
        write_file_func(path, content)
        return True
    except Exception:
        return False


def load_betting_history(user_id: str, read_file_func) -> list:
    """Load betting history from persistent storage.
    
    Args:
        user_id: User identifier
        read_file_func: Function to read file (from agent's filesystem tools)
    
    Returns:
        List of betting history entries
    """
    try:
        path = get_betting_history_path(user_id)
        content = read_file_func(path)
        if content and not content.startswith("Error"):
            return json.loads(content)
    except Exception:
        pass
    
    return []


def save_betting_history(user_id: str, history: list, write_file_func) -> bool:
    """Save betting history to persistent storage.
    
    Args:
        user_id: User identifier
        history: List of betting history entries
        write_file_func: Function to write file (from agent's filesystem tools)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        path = get_betting_history_path(user_id)
        content = json.dumps(history, indent=2)
        write_file_func(path, content)
        return True
    except Exception:
        return False


def add_betting_entry(user_id: str, entry: Dict[str, Any], read_file_func, write_file_func) -> bool:
    """Add a new entry to betting history.
    
    Args:
        user_id: User identifier
        entry: Betting entry dictionary
        read_file_func: Function to read file
        write_file_func: Function to write file
    
    Returns:
        True if successful, False otherwise
    """
    history = load_betting_history(user_id, read_file_func)
    history.append(entry)
    return save_betting_history(user_id, history, write_file_func)


def load_communication_style(user_id: str, read_file_func) -> Dict[str, Any]:
    """Load communication style preferences from persistent storage.
    
    Args:
        user_id: User identifier
        read_file_func: Function to read file (from agent's filesystem tools)
    
    Returns:
        Dictionary with communication style preferences
    """
    try:
        path = get_communication_style_path(user_id)
        content = read_file_func(path)
        if content and not content.startswith("Error"):
            return json.loads(content)
    except Exception:
        pass
    
    # Return default communication style
    return {
        "tone": "professional",  # casual, professional, friendly
        "detail_level": "moderate",  # brief, moderate, detailed
        "include_statistics": True,
        "include_recommendations": True,
    }


def save_communication_style(user_id: str, style: Dict[str, Any], write_file_func) -> bool:
    """Save communication style preferences to persistent storage.
    
    Args:
        user_id: User identifier
        style: Dictionary with communication style preferences
        write_file_func: Function to write file (from agent's filesystem tools)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        path = get_communication_style_path(user_id)
        content = json.dumps(style, indent=2)
        write_file_func(path, content)
        return True
    except Exception:
        return False


def get_user_timezone(user_id: str, read_file_func) -> Optional[str]:
    """Get user's timezone from preferences.
    
    Args:
        user_id: User identifier
        read_file_func: Function to read file (from agent's filesystem tools)
    
    Returns:
        Timezone string (e.g., "America/New_York") or None if not set
    """
    preferences = load_user_preferences(user_id, read_file_func)
    return preferences.get("timezone")


def get_personalization_context(user_id: str, read_file_func) -> str:
    """Get formatted personalization context for agent system prompt.
    
    Args:
        user_id: User identifier
        read_file_func: Function to read file (from agent's filesystem tools)
    
    Returns:
        Formatted string with personalization context
    """
    preferences = load_user_preferences(user_id, read_file_func)
    style = load_communication_style(user_id, read_file_func)
    history = load_betting_history(user_id, read_file_func)
    
    context_parts = []
    
    if preferences.get("favorite_teams"):
        context_parts.append(f"Favorite teams: {', '.join(preferences['favorite_teams'])}")
    if preferences.get("favorite_players"):
        context_parts.append(f"Favorite players: {', '.join(preferences['favorite_players'])}")
    if preferences.get("preferred_sportsbooks"):
        context_parts.append(f"Preferred sportsbooks: {', '.join(preferences['preferred_sportsbooks'])}")
    if preferences.get("betting_style"):
        context_parts.append(f"Betting style: {preferences['betting_style']}")
    if preferences.get("timezone"):
        context_parts.append(f"Timezone: {preferences['timezone']}")
    if preferences.get("location"):
        loc = preferences["location"]
        if isinstance(loc, dict):
            city = loc.get("city", "")
            region = loc.get("region", "")
            country = loc.get("country", "")
            if city or region or country:
                location_str = ", ".join(filter(None, [city, region, country]))
                context_parts.append(f"Location: {location_str}")
    
    if style.get("tone"):
        context_parts.append(f"Communication tone: {style['tone']}")
    if style.get("detail_level"):
        context_parts.append(f"Detail level: {style['detail_level']}")
    
    if history:
        context_parts.append(f"Betting history: {len(history)} previous bets")
    
    return "\n".join(context_parts) if context_parts else "No personalization data available"

