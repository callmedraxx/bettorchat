# OpticOdds API Endpoints Reference - Live, Past, and Upcoming Games

This document clarifies which OpticOdds API endpoints (and our corresponding tools) are designed for **live/active**, **past/completed**, or **upcoming/scheduled** games. This helps understand when to expect "not found" responses and when you might be hitting the wrong API endpoint.

## Summary Table

| Tool/Endpoint | Purpose | Game Status | When to Use | When "Not Found" is Expected |
|---------------|---------|-------------|-------------|------------------------------|
| `fetch_upcoming_games` (`/fixtures`) | Get game schedules | **Upcoming** + **Past** | Getting schedules for any date | If no games scheduled for that date/league |
| `fetch_live_odds` (`/fixtures/odds`) | Get betting odds | **Upcoming** + **Live** (with odds) | Getting current odds for games | If game has no odds available or is completed |
| `fetch_live_game_stats` (`/fixtures/results`) | Get game results/stats | **Live** + **Past/Completed** | Getting scores/stats for games in progress or finished | If game hasn't started yet or fixture_id doesn't exist |
| `fetch_player_props` (`/fixtures/player-results` + `/fixtures/odds`) | Get player prop odds | **Upcoming** + **Live** (with props) | Getting player prop markets | If no player props available for that game |
| `fetch_historical_odds` (`/fixtures/odds/historical`) | Get historical odds | **Past/Completed** only | Getting odds from a specific time in the past | If fixture_id doesn't exist or no historical data |
| `fetch_futures` (`/futures` + `/futures/odds`) | Get futures markets | **Season-long** (not game-specific) | Getting season/tournament futures | If no futures markets for that sport/league |
| `fetch_injury_reports` (`/injuries`) | Get injury reports | **Current** (not game-specific) | Getting current injury status | If no injuries reported |
| `detect_arbitrage_opportunities` (`/fixtures/odds`) | Find arbitrage | **Upcoming** + **Live** (with odds) | Finding price discrepancies | If no odds available or no arbitrage found |
| `fetch_grader` (`/grader/odds` or `/grader/futures`) | Get bet settlement | **Past/Completed** only | Checking if a bet won/lost | If game hasn't finished or bet doesn't exist |

## Detailed Breakdown

### 1. **Upcoming Games & Schedules**

#### `fetch_upcoming_games` → `/fixtures`
- **Purpose**: Get game schedules/fixtures
- **Returns**: All fixtures from the past AND scheduled in the future
- **Default Behavior**: If no date parameters are provided, defaults to returning fixtures from 3 days ago
- **Use When**: 
  - User asks "What games are tomorrow?"
  - User asks "Show me the NBA schedule"
  - User asks "When is the next Lakers game?"
- **"Not Found" Expected When**:
  - No games scheduled for that specific date
  - League is not in season
  - Invalid league/sport name

**Note**: This endpoint returns BOTH past and future games. Use date filters to get only upcoming games.

---

### 2. **Live/Active Games**

#### `fetch_live_odds` → `/fixtures/odds`
- **Purpose**: Get current betting odds for fixtures
- **Returns**: Odds for games that have odds available (typically upcoming or live games)
- **Key Point**: "We only return odds that are available, if an odd is not returned then it is for all intents and purposes suspended"
- **Use When**:
  - User asks "What are the odds for the Lakers game?"
  - User asks "Show me moneyline odds for NBA games"
  - User asks "What's the spread for tomorrow's games?"
- **"Not Found" Expected When**:
  - Game has already completed (odds are no longer available)
  - Game is too far in the future (odds not yet posted)
  - Game has no odds available (suspended or not offered)
  - Invalid fixture_id

**Important**: This endpoint does NOT return odds for completed games. Use `fetch_historical_odds` for past games.

#### `fetch_live_game_stats` → `/fixtures/results`
- **Purpose**: Get live in-game statistics and scores
- **Returns**: Results for games that are live or completed
- **Use When**:
  - User asks "What's the score of the Lakers game?"
  - User asks "Show me live stats for game X"
  - User asks "What are the current stats?"
- **"Not Found" Expected When**:
  - Game hasn't started yet (no results available)
  - Invalid fixture_id
  - Game was cancelled/postponed

---

### 3. **Past/Completed Games**

#### `fetch_historical_odds` → `/fixtures/odds/historical`
- **Purpose**: Get historical odds data from a specific point in time
- **Returns**: Odds as they were at a specific timestamp
- **Use When**:
  - User asks "What were the odds for the Lakers game yesterday?"
  - User asks "Show me odds from 2 hours ago"
  - Analyzing odds movement over time
- **"Not Found" Expected When**:
  - Invalid fixture_id
  - No historical data available for that timestamp
  - Game hasn't happened yet (can't get historical data for future)

**Note**: This has stricter rate limits (100 requests per hour vs 6000 per minute)

#### `fetch_grader` → `/grader/odds` or `/grader/futures`
- **Purpose**: Get bet settlement information (did the bet win/lose?)
- **Returns**: Settlement status for completed bets
- **Use When**:
  - User asks "Did my bet win?"
  - User asks "What was the result of this bet?"
  - Checking bet outcomes
- **"Not Found" Expected When**:
  - Game hasn't finished yet (can't settle bets for ongoing games)
  - Invalid fixture_id, market_id, or selection_id
  - Bet doesn't exist

---

### 4. **Special Cases**

#### `fetch_player_props` → `/fixtures/player-results` + `/fixtures/odds`
- **Purpose**: Get player proposition odds
- **Returns**: Player prop markets for games (typically upcoming or live)
- **Use When**:
  - User asks "What are the odds for LeBron to score 30 points?"
  - User asks "Show me player props for tonight's games"
- **"Not Found" Expected When**:
  - No player props available for that game
  - Game has already completed
  - Invalid fixture_id or player_id

#### `fetch_futures` → `/futures` + `/futures/odds`
- **Purpose**: Get season-long futures markets (e.g., "Lakers to win NBA Championship")
- **Returns**: Futures markets, not game-specific
- **Use When**:
  - User asks "What are the odds for the Lakers to win the championship?"
  - User asks "Show me season futures"
- **"Not Found" Expected When**:
  - No futures markets for that sport/league
  - Season hasn't started or is over

#### `fetch_injury_reports` → `/injuries`
- **Purpose**: Get current injury reports
- **Returns**: Current injury status (not game-specific)
- **Use When**:
  - User asks "Who's injured on the Lakers?"
  - User asks "Show me injury reports"
- **"Not Found" Expected When**:
  - No injuries reported
  - Invalid team_id, league_id, or sport_id

#### `detect_arbitrage_opportunities` → `/fixtures/odds`
- **Purpose**: Find arbitrage opportunities across sportsbooks
- **Returns**: Price discrepancies between sportsbooks
- **Use When**:
  - User asks "Are there any arbitrage opportunities?"
  - User asks "Show me the best odds"
- **"Not Found" Expected When**:
  - No odds available
  - No arbitrage opportunities found
  - Games have completed (odds no longer available)

---

## Common Mistakes & Solutions

### ❌ **Mistake**: Using `fetch_live_odds` for a completed game
- **Problem**: Odds are no longer available for completed games
- **Solution**: Use `fetch_historical_odds` with a timestamp from when the game was upcoming/live

### ❌ **Mistake**: Using `fetch_live_game_stats` for an upcoming game
- **Problem**: No results available until the game starts
- **Solution**: Use `fetch_upcoming_games` to get the schedule, or `fetch_live_odds` to get odds

### ❌ **Mistake**: Using `fetch_historical_odds` for a future game
- **Problem**: Can't get historical data for games that haven't happened
- **Solution**: Use `fetch_live_odds` for upcoming games

### ❌ **Mistake**: Using `fetch_grader` for an ongoing game
- **Problem**: Can't settle bets until the game is finished
- **Solution**: Wait until game completes, or use `fetch_live_game_stats` to check current status

---

## Endpoint-Specific Details

### `/fixtures` (via `get_fixtures`)
- **Default**: Returns fixtures from 3 days ago if no date parameters
- **Supports**: All fixtures from past and future
- **Date Parameters**: `start_date`, `start_date_before`, `start_date_after`

### `/fixtures/active` (via `get_active_fixtures`)
- **Returns**: Only fixtures that are currently active (not completed) and have/had odds
- **Difference from `/fixtures`**: Only returns active games, not all games

### `/fixtures/odds` (via `get_fixture_odds`)
- **Returns**: Only odds that are currently available
- **Key Rule**: "We only return odds that are available, if an odd is not returned then it is for all intents and purposes suspended"
- **Requires**: At least one of: `fixture_id`, `team_id`, or `player_id` AND at least 1 sportsbook (max 5)

### `/fixtures/results` (via `get_fixture_results`)
- **Returns**: Fixture results including scores and live state
- **Use For**: Live games (in progress) and completed games
- **Not For**: Upcoming games (no results until game starts)

### `/fixtures/odds/historical` (via `get_historical_odds`)
- **Returns**: Historical odds at a specific timestamp
- **Rate Limit**: 100 requests per hour (much stricter than standard endpoints)
- **Requires**: `fixture_id` (must be a completed or past game)

---

## Recommendations for Tool Usage

1. **For "What games are tomorrow?"** → Use `fetch_upcoming_games` with date filters
2. **For "What are the odds?"** → Use `fetch_live_odds` (only works for upcoming/live games with odds)
3. **For "What's the score?"** → Use `fetch_live_game_stats` (only works for live/completed games)
4. **For "What were the odds yesterday?"** → Use `fetch_historical_odds` with timestamp
5. **For "Did my bet win?"** → Use `fetch_grader` (only works for completed games)

---

## Status Field Values

Fixtures have a `status` field that indicates their current state:
- **Scheduled**: Game is upcoming
- **Live/In Progress**: Game is currently happening
- **Completed/Finished**: Game is over
- **Cancelled/Postponed**: Game was cancelled

Check the `status` field in responses to understand what data will be available.

