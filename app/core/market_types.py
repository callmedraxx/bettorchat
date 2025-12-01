"""
Market type definitions from OpticOdds API.
This data is embedded in the codebase for fast access without API calls.
"""

MARKET_TYPES = {
    "data": [
        {
            "id": 1,
            "name": "asian_handicap",
            "selections": [
                "{away_team_name} {points}",
                "{home_team_name} {points}"
            ],
            "notes": None
        },
        {
            "id": 2,
            "name": "asian_team_total",
            "selections": [
                "{away_team_name} Over {points}",
                "{away_team_name} Under {points}",
                "{home_team_name} Over {points}",
                "{home_team_name} Under {points}"
            ],
            "notes": None
        },
        {
            "id": 3,
            "name": "asian_total",
            "selections": [
                "Over {points}",
                "Under {points}"
            ],
            "notes": None
        },
        {
            "id": 4,
            "name": "double_chance",
            "selections": [
                "{team1_name} Or {team2_name}",
                "{home_team_name} Or Draw",
                "{away_team_name} Or Draw"
            ],
            "notes": "{team1_name} and {team2_name} are the {home_team_name} and {away_team_name} sorted alphabetically."
        },
        {
            "id": 5,
            "name": "double_team_or_draw",
            "selections": [
                "{away_team_name} :: {away_team_name}",
                "{away_team_name} :: {home_team_name}",
                "{away_team_name} :: Draw",
                "{home_team_name} :: {away_team_name}",
                "{home_team_name} :: {home_team_name}",
                "{home_team_name} :: Draw",
                "Draw :: {away_team_name}",
                "Draw :: {home_team_name}",
                "Draw :: Draw"
            ],
            "notes": None
        },
        {
            "id": 6,
            "name": "correct_score",
            "selections": [
                "{away_team_name} {away_team_score}:{home_team_score}",
                "{home_team_name} {home_team_score}:{away_team_score}",
                "Draw {home_team_score}:{away_team_score}"
            ],
            "notes": None
        },
        {
            "id": 7,
            "name": "moneyline",
            "selections": [
                "{away_team_name}",
                "{home_team_name}"
            ],
            "notes": None
        },
        {
            "id": 8,
            "name": "moneyline_3way",
            "selections": [
                "{away_team_name}",
                "{home_team_name}",
                "Draw"
            ],
            "notes": None
        },
        {
            "id": 9,
            "name": "moneyline_3way_and_total",
            "selections": [
                "{away_team_name} :: Over {points}",
                "{away_team_name} :: Under {points}",
                "{home_team_name} :: Over {points}",
                "{home_team_name} :: Under {points}",
                "Draw :: Over {points}",
                "Draw :: Under {points}"
            ],
            "notes": None
        },
        {
            "id": 10,
            "name": "moneyline_3way_and_yes_no",
            "selections": [
                "{away_team_name} :: No",
                "{away_team_name} :: Yes",
                "{home_team_name} :: No",
                "{home_team_name} :: Yes",
                "Draw :: No",
                "Draw :: Yes"
            ],
            "notes": None
        },
        {
            "id": 11,
            "name": "moneyline_and_total",
            "selections": [
                "{away_team_name} :: Over {points}",
                "{away_team_name} :: Under {points}",
                "{home_team_name} :: Over {points}",
                "{home_team_name} :: Under {points}"
            ],
            "notes": None
        },
        {
            "id": 12,
            "name": "moneyline_and_yes_no",
            "selections": [
                "{away_team_name} :: No",
                "{away_team_name} :: Yes",
                "{home_team_name} :: No",
                "{home_team_name} :: Yes"
            ],
            "notes": None
        },
        {
            "id": 13,
            "name": "odd_even",
            "selections": [
                "Even",
                "Odd"
            ],
            "notes": None
        },
        {
            "id": 14,
            "name": "player_only",
            "selections": [
                "{player_name}"
            ],
            "notes": None
        },
        {
            "id": 15,
            "name": "player_total",
            "selections": [
                "{player_name} Over {points}",
                "{player_name} Under {points}"
            ],
            "notes": None
        },
        {
            "id": 16,
            "name": "player_total_combo",
            "selections": [
                "{player_name_1} + {player_name_2} Over {points}",
                "{player_name_1} + {player_name_2} Under {points}"
            ],
            "notes": "{player_name_1} and {player_name_2} are the two players involved in the bet sorted alphabetically. The player_id will be multiple player IDs separated by a `+`."
        },
        {
            "id": 18,
            "name": "player_golf_hole_score_qualifier",
            "selections": [
                "{player_name} :: Birdie Or Better",
                "{player_name} :: Bogey Or Worse",
                "{player_name} :: Par"
            ],
            "notes": None
        },
        {
            "id": 19,
            "name": "player_yes_no",
            "selections": [
                "{player_name} No",
                "{player_name} Yes"
            ],
            "notes": None
        },
        {
            "id": 20,
            "name": "spread",
            "selections": [
                "{home_team_name} {points}",
                "{away_team_name} {points}"
            ],
            "notes": None
        },
        {
            "id": 21,
            "name": "spread_3way",
            "selections": [
                "{home_team_name} {points}",
                "{away_team_name} {points}",
                "Draw {points}"
            ],
            "notes": None
        },
        {
            "id": 22,
            "name": "team_and_neither",
            "selections": [
                "{home_team_name}",
                "{away_team_name}",
                "Neither"
            ],
            "notes": None
        },
        {
            "id": 23,
            "name": "team_and_period",
            "selections": [
                "{home_team_name} :: 1st Half",
                "{home_team_name} :: 2nd Half",
                "{home_team_name} :: 1st Inning",
                "{home_team_name} :: 2nd Inning",
                "{home_team_name} :: 3rd Inning",
                "{home_team_name} :: 4th Inning",
                "{home_team_name} :: 5th Inning",
                "{home_team_name} :: 6th Inning",
                "{home_team_name} :: 7th Inning",
                "{home_team_name} :: 8th Inning",
                "{home_team_name} :: 9th Inning",
                "{home_team_name} :: 1st Period",
                "{home_team_name} :: 2nd Period",
                "{home_team_name} :: 3rd Period",
                "{home_team_name} :: 1st Quarter",
                "{home_team_name} :: 2nd Quarter",
                "{home_team_name} :: 3rd Quarter",
                "{home_team_name} :: 4th Quarter",
                "{home_team_name} :: Draw",
                "{away_team_name} :: 1st Half",
                "{away_team_name} :: 2nd Half",
                "{away_team_name} :: 1st Inning",
                "{away_team_name} :: 2nd Inning",
                "{away_team_name} :: 3rd Inning",
                "{away_team_name} :: 4th Inning",
                "{away_team_name} :: 5th Inning",
                "{away_team_name} :: 6th Inning",
                "{away_team_name} :: 7th Inning",
                "{away_team_name} :: 8th Inning",
                "{away_team_name} :: 9th Inning",
                "{away_team_name} :: 1st Period",
                "{away_team_name} :: 2nd Period",
                "{away_team_name} :: 3rd Period",
                "{away_team_name} :: 1st Quarter",
                "{away_team_name} :: 2nd Quarter",
                "{away_team_name} :: 3rd Quarter",
                "{away_team_name} :: 4th Quarter",
                "{away_team_name} :: Draw"
            ],
            "notes": None
        },
        {
            "id": 24,
            "name": "team_and_player",
            "selections": [
                "{home_team_name} :: {player_name}",
                "{away_team_name} :: {player_name}"
            ],
            "notes": None
        },
        {
            "id": 25,
            "name": "team_odd_even",
            "selections": [
                "{away_team_name} Even",
                "{away_team_name} Odd",
                "{home_team_name} Even",
                "{home_team_name} Odd"
            ],
            "notes": None
        },
        {
            "id": 26,
            "name": "team_or_player",
            "selections": [
                "{away_team_name} D/ST",
                "{away_team_name} Defense",
                "{home_team_name} D/ST",
                "{home_team_name} Defense",
                "{player_name}"
            ],
            "notes": None
        },
        {
            "id": 27,
            "name": "team_total",
            "selections": [
                "{away_team_name} Over {points}",
                "{away_team_name} Under {points}",
                "{home_team_name} Over {points}",
                "{home_team_name} Under {points}"
            ],
            "notes": None
        },
        {
            "id": 28,
            "name": "team_total_3way",
            "selections": [
                "{away_team_name} Exact {points}",
                "{away_team_name} Over {points}",
                "{away_team_name} Under {points}",
                "{home_team_name} Exact {points}",
                "{home_team_name} Over {points}",
                "{home_team_name} Under {points}"
            ],
            "notes": None
        },
        {
            "id": 29,
            "name": "team_total_exact",
            "selections": [
                "{away_team_name} - {points}",
                "{home_team_name} - {points}"
            ],
            "notes": None
        },
        {
            "id": 30,
            "name": "team_yes_no",
            "selections": [
                "{away_team_name} No",
                "{away_team_name} Yes",
                "{home_team_name} No",
                "{home_team_name} Yes"
            ],
            "notes": None
        },
        {
            "id": 31,
            "name": "total",
            "selections": [
                "Over {points}",
                "Under {points}"
            ],
            "notes": None
        },
        {
            "id": 32,
            "name": "total_3way",
            "selections": [
                "Exact {points}",
                "Over {points}",
                "Under {points}"
            ],
            "notes": None
        },
        {
            "id": 33,
            "name": "winning_margin_or_draw",
            "selections": [
                "{away_team_name} {points_low}-{points_high}",
                "{away_team_name} {points}+",
                "{home_team_name} {points_low}-{points_high}",
                "{home_team_name} {points}+",
                "Draw"
            ],
            "notes": None
        },
        {
            "id": 34,
            "name": "yes_no",
            "selections": [
                "No",
                "Yes"
            ],
            "notes": None
        },
        {
            "id": 35,
            "name": "yes_no_and_total",
            "selections": [
                "No :: Over {points}",
                "No :: Under {points}",
                "Yes :: Over {points}",
                "Yes :: Under {points}"
            ],
            "notes": None
        },
        {
            "id": 36,
            "name": "heads_or_tails",
            "selections": [
                "Heads",
                "Tails"
            ],
            "notes": None
        },
        {
            "id": 37,
            "name": "run_count",
            "selections": [
                "0 Runs",
                "1 Runs",
                "2 Runs",
                "3 Runs",
                "4 Runs"
            ],
            "notes": None
        },
        {
            "id": 38,
            "name": "method_of_victory",
            "selections": [
                "Decision",
                "KO/TKO/DQ",
                "Submission"
            ],
            "notes": None
        },
        {
            "id": 39,
            "name": "color",
            "selections": [
                "Blue",
                "Green",
                "Orange",
                "Other",
                "Purple",
                "Red",
                "White",
                "Yellow"
            ],
            "notes": None
        },
        {
            "id": 40,
            "name": "team_method_of_victory",
            "selections": [
                "{away_team_name} - Decision",
                "{away_team_name} - KO/TKO/DQ",
                "{away_team_name} - KO/TKO, DQ, or Submission",
                "{away_team_name} - Submission",
                "{home_team_name} - Decision",
                "{home_team_name} - KO/TKO/DQ",
                "{home_team_name} - KO/TKO, DQ, or Submission",
                "{home_team_name} - Submission",
                "Draw"
            ],
            "notes": None
        },
        {
            "id": 41,
            "name": "total_exact",
            "selections": [
                "{points}",
                "{points}+"
            ],
            "notes": None
        },
        {
            "id": 42,
            "name": "player_h2h_ml",
            "selections": [
                "{player_name_1} :: {player_name_2} -- {player_name_1|player_name_2}",
                "{player_name_1} :: {player_name_2} -- {player_name_2|player_name_1}"
            ],
            "notes": "{player_name_1} and {player_name_2} are the two players involved in the bet sorted alphabetically. The player_id will be multiple player IDs separated by a `,` and the last player id will be the player of the bet."
        },
        {
            "id": 43,
            "name": "player_h2h_spread",
            "selections": [
                "{player_name_1} :: {player_name_2} -- {player_name_1|player_name_2} {points}",
                "{player_name_1} :: {player_name_2} -- {player_name_2|player_name_1} {points}"
            ],
            "notes": "{player_name_1} and {player_name_2} are the two players involved in the bet sorted alphabetically. The player_id will be multiple player IDs separated by a `,` and the last player id will be the player of the bet."
        }
    ]
}


def get_market_type_by_name(name: str) -> dict:
    """Get a market type by its name."""
    for market_type in MARKET_TYPES["data"]:
        if market_type.get("name") == name:
            return market_type
    return None


def get_player_prop_market_types() -> list:
    """Get all player prop market types."""
    return [
        mt for mt in MARKET_TYPES["data"]
        if mt.get("name", "").startswith("player_")
    ]


def is_player_prop_market_type(market_type_name: str) -> bool:
    """Check if a market type name is a player prop type."""
    return market_type_name.startswith("player_")


def get_market_type_name_mapping() -> dict:
    """Get a mapping of common display names to actual market type names.
    
    Returns a dictionary mapping human-readable names to API market type names.
    """
    return {
        # Main markets
        "moneyline": "moneyline",
        "Moneyline": "moneyline",
        "ML": "moneyline",
        "spread": "spread",
        "Spread": "spread",
        "point spread": "spread",
        "Point Spread": "spread",
        "total": "total",
        "Total": "total",
        "over/under": "total",
        "Over/Under": "total",
        "O/U": "total",
        
        # Player props (display names -> market type category)
        "player props": "player_props",  # Generic category
        "Player Props": "player_props",
        "player_props": "player_props",
        "player props": "player_props",
        "player totals": "player_total",
        "Player Totals": "player_total",
        "player total": "player_total",
        "Player Total": "player_total",
        
        # Team markets
        "team total": "team_total",
        "Team Total": "team_total",
        "asian handicap": "asian_handicap",
        "Asian Handicap": "asian_handicap",
    }


def normalize_market_name(market_name: str) -> str:
    """Normalize a market name to the actual market type name.
    
    Converts display names like "Player Props" or "Moneyline" to actual
    market type names like "player_props" or "moneyline".
    
    Args:
        market_name: Display name or market type name
        
    Returns:
        Normalized market type name, or original if not found in mapping
    """
    mapping = get_market_type_name_mapping()
    normalized = mapping.get(market_name)
    if normalized:
        return normalized
    
    # Check if it's already a valid market type name
    if get_market_type_by_name(market_name):
        return market_name
    
    # Try case-insensitive match
    market_name_lower = market_name.lower().strip()
    for display_name, actual_name in mapping.items():
        if display_name.lower() == market_name_lower:
            return actual_name
    
    # Return original if no mapping found
    return market_name

