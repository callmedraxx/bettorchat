# Fetch Live Odds - Parameters and Endpoints Analysis

## Tool Function: `fetch_live_odds`

### Input Parameters (Tool Signature)

```python
fetch_live_odds(
    fixture_id: Optional[str] = None,
    fixture: Optional[str] = None,           # JSON string of fixture object
    fixtures: Optional[str] = None,           # JSON string of multiple fixtures (array)
    league_id: Optional[str] = None,
    sport_id: Optional[str] = None,
    sportsbook_ids: Optional[str] = None,    # Comma-separated string (e.g., "DraftKings,FanDuel")
    market_types: Optional[str] = None,     # Comma-separated string (e.g., "moneyline,spread,total")
) -> str
```

### Parameter Processing Flow

1. **Market Types Processing** (lines 328-337):
   - If `market_types` is comma-separated string → splits into list
   - Example: `"moneyline,spread"` → `["moneyline", "spread"]`
   - Single string → `["moneyline"]`
   - Already a list → used as-is

2. **Sportsbook IDs Processing** (lines 339-349):
   - If `sportsbook_ids` is comma-separated string → splits into list
   - Example: `"DraftKings,FanDuel,BetMGM"` → `["DraftKings", "FanDuel", "BetMGM"]`
   - Single string → `["DraftKings"]`
   - Already a list → used as-is
   - **If not provided**: Automatically fetches from API using `get_default_sportsbooks()`

3. **League ID Extraction** (lines 351-361):
   - Uses provided `league_id` if available
   - If `fixture` object provided, extracts `league_id` from fixture object
   - Checks: `fixture.league.id` or `fixture.league.numerical_id`

4. **Fixture ID Resolution** (lines 405-421):
   - Priority order:
     1. Extract from `fixture` object (if provided)
     2. Use `fixture_id` parameter (if provided)
   - Uses `extract_fixture_id()` helper function

5. **Default Sportsbooks** (lines 363-375):
   - If no `sportsbook_ids` provided:
     - Calls `get_default_sportsbooks(sport_id, league_id)`
     - Falls back to: `["DraftKings", "FanDuel", "BetMGM"]` if fetch fails

### Parameters Passed to OpticOdds API

**Endpoint**: `GET https://api.opticodds.com/api/v3/fixtures/odds`

**Method Call**: `client.get_fixture_odds(...)`

**Actual Parameters Sent** (lines 425-431):

```python
client.get_fixture_odds(
    fixture_id=resolved_fixture_id,           # Extracted from fixture object or parameter
    sport_id=sport_id if sport_id else None,  # Passed as-is if provided
    league_id=resolved_league_id,             # Extracted from fixture or parameter
    sportsbook=resolved_sportsbook_ids,       # List of sportsbook names/IDs
    market_types=resolved_market_types,       # List of market types
)
```

### OpticOdds Client Processing (`get_fixture_odds`)

**Location**: `app/core/opticodds_client.py` lines 311-396

**Query Parameters Built**:

1. **fixture_id** (line 340-341):
   - If provided: `params["fixture_id"] = str(fixture_id)`

2. **sport/sport_id** (lines 343-355):
   - Prefers `sport_id` if provided → `params["sport_id"] = str(sport_id)`
   - If `sport` provided:
     - Tries to convert to int (if numeric, treats as `sport_id`)
     - Otherwise uses as `sport` name → `params["sport"] = str(sport)`

3. **league/league_id** (lines 357-369):
   - Prefers `league_id` if provided → `params["league_id"] = str(league_id)`
   - If `league` provided:
     - Tries to convert to int (if numeric, treats as `league_id`)
     - Otherwise uses as `league` name → `params["league"] = str(league)`

4. **sportsbook** (lines 371-379):
   - If list: Creates multiple query params → `?sportsbook=DraftKings&sportsbook=FanDuel`
   - If single: `params["sportsbook"] = str(sportsbook)`

5. **market_types** (lines 381-390):
   - If list: Creates multiple query params → `?market_types=moneyline&market_types=spread`
   - If single: `params["market_types"] = str(market_types)`
   - Automatically URL-encodes special characters (e.g., `+` → `%2B`)

6. **player_id** (lines 391-392):
   - If provided: `params["player_id"] = str(player_id)`

7. **team_id** (lines 393-394):
   - If provided: `params["team_id"] = str(team_id)`

### Final API Request

**Base URL**: `https://api.opticodds.com/api/v3`  
**Endpoint**: `/fixtures/odds`  
**Method**: `GET`

**Example Request**:
```
GET https://api.opticodds.com/api/v3/fixtures/odds?fixture_id=20251127E5C64DE0&sport_id=1&league_id=123&sportsbook=DraftKings&sportsbook=FanDuel&market_types=moneyline&market_types=spread
```

**Headers**:
- `X-API-Key: <your_api_key>`
- `Content-Type: application/json`

### API Requirements

According to documentation (line 182):
- **Requires**: At least one of: `fixture_id`, `team_id`, or `player_id` **AND** at least 1 sportsbook (max 5)
- **Returns**: Only odds that are currently available
- **Key Rule**: "We only return odds that are available, if an odd is not returned then it is for all intents and purposes suspended"

### Potential Issues

1. **Missing Sportsbook**: If no `sportsbook_ids` provided and `get_default_sportsbooks()` fails, falls back to hardcoded defaults
2. **Missing Fixture ID**: If neither `fixture_id` nor `fixture` object provided, API call will fail (API requires at least one identifier)
3. **Sport Parameter**: The client accepts both `sport` and `sport_id`, but the tool only passes `sport_id`
4. **League Parameter**: The client accepts both `league` and `league_id`, but the tool only passes `league_id`

### Multiple Fixtures Handling

If `fixtures` parameter provided (lines 377-403):
- Extracts all fixture IDs using `extract_fixture_ids_from_objects()`
- Makes separate API call for each fixture
- Combines all results into single response

