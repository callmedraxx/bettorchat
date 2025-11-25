# OpticOdds API Common Issues - Current Status

## Analysis of Current Implementation

### 1. Multiple Parameters ❌ **NOT HANDLED CORRECTLY**

**API Requirement:**
```
&sportsbook=DraftKings&sportsbook=Fanduel
```

**Current Code** (`app/core/opticodds_client.py:261-265`):
```python
if sportsbook:
    if isinstance(sportsbook, list):
        params["sportsbook"] = ",".join(map(str, sportsbook))  # ❌ Creates: sportsbook=DraftKings,Fanduel
    else:
        params["sportsbook"] = str(sportsbook)
```

**Problem:** We're creating comma-separated values instead of multiple parameters.

**Fix:** httpx supports passing lists directly in params, which automatically creates multiple query parameters. We should pass the list directly.

---

### 2. URL Encoding ⚠️ **PARTIALLY HANDLED**

**API Requirement:**
- Special characters like `+` must be URL encoded as `%2B`
- Example: `Player Passing + Rushing Yards` → `Player%20Passing%20%2B%20Rushing%20Yards`

**Current Code:**
- httpx automatically URL-encodes query parameters
- However, we're not explicitly handling or testing special characters in market names

**Status:** Should work automatically, but we should verify and potentially add explicit handling for edge cases.

---

### 3. Pagination ❌ **NOT HANDLED**

**API Response Format:**
```json
{
  "data": [...],
  "page": 1,
  "total_pages": 7
}
```

**Current Code:**
- No pagination logic anywhere
- Only returns first page of results
- Doesn't check `total_pages` or fetch additional pages

**Affected Methods:**
- `get_fixtures()` - Could have multiple pages
- `get_fixture_odds()` - Could have multiple pages
- `get_active_fixtures()` - Could have multiple pages
- `get_sports()` - Could have multiple pages
- `get_leagues()` - Could have multiple pages
- `get_sportsbooks()` - Could have multiple pages
- `get_markets()` - Could have multiple pages
- All other methods that return paginated data

**Problem:** If there are multiple pages, we only get the first page and miss the rest.

---

## Summary

| Issue | Status | Impact | Priority |
|-------|--------|--------|----------|
| Multiple Parameters | ❌ Wrong format | May cause API errors or missing data | High |
| URL Encoding | ⚠️ Should work but untested | May fail with special characters | Medium |
| Pagination | ❌ Not implemented | Missing data from additional pages | High |

## Recommendations

1. **Fix Multiple Parameters**: Change comma-separated to multiple params using httpx list support
2. **Add Pagination**: Implement pagination handling for all relevant methods
3. **Test URL Encoding**: Verify special characters are properly encoded
4. **Update Documentation**: Add notes about these issues in agent prompts

