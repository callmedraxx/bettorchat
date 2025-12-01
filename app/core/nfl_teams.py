"""
NFL teams data embedded in codebase for fast access without API calls.
This data is used to quickly look up team information, IDs, and filter players by team.
"""

NFL_TEAMS = {
    "data": [
        {
            "id": "AF456B375E7E",
            "name": "Arizona Cardinals",
            "numerical_id": 83,
            "base_id": 81,
            "is_active": True,
            "city": "Arizona",
            "mascot": "Cardinals",
            "nickname": "Cardinals",
            "abbreviation": "ARI",
            "division": "West",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/81.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "348C1EE88C42",
            "name": "Atlanta Falcons",
            "numerical_id": 84,
            "base_id": 82,
            "is_active": True,
            "city": "Atlanta",
            "mascot": "Falcons",
            "nickname": "Falcons",
            "abbreviation": "ATL",
            "division": "South",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/82.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "766A226BC204",
            "name": "Baltimore Ravens",
            "numerical_id": 85,
            "base_id": 83,
            "is_active": True,
            "city": "Baltimore",
            "mascot": "Ravens",
            "nickname": "Ravens",
            "abbreviation": "BAL",
            "division": "North",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/83.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "0787D09E47B9",
            "name": "Buffalo Bills",
            "numerical_id": 86,
            "base_id": 84,
            "is_active": True,
            "city": "Buffalo",
            "mascot": "Bills",
            "nickname": "Bills",
            "abbreviation": "BUF",
            "division": "East",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/84.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "EB5E972AB475",
            "name": "Carolina Panthers",
            "numerical_id": 87,
            "base_id": 85,
            "is_active": True,
            "city": "Carolina",
            "mascot": "Panthers",
            "nickname": "Panthers",
            "abbreviation": "CAR",
            "division": "South",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/85.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "7108F48884ED",
            "name": "Chicago Bears",
            "numerical_id": 88,
            "base_id": 86,
            "is_active": True,
            "city": "Chicago",
            "mascot": "Bears",
            "nickname": "Bears",
            "abbreviation": "CHI",
            "division": "North",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/86.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "EB3A43FF026E",
            "name": "Cincinnati Bengals",
            "numerical_id": 89,
            "base_id": 87,
            "is_active": True,
            "city": "Cincinnati",
            "mascot": "Bengals",
            "nickname": "Bengals",
            "abbreviation": "CIN",
            "division": "North",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/87.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "81A1B4413577",
            "name": "Cleveland Browns",
            "numerical_id": 90,
            "base_id": 88,
            "is_active": True,
            "city": "Cleveland",
            "mascot": "Browns",
            "nickname": "Browns",
            "abbreviation": "CLE",
            "division": "North",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/88.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "0BDD5205ECCB",
            "name": "Dallas Cowboys",
            "numerical_id": 91,
            "base_id": 89,
            "is_active": True,
            "city": "Dallas",
            "mascot": "Cowboys",
            "nickname": "Cowboys",
            "abbreviation": "DAL",
            "division": "East",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/89.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "0DBD3AEC9A84",
            "name": "Denver Broncos",
            "numerical_id": 92,
            "base_id": 90,
            "is_active": True,
            "city": "Denver",
            "mascot": "Broncos",
            "nickname": "Broncos",
            "abbreviation": "DEN",
            "division": "West",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/90.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "43412DC9CDCA",
            "name": "Detroit Lions",
            "numerical_id": 93,
            "base_id": 91,
            "is_active": True,
            "city": "Detroit",
            "mascot": "Lions",
            "nickname": "Lions",
            "abbreviation": "DET",
            "division": "North",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/91.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "2C6CB429C60C",
            "name": "Green Bay Packers",
            "numerical_id": 94,
            "base_id": 92,
            "is_active": True,
            "city": "Green Bay",
            "mascot": "Packers",
            "nickname": "Packers",
            "abbreviation": "GB",
            "division": "North",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/92.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "4DD082E9EC10",
            "name": "Houston Texans",
            "numerical_id": 95,
            "base_id": 93,
            "is_active": True,
            "city": "Houston",
            "mascot": "Texans",
            "nickname": "Texans",
            "abbreviation": "HOU",
            "division": "South",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/93.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "28ABEAB98C11",
            "name": "Indianapolis Colts",
            "numerical_id": 96,
            "base_id": 94,
            "is_active": True,
            "city": "Indianapolis",
            "mascot": "Colts",
            "nickname": "Colts",
            "abbreviation": "IND",
            "division": "South",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/94.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "9CCE4CA64CF2",
            "name": "Jacksonville Jaguars",
            "numerical_id": 97,
            "base_id": 95,
            "is_active": True,
            "city": "Jacksonville",
            "mascot": "Jaguars",
            "nickname": "Jaguars",
            "abbreviation": "JAX",
            "division": "South",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/95.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "2D71E5BA64A5",
            "name": "Kansas City Chiefs",
            "numerical_id": 98,
            "base_id": 96,
            "is_active": True,
            "city": "Kansas City",
            "mascot": "Chiefs",
            "nickname": "Chiefs",
            "abbreviation": "KC",
            "division": "West",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/96.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "A715F8199801",
            "name": "Las Vegas Raiders",
            "numerical_id": 99,
            "base_id": 97,
            "is_active": True,
            "city": "Las Vegas",
            "mascot": "Raiders",
            "nickname": "Raiders",
            "abbreviation": "LV",
            "division": "West",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/97.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "A283836CDF6E",
            "name": "Los Angeles Chargers",
            "numerical_id": 100,
            "base_id": 98,
            "is_active": True,
            "city": "Los Angeles",
            "mascot": "Chargers",
            "nickname": "Chargers",
            "abbreviation": "LAC",
            "division": "West",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/98.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "13AD4FDBEBA8",
            "name": "Los Angeles Rams",
            "numerical_id": 101,
            "base_id": 99,
            "is_active": True,
            "city": "Los Angeles",
            "mascot": "Rams",
            "nickname": "Rams",
            "abbreviation": "LAR",
            "division": "West",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/99.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "8380A12E67FE",
            "name": "Miami Dolphins",
            "numerical_id": 102,
            "base_id": 100,
            "is_active": True,
            "city": "Miami",
            "mascot": "Dolphins",
            "nickname": "Dolphins",
            "abbreviation": "MIA",
            "division": "East",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/100.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "24E4EA618C5E",
            "name": "Minnesota Vikings",
            "numerical_id": 103,
            "base_id": 101,
            "is_active": True,
            "city": "Minnesota",
            "mascot": "Vikings",
            "nickname": "Vikings",
            "abbreviation": "MIN",
            "division": "North",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/101.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "04E3F3D69B89",
            "name": "New England Patriots",
            "numerical_id": 104,
            "base_id": 102,
            "is_active": True,
            "city": "New England",
            "mascot": "Patriots",
            "nickname": "Patriots",
            "abbreviation": "NE",
            "division": "East",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/102.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "E94C20E042D9",
            "name": "New Orleans Saints",
            "numerical_id": 105,
            "base_id": 103,
            "is_active": True,
            "city": "New Orleans",
            "mascot": "Saints",
            "nickname": "Saints",
            "abbreviation": "NO",
            "division": "South",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/103.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "ACC49FC634EE",
            "name": "New York Giants",
            "numerical_id": 106,
            "base_id": 104,
            "is_active": True,
            "city": "New York",
            "mascot": "Giants",
            "nickname": "Giants",
            "abbreviation": "NYG",
            "division": "East",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/104.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "032D4F9C6C55",
            "name": "New York Jets",
            "numerical_id": 107,
            "base_id": 105,
            "is_active": True,
            "city": "New York",
            "mascot": "Jets",
            "nickname": "Jets",
            "abbreviation": "NYJ",
            "division": "East",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/105.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "EDCC2866B795",
            "name": "Philadelphia Eagles",
            "numerical_id": 108,
            "base_id": 106,
            "is_active": True,
            "city": "Philadelphia",
            "mascot": "Eagles",
            "nickname": "Eagles",
            "abbreviation": "PHI",
            "division": "East",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/106.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "727B3B3C78E8",
            "name": "Pittsburgh Steelers",
            "numerical_id": 109,
            "base_id": 107,
            "is_active": True,
            "city": "Pittsburgh",
            "mascot": "Steelers",
            "nickname": "Steelers",
            "abbreviation": "PIT",
            "division": "North",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/107.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "132B64CEDAC4",
            "name": "San Francisco 49ers",
            "numerical_id": 110,
            "base_id": 108,
            "is_active": True,
            "city": "San Francisco",
            "mascot": "49ers",
            "nickname": "49ers",
            "abbreviation": "SF",
            "division": "West",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/108.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "EFED0277C4BD",
            "name": "Seattle Seahawks",
            "numerical_id": 111,
            "base_id": 109,
            "is_active": True,
            "city": "Seattle",
            "mascot": "Seahawks",
            "nickname": "Seahawks",
            "abbreviation": "SEA",
            "division": "West",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/109.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "4E7DB4C57393",
            "name": "Tampa Bay Buccaneers",
            "numerical_id": 112,
            "base_id": 110,
            "is_active": True,
            "city": "Tampa Bay",
            "mascot": "Buccaneers",
            "nickname": "Buccaneers",
            "abbreviation": "TB",
            "division": "South",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/110.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "24988863B4CB",
            "name": "Tennessee Titans",
            "numerical_id": 113,
            "base_id": 111,
            "is_active": True,
            "city": "Tennessee",
            "mascot": "Titans",
            "nickname": "Titans",
            "abbreviation": "TEN",
            "division": "South",
            "conference": "AFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/111.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        },
        {
            "id": "C921828AB706",
            "name": "Washington Commanders",
            "numerical_id": 114,
            "base_id": 112,
            "is_active": True,
            "city": "Washington",
            "mascot": "Commanders",
            "nickname": "Commanders",
            "abbreviation": "WSH",
            "division": "East",
            "conference": "NFC",
            "logo": "https://cdn.opticodds.com/team-logos/football/112.png",
            "source_ids": {},
            "sport": {
                "id": "football",
                "name": "Football",
                "numerical_id": 9
            },
            "league": {
                "id": "nfl",
                "name": "NFL",
                "numerical_id": 367
            }
        }
    ],
    "page": 1,
    "total_pages": 1
}


def get_nfl_teams() -> dict:
    """Get all NFL teams data."""
    return NFL_TEAMS


def get_team_by_name(team_name: str) -> dict:
    """Get a team by name (case-insensitive partial match).
    
    Args:
        team_name: Team name to search for (e.g., "Detroit Lions", "Lions", "Detroit")
    
    Returns:
        Team dict if found, None otherwise
    """
    team_name_lower = team_name.lower().strip()
    for team in NFL_TEAMS["data"]:
        name = team.get("name", "").lower()
        city = team.get("city", "").lower()
        mascot = team.get("mascot", "").lower()
        nickname = team.get("nickname", "").lower()
        
        if (team_name_lower in name or 
            team_name_lower in city or 
            team_name_lower in mascot or 
            team_name_lower in nickname):
            return team
    return None


def get_team_by_abbreviation(abbreviation: str) -> dict:
    """Get a team by abbreviation (case-insensitive).
    
    Args:
        abbreviation: Team abbreviation (e.g., "DET", "GB", "KC")
    
    Returns:
        Team dict if found, None otherwise
    """
    abbrev_upper = abbreviation.upper().strip()
    for team in NFL_TEAMS["data"]:
        if team.get("abbreviation", "").upper() == abbrev_upper:
            return team
    return None


def get_team_by_id(team_id: str) -> dict:
    """Get a team by ID.
    
    Args:
        team_id: Team ID (e.g., "43412DC9CDCA")
    
    Returns:
        Team dict if found, None otherwise
    """
    for team in NFL_TEAMS["data"]:
        if team.get("id") == team_id:
            return team
    return None


def get_teams_by_division(division: str) -> list:
    """Get all teams in a division.
    
    Args:
        division: Division name (e.g., "North", "South", "East", "West")
    
    Returns:
        List of team dicts
    """
    division_lower = division.lower().strip()
    return [
        team for team in NFL_TEAMS["data"]
        if team.get("division", "").lower() == division_lower
    ]


def get_teams_by_conference(conference: str) -> list:
    """Get all teams in a conference.
    
    Args:
        conference: Conference name (e.g., "AFC", "NFC")
    
    Returns:
        List of team dicts
    """
    conference_upper = conference.upper().strip()
    return [
        team for team in NFL_TEAMS["data"]
        if team.get("conference", "").upper() == conference_upper
    ]


def get_team_id_by_name(team_name: str) -> str:
    """Get team ID by team name (quick lookup for API calls).
    
    Args:
        team_name: Team name to search for
    
    Returns:
        Team ID string if found, None otherwise
    """
    team = get_team_by_name(team_name)
    return team.get("id") if team else None

