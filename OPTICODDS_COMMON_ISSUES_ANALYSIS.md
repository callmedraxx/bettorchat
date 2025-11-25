# OpticOdds API Common Issues - Current Implementation Analysis

## Issues Identified

### 1. Multiple Parameters ❌ NOT HANDLED CORRECTLY

**API Documentation Says:**
> You can pass multiple parameters like this: `&sportsbook=DraftKings&sportsbook=Fanduel`

**Current Implementation:**
```python
# In get_fixture_odds():
if sportsbook:
    if isinstance(sportsbook, list):
        params["sportsbook"] = ",".join(map(str, sportsbook))  # ❌ WRONG
    else:
        params["sportsbook"] = str(sportsbook)
```

**Problem:** We're using comma-separated values (`sportsbook=DraftKings,Fanduel`) instead of multiple parameters (`sportsbook=DraftKings&sportsbook=Fanduel`).

**Fix Needed:** httpx supports passing lists in params, which automatically creates multiple parameters. We should pass the list directly instead of joining with commas.

---

### 2. URL Encoding ⚠️ PARTIALLY HANDLED

**API Documentation Says:**
> Please make sure that query parameters are URL encoded, for instance if there are query parameters with a + in the url, sometimes this will not return results as expected, you will need to replace + with %2B.
> 
> Example: `&market=Player Passing + Rushing Yards` should be `&market=Player%20Passing%20%2B%20Rushing%20Yards`

**Current Implementation:**
- httpx automatically URL-encodes query parameters
- However, we're not explicitly handling special cases like `+` in market names
- If market_types contains `+`, it should be properly encoded

**Status:** httpx should handle this automatically, but we should verify and potentially add explicit encoding for market names with special characters.

---

### 3. Pagination ❌ NOT HANDLED

**API Documentation Says:**
> Most of our endpoints return data in the form:
> ```json
> {
>   "data": ...,
>   "page": 1,
>   "total_pages": 7
> }
> ```

**Current Implementation:**
- No pagination handling anywhere
- Only returns first page of results
- Doesn't check `total_pages` or make additional requests

**Problem:** If there are multiple pages of results, we only get the first page and miss the rest.

**Fix Needed:** Implement pagination logic to:
1. Check `total_pages` in response
2. Make additional requests for remaining pages
3. Combine all pages of results

---

## Current Code Locations

### Multiple Parameters Issue
- **File**: `app/core/opticodds_client.py`
- **Lines**: 261-265 (sportsbook), 266-270 (market_types)
- **Affected Methods**: `get_fixture_odds()`

### URL Encoding
- **File**: `app/core/opticodds_client.py`
- **Status**: httpx handles automatically, but should verify for special characters

### Pagination
- **File**: `app/core/opticodds_client.py`
- **Affected Methods**: All methods that return paginated data:
  - `get_fixtures()`
  - `get_fixture_odds()`
  - `get_active_fixtures()`
  - `get_sports()`
  - `get_leagues()`
  - `get_sportsbooks()`
  - `get_markets()`
  - And others...

---

## Recommendations

1. **Fix Multiple Parameters**: Pass lists directly to httpx params instead of comma-separating
2. **Add URL Encoding Verification**: Explicitly handle special characters in market names
3. **Implement Pagination**: Add pagination support to all relevant methods
4. **Add Tests**: Test with multiple sportsbooks and paginated responses

