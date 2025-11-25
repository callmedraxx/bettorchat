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
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        endpoint_type: str = "standard", 
        paginate: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Make API request with rate limiting and optional pagination.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            endpoint_type: Rate limit type ("standard" or "historical")
            paginate: If True, fetch all pages and combine results
            **kwargs: Additional request parameters
        """
        self._check_rate_limit(endpoint_type)
        
        try:
            response = self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            result = response.json()
            
            # Handle pagination if requested
            if paginate and isinstance(result, dict):
                total_pages = result.get("total_pages", 1)
                current_page = result.get("page", 1)
                data = result.get("data", [])
                
                # Fetch remaining pages
                if total_pages > 1 and current_page == 1:
                    # Initialize combined data - preserve original structure
                    all_data = list(data) if isinstance(data, list) else [data] if data else []
                    
                    # Update params for pagination
                    params = kwargs.get("params", {})
                    if not isinstance(params, dict):
                        params = {}
                    
                    # Fetch remaining pages
                    for page in range(2, total_pages + 1):
                        self._check_rate_limit(endpoint_type)
                        page_params = params.copy()
                        page_params["page"] = page
                        page_kwargs = kwargs.copy()
                        page_kwargs["params"] = page_params
                        
                        try:
                            page_response = self.client.request(method, endpoint, **page_kwargs)
                            page_response.raise_for_status()
                            page_result = page_response.json()
                            page_data = page_result.get("data", [])
                            
                            if isinstance(page_data, list):
                                all_data.extend(page_data)
                            elif page_data:
                                all_data.append(page_data)
                        except Exception as e:
                            # Log error but continue with pages we got
                            # In production, you might want to log this properly
                            break
                    
                    # Return combined result
                    result["data"] = all_data
                    result["page"] = total_pages
                    result["all_pages_fetched"] = True
                    result["total_items"] = len(all_data)
            
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited, wait and retry once
                time.sleep(1)
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response.json()
            raise
    
    # Common endpoints
    def get_sports(self, paginate: bool = False) -> Dict[str, Any]:
        """Get all sports.
        
        Args:
            paginate: If True, fetch all pages of results
        """
        return self._request("GET", "/sports", paginate=paginate)
    
    def get_active_sports(self, paginate: bool = False) -> Dict[str, Any]:
        """Get active sports.
        
        Args:
            paginate: If True, fetch all pages of results
        """
        return self._request("GET", "/sports/active", paginate=paginate)
    
    def get_leagues(self, sport: Optional[Union[str, int]] = None, paginate: bool = False) -> Dict[str, Any]:
        """Get leagues.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        return self._request("GET", "/leagues", params=params, paginate=paginate)
    
    def get_active_leagues(self, paginate: bool = False) -> Dict[str, Any]:
        """Get active leagues.
        
        Args:
            paginate: If True, fetch all pages of results
        """
        return self._request("GET", "/leagues/active", paginate=paginate)
    
    def get_sportsbooks(self, paginate: bool = False) -> Dict[str, Any]:
        """Get all sportsbooks.
        
        Args:
            paginate: If True, fetch all pages of results
        """
        return self._request("GET", "/sportsbooks", paginate=paginate)
    
    def get_active_sportsbooks(
        self, 
        sport: Optional[Union[str, int]] = None,
        league: Optional[Union[str, int]] = None,
        fixture_id: Optional[Union[str, int]] = None,
        paginate: bool = False
    ) -> Dict[str, Any]:
        """Get active sportsbooks.
        
        Args:
            sport: Optional sport name (e.g., 'basketball') or ID to filter sportsbooks by sport
            league: Optional league name (e.g., 'nba') or ID to filter sportsbooks by league
            fixture_id: Optional fixture ID to filter sportsbooks that have odds for this fixture
            paginate: If True, fetch all pages of results
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        return self._request("GET", "/sportsbooks/active", params=params, paginate=paginate)
    
    def get_markets(self, paginate: bool = False) -> Dict[str, Any]:
        """Get all markets.
        
        Args:
            paginate: If True, fetch all pages of results
        """
        return self._request("GET", "/markets", paginate=paginate)
    
    def get_active_markets(self, paginate: bool = False) -> Dict[str, Any]:
        """Get active markets.
        
        Args:
            paginate: If True, fetch all pages of results
        """
        return self._request("GET", "/markets/active", paginate=paginate)
    
    # Squads endpoints
    def get_teams(
        self, 
        league: Optional[Union[str, int]] = None, 
        sport: Optional[Union[str, int]] = None,
        paginate: bool = False
    ) -> Dict[str, Any]:
        """Get teams.
        
        Args:
            league: League name (e.g., 'nba') or ID
            sport: Sport name (e.g., 'basketball') or ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if league:
            params["league"] = str(league)
        if sport:
            params["sport"] = str(sport)
        return self._request("GET", "/teams", params=params, paginate=paginate)
    
    def get_players(
        self, 
        league: Optional[Union[str, int]] = None, 
        team: Optional[Union[str, int]] = None,
        paginate: bool = False
    ) -> Dict[str, Any]:
        """Get players.
        
        Args:
            league: League name (e.g., 'nba') or ID
            team: Team name or ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if league:
            params["league"] = str(league)
        if team:
            params["team"] = str(team)
        return self._request("GET", "/players", params=params, paginate=paginate)
    
    # Fixtures endpoints
    def get_fixtures(
        self,
        sport: Optional[Union[str, int]] = None,
        league: Optional[Union[str, int]] = None,
        fixture_id: Optional[Union[str, int]] = None,
        paginate: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Get fixtures.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
            fixture_id: Fixture ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        if fixture_id:
            params["fixture_id"] = str(fixture_id)
        params.update(kwargs)
        return self._request("GET", "/fixtures", params=params, paginate=paginate)
    
    def get_active_fixtures(
        self, 
        sport: Optional[Union[str, int]] = None, 
        league: Optional[Union[str, int]] = None,
        paginate: bool = False
    ) -> Dict[str, Any]:
        """Get active fixtures.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        return self._request("GET", "/fixtures/active", params=params, paginate=paginate)
    
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
        fixture_id: Optional[Union[str, int, List[Union[str, int]]]] = None,
        sportsbook: Optional[Union[str, int, List[Union[str, int]]]] = None,
        market: Optional[Union[str, List[str]]] = None,
        player_id: Optional[Union[str, int]] = None,
        team_id: Optional[Union[str, int]] = None,
        paginate: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Get fixture odds.
        
        Args:
            fixture_id: Fixture ID or list of fixture IDs (up to 5). Creates multiple query params.
            sportsbook: Sportsbook name/ID or list of sportsbooks (REQUIRED, max 5). Creates multiple query params.
            market: Market name(s) as string or list (will create multiple query params, URL encoded)
            player_id: Player ID (for player props)
            team_id: Team ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        
        # Handle multiple fixture_ids - use list to create multiple query params
        # API expects: &fixture_id=ID1&fixture_id=ID2 (up to 5)
        if fixture_id:
            if isinstance(fixture_id, list):
                # Limit to 5 fixture_ids per API requirement
                fixture_ids = [str(fid) for fid in fixture_id[:5]]
                params["fixture_id"] = fixture_ids
            else:
                params["fixture_id"] = str(fixture_id)
        
        # Handle multiple sportsbooks - use list to create multiple query params
        # API expects: &sportsbook=DraftKings&sportsbook=Fanduel (REQUIRED, max 5)
        # httpx automatically creates multiple query params when a list is passed
        if sportsbook:
            if isinstance(sportsbook, list):
                # Limit to 5 sportsbooks per API requirement
                # Normalize to lowercase for consistency (API may be case-sensitive)
                sportsbooks = [str(sb).strip().lower() for sb in sportsbook[:5]]
                params["sportsbook"] = sportsbooks
            else:
                # Normalize to lowercase for consistency (API may be case-sensitive)
                params["sportsbook"] = str(sportsbook).strip().lower()
        
        # Handle multiple markets - use list to create multiple query params
        # httpx automatically URL encodes special characters like + in market names
        # Example: "Player Passing + Rushing Yards" → "Player%20Passing%20%2B%20Rushing%20Yards"
        if market:
            if isinstance(market, list):
                # Pass as list - httpx will create multiple params and URL encode
                params["market"] = [str(m) for m in market]
            else:
                # Single market - httpx will automatically URL encode
                params["market"] = str(market)
        
        if player_id:
            params["player_id"] = str(player_id)
        if team_id:
            params["team_id"] = str(team_id)
        params.update(kwargs)
        return self._request("GET", "/fixtures/odds", params=params, paginate=paginate)
    
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
        paginate: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Get futures markets.
        
        Args:
            sport: Sport name (e.g., 'basketball') or ID
            league: League name (e.g., 'nba') or ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if sport:
            params["sport"] = str(sport)
        if league:
            params["league"] = str(league)
        params.update(kwargs)
        return self._request("GET", "/futures", params=params, paginate=paginate)
    
    def get_futures_odds(
        self,
        future_id: Optional[Union[str, int]] = None,
        sport: Optional[Union[str, int]] = None,
        paginate: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Get futures odds.
        
        Args:
            future_id: Future ID
            sport: Sport name (e.g., 'basketball') or ID
            paginate: If True, fetch all pages of results
        """
        params = {}
        if future_id:
            params["future_id"] = str(future_id)
        if sport:
            params["sport"] = str(sport)
        params.update(kwargs)
        return self._request("GET", "/futures/odds", params=params, paginate=paginate)
    
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

