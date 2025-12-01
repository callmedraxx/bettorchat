"""
Database models.
"""
from app.models.fixture import Fixture
from app.models.nfl_player import NFLPlayer
from app.models.nfl_fixture import NFLFixture
from app.models.nfl_odds import NFLOdds

__all__ = ["Fixture", "NFLPlayer", "NFLFixture", "NFLOdds"]

