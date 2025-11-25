# NBA Games Tonight - API vs Tool Comparison

## Summary

Both approaches use the same underlying OpticOdds API endpoint (`/fixtures`), but there are key differences in how they handle parameters and date filtering.

## Direct API Call Approach

**Endpoint**: `GET /api/v3/fixtures`

**Parameters Used**:
```python
params = {
    "sport": "basketball",
    "league": "nba",
    "start_date_after": "2025-11-25"  # Today's date
}
```

**Headers**:
```
X-API-Key: <api_key>
Content-Type: application/json
```

**Result**: Returns fixtures from the specified date onwards.

## Existing Tool Approach (`fetch_upcoming_games`)

**Implementation** (from `app/agents/tools/betting_tools.py`):
```python
def fetch_upcoming_games(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    fixture_id: Optional[str] = None,
) -> str:
    client = get_client()
    result = client.get_fixtures(
        sport=sport if sport else None,
        league=league if league else None,
        fixture_id=fixture_id if fixture_id else None,
    )
    formatted = format_fixtures_response(result)
    return formatted
```

**Parameters Used**:
```python
params = {
    "sport": "basketball",
    "league": "nba"
}
# NO date parameters!
```

**Key Difference**: The tool does NOT pass any date parameters, which means:
- According to API docs: "If you do not pass any of the date parameters (start_date, start_date_before, start_date_after) then this endpoint will default to returning fixtures from 3 days ago."

## Comparison Results

### Test Date: November 25, 2025 (Tuesday)

**Direct API Call (with `start_date_after=2025-11-25`)**:
- ✅ API call successful (200 OK)
- ⚠️ Returned 0 fixtures (no games scheduled for tonight)

**Tool Approach (no date parameters)**:
- Would default to returning fixtures from 3 days ago (November 22, 2025)
- Would NOT return games for "tonight" unless they happen to be in that default range

## Issue Identified

**The existing `fetch_upcoming_games` tool does NOT support date filtering!**

This means:
1. When user asks for "games tonight", the tool returns games from 3 days ago (default behavior)
2. The tool cannot filter by specific dates
3. The tool cannot get "upcoming" games - it gets "recent past" games by default

## Recommendation

The `fetch_upcoming_games` tool should be updated to:
1. Accept optional date parameters (`start_date`, `start_date_after`, `start_date_before`)
2. When user asks for "tonight" or "tomorrow", automatically add date filters
3. Default to `start_date_after=today` instead of the API's default of 3 days ago

## API Endpoint Details

From OpticOdds documentation:
- `/fixtures` - Returns all fixtures (past and future)
- Default behavior: Returns fixtures from 3 days ago if no date parameters
- Date parameters:
  - `start_date`: Specific date
  - `start_date_after`: Get fixtures after this date
  - `start_date_before`: Get fixtures before this date
  - Cannot use `start_date` with `start_date_after` or `start_date_before`

## Test Results

**Date**: November 25, 2025, 3:59 AM ET

**Direct API Call**:
- URL: `https://api.opticodds.com/api/v3/fixtures?sport=basketball&league=nba&start_date_after=2025-11-25`
- Status: 200 OK
- Fixtures returned: 0 (no games scheduled for tonight)

**Active Fixtures**:
- URL: `https://api.opticodds.com/api/v3/fixtures/active?sport=basketball&league=nba`
- Status: 200 OK
- Fixtures returned: 0 (no active games with odds)

**Conclusion**: Both approaches work correctly, but the tool approach doesn't support date filtering, which is needed for "tonight" queries.

