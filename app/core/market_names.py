"""
Market name mapping for translating user-friendly terms to correct API market names.

This module provides mappings from common user requests (e.g., "total points", "spread") 
to the exact market names required by the OpticOdds API (e.g., "Total Points", "Point Spread").
"""

# Market name mappings: user-friendly term -> correct API market name
MARKET_NAME_MAPPINGS = {
    # Main game markets
    "total": "Total Points",
    "total points": "Total Points",
    "over under": "Total Points",
    "over/under": "Total Points",
    "o/u": "Total Points",
    "points total": "Total Points",
    "game total": "Total Points",
    
    "spread": "Point Spread",
    "point spread": "Point Spread",
    "line": "Point Spread",
    "handicap": "Point Spread",
    
    "moneyline": "Moneyline",
    "ml": "Moneyline",
    "winner": "Moneyline",
    "outright": "Moneyline",
    
    # Player prop markets
    "player points": "Player Points",
    "player receptions": "Player Receptions",
    "player receiving yards": "Player Receiving Yards",
    "player rushing yards": "Player Rushing Yards",
    "player passing yards": "Player Passing Yards",
    "player touchdowns": "Player Touchdowns",
    "player passing touchdowns": "Player Passing Touchdowns",
    "player rushing touchdowns": "Player Rushing Touchdowns",
    "player receiving touchdowns": "Player Receiving Touchdowns",
    "player rushing attempts": "Player Rushing Attempts",
    "player passing attempts": "Player Passing Attempts",
    "player passing completions": "Player Passing Completions",
    "player interceptions": "Player Interceptions",
    "player sacks": "Player Sacks",
    "anytime touchdown": "Anytime Touchdown Scorer",
    "anytime td": "Anytime Touchdown Scorer",
    "first touchdown": "First Touchdown Scorer",
    "first td": "First Touchdown Scorer",
    "last touchdown": "Last Touchdown Scorer",
    "last td": "Last Touchdown Scorer",
    
    # Team markets
    "team total": "Team Total",
    "team total points": "Team Total",
    "team total touchdowns": "Team Total Touchdowns",
    
    # Quarter/Half markets
    "1st quarter total": "1st Quarter Total Points",
    "first quarter total": "1st Quarter Total Points",
    "1st quarter spread": "1st Quarter Point Spread",
    "first quarter spread": "1st Quarter Point Spread",
    "1st quarter moneyline": "1st Quarter Moneyline",
    "first quarter moneyline": "1st Quarter Moneyline",
    
    "1st half total": "1st Half Total Points",
    "first half total": "1st Half Total Points",
    "1st half spread": "1st Half Point Spread",
    "first half spread": "1st Half Point Spread",
    "1st half moneyline": "1st Half Moneyline",
    "first half moneyline": "1st Half Moneyline",
    
    "2nd quarter total": "2nd Quarter Total Points",
    "second quarter total": "2nd Quarter Total Points",
    "2nd half total": "2nd Half Total Points",
    "second half total": "2nd Half Total Points",
    
    # Other markets
    "total touchdowns": "Total Touchdowns",
    "correct score": "Correct Score",
    "first team to score": "First Team To Score",
    "last team to score": "Last Team To Score",
    "overtime": "Will There Be Overtime",
    "will there be overtime": "Will There Be Overtime",
}

# Reverse mapping: API market name -> common aliases (for reference)
API_MARKET_NAMES = {
    "Total Points": ["total", "total points", "over under", "o/u", "game total"],
    "Point Spread": ["spread", "line", "handicap"],
    "Moneyline": ["moneyline", "ml", "winner", "outright"],
    "Player Points": ["player points"],
    "Player Receptions": ["player receptions"],
    "Player Receiving Yards": ["player receiving yards"],
    "Player Rushing Yards": ["player rushing yards"],
    "Player Passing Yards": ["player passing yards"],
    "Player Touchdowns": ["player touchdowns"],
    "Anytime Touchdown Scorer": ["anytime touchdown", "anytime td"],
    "First Touchdown Scorer": ["first touchdown", "first td"],
    "Team Total": ["team total", "team total points"],
    "Total Touchdowns": ["total touchdowns"],
}

# All valid API market names (from the provided JSON)
VALID_MARKET_NAMES = {
    "1st Drive Player Receptions",
    "1st Drive Player Touchdowns",
    "1st Half Anytime Touchdown Scorer",
    "1st Half Correct Score",
    "1st Half Last Team To Score",
    "1st Half Moneyline",
    "1st Half Moneyline 3-Way",
    "1st Half Player Touchdowns",
    "1st Half Point Spread",
    "1st Half Team Total",
    "1st Half Team Total Touchdowns",
    "1st Half Total Points",
    "1st Half Total Points Odd/Even",
    "1st Half Total Touchdowns",
    "1st Quarter Both Teams To Score",
    "1st Quarter Correct Score",
    "1st Quarter Moneyline",
    "1st Quarter Moneyline 3-Way",
    "1st Quarter Player Passing Yards",
    "1st Quarter Player Receiving Yards",
    "1st Quarter Player Rushing + Receiving Yards",
    "1st Quarter Player Rushing Yards",
    "1st Quarter Point Spread",
    "1st Quarter Total Points",
    "1st Quarter Total Points Odd/Even",
    "1st Quarter Total Touchdowns",
    "2nd Half Anytime Touchdown Scorer",
    "2nd Half Moneyline",
    "2nd Half Player Touchdowns",
    "2nd Half Point Spread",
    "2nd Half Team Total",
    "2nd Half Total Points",
    "2nd Half Total Points Odd/Even",
    "2nd Quarter Both Teams To Score",
    "2nd Quarter Moneyline",
    "2nd Quarter Moneyline 3-Way",
    "2nd Quarter Point Spread",
    "2nd Quarter Total Points",
    "3rd Quarter Both Teams To Score",
    "3rd Quarter Moneyline",
    "3rd Quarter Moneyline 3-Way",
    "3rd Quarter Point Spread",
    "3rd Quarter Total Points",
    "4th Quarter Both Teams To Score",
    "4th Quarter Moneyline",
    "4th Quarter Moneyline 3-Way",
    "4th Quarter Point Spread",
    "4th Quarter Total Points",
    "Anytime Touchdown Scorer",
    "Correct Score",
    "Defensive Anytime Touchdown Scorer",
    "First Team To Score",
    "First Touchdown Scorer",
    "Last Team To Score",
    "Last Touchdown Scorer",
    "Moneyline",
    "Most Passing Yards Player",
    "Most Rushing Yards Player",
    "Player Defensive Interceptions",
    "Player Interceptions",
    "Player Longest Passing Completion",
    "Player Longest Reception",
    "Player Longest Rush",
    "Player Passing + Rushing Yards",
    "Player Passing Attempts",
    "Player Passing Completions",
    "Player Passing Touchdowns",
    "Player Passing Yards",
    "Player Passing Yards Each Half",
    "Player Passing Yards Each Quarter",
    "Player Receiving Yards",
    "Player Receiving Yards Each Half",
    "Player Receiving Yards Each Quarter",
    "Player Receptions",
    "Player Rushing + Receiving Yards",
    "Player Rushing Attempts",
    "Player Rushing Yards",
    "Player Rushing Yards Each Half",
    "Player Rushing Yards Each Quarter",
    "Player Sacks",
    "Player Touchdowns",
    "Point Spread",
    "Team Total",
    "Team Total Touchdowns",
    "Total Points",
    "Total Points Odd/Even",
    "Total Touchdowns",
    "Will There Be Overtime",
}


def resolve_market_name(user_input: str) -> str:
    """
    Resolve a user-friendly market name to the correct API market name.
    
    Args:
        user_input: User-provided market name (e.g., "total points", "spread")
    
    Returns:
        Correct API market name (e.g., "Total Points", "Point Spread")
        Returns the input unchanged if no mapping found (assumes it's already correct)
    """
    if not user_input:
        return user_input
    
    # Normalize input: lowercase, strip whitespace
    normalized = user_input.lower().strip()
    
    # Check direct mapping
    if normalized in MARKET_NAME_MAPPINGS:
        return MARKET_NAME_MAPPINGS[normalized]
    
    # Check if input is already a valid API market name (case-insensitive)
    for valid_name in VALID_MARKET_NAMES:
        if valid_name.lower() == normalized:
            return valid_name
    
    # If no mapping found, return original (might already be correct)
    return user_input


def resolve_market_names(markets: str) -> str:
    """
    Resolve multiple market names (comma-separated) to correct API market names.
    
    Args:
        markets: Comma-separated market names (e.g., "total points,spread,moneyline")
    
    Returns:
        Comma-separated resolved market names (e.g., "Total Points,Point Spread,Moneyline")
    """
    if not markets:
        return markets
    
    # Split by comma and resolve each
    market_list = [m.strip() for m in markets.split(",") if m.strip()]
    resolved = [resolve_market_name(m) for m in market_list]
    
    # Join back with comma
    return ",".join(resolved)


def is_valid_market_name(market_name: str) -> bool:
    """
    Check if a market name is a valid API market name.
    
    Args:
        market_name: Market name to check
    
    Returns:
        True if the market name is valid, False otherwise
    """
    if not market_name:
        return False
    
    # Check case-insensitive match against valid names
    normalized = market_name.strip()
    for valid_name in VALID_MARKET_NAMES:
        if valid_name.lower() == normalized.lower():
            return True
    
    return False

