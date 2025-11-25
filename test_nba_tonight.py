#!/usr/bin/env python3
"""
Simple script to fetch NBA games for tonight using OpticOdds API.
"""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# OpticOdds API configuration
API_KEY = "f8a621e8-2583-4e97-a769-e70c99acdb85"
BASE_URL = "https://api.opticodds.com/api/v3"

def get_tonight_date():
    """Get today's date in EST."""
    eastern_tz = ZoneInfo("America/New_York")
    now = datetime.now(eastern_tz)
    return now.date().isoformat()

def fetch_nba_games_tonight():
    """Fetch NBA games for tonight."""
    today = get_tonight_date()
    
    print("=" * 80)
    print(f"FETCHING NBA GAMES FOR TONIGHT ({today})")
    print("=" * 80)
    
    # Method 1: Direct API call with date filter
    print("\n1. Direct API Call (with start_date_after parameter):")
    print("-" * 80)
    
    url = f"{BASE_URL}/fixtures"
    params = {
        "sport": "basketball",
        "league": "nba",
        "start_date_after": today
    }
    
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    req = urllib.request.Request(full_url)
    req.add_header("X-API-Key", API_KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            fixtures = result.get("data", [])
            
            print(f"✅ Status: {response.getcode()}")
            print(f"📊 Fixtures returned: {len(fixtures)}")
            
            if fixtures:
                print(f"\n🎮 Games for tonight:")
                for i, game in enumerate(fixtures, 1):
                    home_team = game.get("home_team", {})
                    away_team = game.get("away_team", {})
                    home_name = home_team.get("name", "Unknown") if isinstance(home_team, dict) else str(home_team)
                    away_name = away_team.get("name", "Unknown") if isinstance(away_team, dict) else str(away_team)
                    
                    fixture_id = game.get("id")
                    date = game.get("date")
                    start_time = game.get("start_time")
                    status = game.get("status", "Scheduled")
                    
                    print(f"\n  {i}. {away_name} @ {home_name}")
                    print(f"     Fixture ID: {fixture_id}")
                    print(f"     Date: {date} | Time: {start_time}")
                    print(f"     Status: {status}")
            else:
                print(f"\n⚠️  No games scheduled for tonight ({today})")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Method 2: What the existing tool does (no date filter)
    print("\n\n2. Existing Tool Approach (no date parameters - defaults to 3 days ago):")
    print("-" * 80)
    
    params_no_date = {
        "sport": "basketball",
        "league": "nba"
    }
    
    query_string_no_date = urllib.parse.urlencode(params_no_date)
    full_url_no_date = f"{url}?{query_string_no_date}"
    
    req_no_date = urllib.request.Request(full_url_no_date)
    req_no_date.add_header("X-API-Key", API_KEY)
    req_no_date.add_header("Content-Type", "application/json")
    req_no_date.add_header("User-Agent", "Mozilla/5.0")
    
    try:
        with urllib.request.urlopen(req_no_date, timeout=30) as response:
            result_no_date = json.loads(response.read().decode())
            fixtures_no_date = result_no_date.get("data", [])
            
            print(f"✅ Status: {response.getcode()}")
            print(f"📊 Fixtures returned: {len(fixtures_no_date)}")
            print(f"⚠️  Note: API defaults to returning fixtures from 3 days ago")
            
            if fixtures_no_date:
                print(f"\n📅 Sample dates in response:")
                dates = [f.get("date") for f in fixtures_no_date[:5] if f.get("date")]
                print(f"   {dates}")
                
                print(f"\n🎮 First 3 games returned:")
                for i, game in enumerate(fixtures_no_date[:3], 1):
                    home_team = game.get("home_team", {})
                    away_team = game.get("away_team", {})
                    home_name = home_team.get("name", "Unknown") if isinstance(home_team, dict) else str(home_team)
                    away_name = away_team.get("name", "Unknown") if isinstance(away_team, dict) else str(away_team)
                    print(f"  {i}. {away_name} @ {home_name} | Date: {game.get('date')}")
            else:
                print(f"\n⚠️  No fixtures returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"""
Direct API Call (with date filter):
  - Uses: start_date_after={today}
  - Returns: Games from today onwards
  - Result: {len(fixtures) if 'fixtures' in locals() else 'N/A'} games

Existing Tool (no date filter):
  - Uses: sport=basketball, league=nba (no date params)
  - Returns: Games from 3 days ago (API default)
  - Result: {len(fixtures_no_date) if 'fixtures_no_date' in locals() else 'N/A'} games

ISSUE: The existing tool does NOT support date filtering!
       It cannot get "tonight's" games - it gets games from 3 days ago.
""")

if __name__ == "__main__":
    fetch_nba_games_tonight()

