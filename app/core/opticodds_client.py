"""
OpticOdds API v3.0 client wrapper.
"""
import os
import time
from typing import Optional, Dict, List, Any, Union
import httpx
from app.core.config import settings


class OpticOddsClient:
    """Client for OpticOdds API v3.0."""
    
    BASE_URL = "https://api.opticodds.com/api/v3"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpticOdds client."""
        self.api_key = api_key or settings.OPTICODDS_API_KEY or os.getenv("OPTICODDS_API_KEY")
        if not self.api_key:
            raise ValueError("OPTICODDS_API_KEY must be set in environment variables or config")
        
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        
        # Rate limiting tracking
        self._request_times = []
        self._rate_limit_6000_per_min = 6000
        self._rate_limit_100_per_hour = 100
    
    def _check_rate_limit(self, endpoint_type: str = "standard"):
        """Check and enforce rate limits."""
        now = time.time()
        
        if endpoint_type == "historical":
            # 100 requests per hour
            hour_ago = now - 3600
            self._request_times = [t for t in self._request_times if t > hour_ago]
            if len(self._request_times) >= self._rate_limit_100_per_hour:
                sleep_time = 3600 - (now - self._request_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
        else:
            # 6000 requests per minute
            minute_ago = now - 60
            self._request_times = [t for t in self._request_times if t > minute_ago]
            if len(self._request_times) >= self._rate_limit_6000_per_min:
                sleep_time = 60 - (now - self._request_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        self._request_times.append(now)
    
    def _request(self, method: str, endpoint: str, endpoint_type: str = "standard", **kwargs) -> Dict[str, Any]:
        """Make API request with rate limiting."""
        self._check_rate_limit(endpoint_type)
        
        try:
            response = self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited, wait and retry once
                time.sleep(1)
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response.json()
            raise
    
    # Common endpoints
    def get_sports(self) -> Dict[str, Any]:
        """Get all sports."""
        return self._request("GET", "/sports")
    
    def get_active_sports(self) -> Dict[str, Any]:
        """Get active sports."""
        return self._request("GET", "/sports/active")
    
    def get_leagues(self, sport: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """Get leagues.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        return self._request("GET", "/leagues", params=params)
    
    def get_active_leagues(self) -> Dict[str, Any]:
        """Get active leagues."""
        return self._request("GET", "/leagues/active")
    
    def get_sportsbooks(self) -> Dict[str, Any]:
        """Get all sportsbooks."""
        return self._request("GET", "/sportsbooks")
    
    def get_active_sportsbooks(self, sport: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """Get active sportsbooks.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        return self._request("GET", "/sportsbooks/active", params=params)
    
    def get_markets(self) -> Dict[str, Any]:
        """Get all markets."""
        return self._request("GET", "/markets")
    
    def get_active_markets(self) -> Dict[str, Any]:
        """Get active markets."""
        return self._request("GET", "/markets/active")
    
    # Squads endpoints
    def get_teams(self, league: Optional[Union[str, int]] = None, sport: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """Get teams.
        
        Args:
            league: League name (e.g., 'nba') or ID
            sport: Sport name (e.g., 'basketball') or ID
        """
        params = {}
        if league:
            params["league"] = str(league)
        if sport:
            params["sport"] = str(sport)
        return self._request("GET", "/teams", params=params)
    
    def get_players(self, league: Optional[Union[str, int]] = None, team: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """Get players.
        
        Args:
            league: League name (e.g., 'nba') or ID
            team: Team name or ID
        """
        params = {}
        if league:
            params["league"] = str(league)
        if team:
            params["team"] = str(team)
        return self._request("GET", "/players", params=params)
    
    # Fixtures endpoints
    def get_fixtures(
        self,
        sport: Optional[Union[str, int]] = None,
        league: Optional[Union[str, int]] = None,
        fixture_id: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get fixtures.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
            fixture_id: Fixture ID
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        params.update(kwargs)
        return self._request("GET", "/fixtures", params=params)
    
    def get_active_fixtures(self, sport: Optional[Union[str, int]] = None, league: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """Get active fixtures.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        return self._request("GET", "/fixtures/active", params=params)
    
    def get_tournaments(self, league: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """Get tournaments.
        
        Args:
            league: League name (e.g., 'nba') or ID
        """
        params = {}
        if league:
            params["league"] = str(league)
        return self._request("GET", "/tournaments", params=params)
    
    # Odds endpoints
    def get_fixture_odds(
        self,
        fixture_id: Optional[Union[str, int]] = None,
        sport: Optional[Union[str, int]] = None,
        sport_id: Optional[Union[str, int]] = None,
        league: Optional[Union[str, int]] = None,
        league_id: Optional[Union[str, int]] = None,
        sportsbook: Optional[Union[str, int, List[Union[str, int]]]] = None,
        market_types: Optional[Union[str, List[str]]] = None,
        player_id: Optional[Union[str, int]] = None,
        team_id: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get fixture odds.
        
        Args:
            fixture_id: Fixture ID
            sport: Sport name (e.g., 'basketball') - use for string names
            sport_id: Sport ID (e.g., 1) - use for numeric IDs
            league: League name (e.g., 'nba') - use for string names
            league_id: League ID - use for numeric IDs
            sportsbook: Sportsbook name/ID or list of sportsbooks
            market_types: Market type(s) as string or list
            player_id: Player ID (for player props)
            team_id: Team ID
        """
        params = {}
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        
        # Handle sport parameter - prefer sport_id if provided, otherwise use sport
        # If sport is numeric, treat it as sport_id
        if sport_id:
            params["sport_id"] = str(sport_id)
        elif sport:
            # Check if sport is numeric (ID) or string (name)
            try:
                # Try to convert to int - if successful, it's an ID
                sport_int = int(sport)
                params["sport_id"] = str(sport_int)
            except (ValueError, TypeError):
                # Not numeric, treat as name
                params["sport"] = str(sport)
        
        # Handle league parameter - prefer league_id if provided, otherwise use league
        # If league is numeric, treat it as league_id
        if league_id:
            params["league_id"] = str(league_id)
        elif league:
            # Check if league is numeric (ID) or string (name)
            try:
                # Try to convert to int - if successful, it's an ID
                league_int = int(league)
                params["league_id"] = str(league_int)
            except (ValueError, TypeError):
                # Not numeric, treat as name
                params["league"] = str(league)
        
        if sportsbook:
            if isinstance(sportsbook, list):
                params["sportsbook"] = ",".join(map(str, sportsbook))
            else:
                params["sportsbook"] = str(sportsbook)
        if market_types:
            if isinstance(market_types, list):
                params["market_types"] = ",".join(market_types)
            else:
                params["market_types"] = market_types
        if player_id:
            params["player_id"] = str(player_id)
        if team_id:
            params["team_id"] = str(team_id)
        params.update(kwargs)
        return self._request("GET", "/fixtures/odds", params=params)
    
    def get_historical_odds(
        self,
        fixture_id: int,
        timestamp: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get historical odds for a fixture."""
        params = {"fixture_id": fixture_id}
        if timestamp:
            params["timestamp"] = timestamp
        params.update(kwargs)
        return self._request("GET", "/fixtures/odds/historical", endpoint_type="historical", params=params)
    
    # Results endpoints
    def get_fixture_results(
        self,
        fixture_id: Optional[Union[str, int]] = None,
        sport: Optional[Union[str, int]] = None,
        league: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get fixture results.
        
        Args:
            fixture_id: Fixture ID
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
        """
        params = {}
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        params.update(kwargs)
        return self._request("GET", "/fixtures/results", params=params)
    
    def get_player_results(
        self,
        fixture_id: Optional[Union[str, int]] = None,
        player_id: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get player results.
        
        Args:
            fixture_id: Fixture ID
            player_id: Player ID
        """
        params = {}
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        if player_id:
            params["player_id"] = str(player_id)
        params.update(kwargs)
        return self._request("GET", "/fixtures/player-results", params=params)
    
    def get_head_to_head(
        self,
        team_id_1: int,
        team_id_2: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Get head-to-head results."""
        params = {"team_id_1": team_id_1, "team_id_2": team_id_2}
        params.update(kwargs)
        return self._request("GET", "/fixtures/results/head-to-head", params=params)
    
    # Futures endpoints
    def get_futures(
        self,
        sport: Optional[Union[str, int]] = None,
        league: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get futures markets.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        params.update(kwargs)
        return self._request("GET", "/futures", params=params)
    
    def get_futures_odds(
        self,
        future_id: Optional[Union[str, int]] = None,
        sport: Optional[Union[str, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get futures odds.
        
        Args:
            future_id: Future ID
            sport: Sport name (e.g., 'basketball') or ID
        """
        params = {}
        if future_id:
            params["future_id"] = str(future_id)
        if sport:
            params["sport"] = str(sport)
        params.update(kwargs)
        return self._request("GET", "/futures/odds", params=params)
    
    # Grader endpoints
    def get_grader_odds(
        self,
        fixture_id: int,
        market_id: int,
        selection_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Get grader odds for settlement."""
        params = {
            "fixture_id": fixture_id,
            "market_id": market_id,
            "selection_id": selection_id,
        }
        params.update(kwargs)
        return self._request("GET", "/grader/odds", params=params)
    
    def get_grader_futures(
        self,
        future_id: int,
        selection_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Get grader futures for settlement."""
        params = {
            "future_id": future_id,
            "selection_id": selection_id,
        }
        params.update(kwargs)
        return self._request("GET", "/grader/futures", params=params)
    
    # Injuries endpoints
    def get_injuries(
        self,
        sport_id: Optional[int] = None,
        league_id: Optional[int] = None,
        team_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get injury reports."""
        params = {}
        if sport_id:
            params["sport_id"] = sport_id
        if league_id:
            params["league_id"] = league_id
        if team_id:
            params["team_id"] = team_id
        params.update(kwargs)
        return self._request("GET", "/injuries", params=params)
    
    def get_injury_predictions(
        self,
        player_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get injury predictions."""
        params = {}
        if player_id:
            params["player_id"] = player_id
        params.update(kwargs)
        return self._request("GET", "/injuries/predictions", params=params)
    
    # Parlay endpoint
    def calculate_parlay_odds(
        self,
        legs: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """Calculate parlay odds."""
        data = {"legs": legs}
        data.update(kwargs)
        return self._request("POST", "/parlay/odds", json=data)
    
    def __del__(self):
        """Cleanup client."""
        if hasattr(self, "client"):
            self.client.close()

