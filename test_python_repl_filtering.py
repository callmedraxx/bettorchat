#!/usr/bin/env python3
"""
Test script for Python REPL tool with JSON filtering from fixture_active_nfl.json
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.tools.python_tools import python_repl

def test_basic_filtering():
    """Test basic filtering operations."""
    print("=" * 60)
    print("Test 1: Basic Filtering - Get games with specific team")
    print("=" * 60)
    
    # Load the JSON data
    with open('fixture_active_nfl.json', 'r') as f:
        json_data = json.dumps(json.load(f))
    
    # Filter for games with "Chiefs" in team name
    result = python_repl(
        command='''
import json
data = json.loads(raw_data)
fixtures = data.get("data", [])
filtered = [f for f in fixtures if "Chiefs" in f.get("home_team_display", "") or "Chiefs" in f.get("away_team_display", "")]
print(f"Found {len(filtered)} games with Chiefs")
for fixture in filtered[:3]:  # Show first 3
    print(f"  {fixture.get('away_team_display')} @ {fixture.get('home_team_display')} - {fixture.get('start_date')}")
        ''',
        data=json_data
    )
    print(result)
    assert "Found" in result and "Chiefs" in result
    print("✓ Passed\n")

def test_date_filtering():
    """Test filtering by date."""
    print("=" * 60)
    print("Test 2: Date Filtering - Get games on specific date")
    print("=" * 60)
    
    with open('fixture_active_nfl.json', 'r') as f:
        json_data = json.dumps(json.load(f))
    
    result = python_repl(
        command='''
import json
from datetime import datetime
data = json.loads(raw_data)
fixtures = data.get("data", [])
# Filter for games on 2025-11-27
target_date = "2025-11-27"
filtered = [f for f in fixtures if f.get("start_date", "").startswith(target_date)]
print(f"Found {len(filtered)} games on {target_date}")
for fixture in filtered:
    print(f"  {fixture.get('away_team_display')} @ {fixture.get('home_team_display')}")
        ''',
        data=json_data
    )
    print(result)
    assert "Found" in result and "2025-11-27" in result
    print("✓ Passed\n")

def test_expression_return():
    """Test expression evaluation (returning values)."""
    print("=" * 60)
    print("Test 3: Expression Return - Count games by week")
    print("=" * 60)
    
    with open('fixture_active_nfl.json', 'r') as f:
        json_data = json.dumps(json.load(f))
    
    result = python_repl(
        command='''
import json
from collections import Counter
data = json.loads(raw_data)
fixtures = data.get("data", [])
week_counts = Counter(f.get("season_week", "Unknown") for f in fixtures)
dict(week_counts)
        ''',
        data=json_data
    )
    print(result)
    assert "13" in result or "14" in result or "15" in result  # Should have week numbers
    print("✓ Passed\n")

def test_complex_filtering():
    """Test complex filtering with multiple conditions."""
    print("=" * 60)
    print("Test 4: Complex Filtering - Games in week 13 with odds available")
    print("=" * 60)
    
    with open('fixture_active_nfl.json', 'r') as f:
        json_data = json.dumps(json.load(f))
    
    result = python_repl(
        command='''
import json
data = json.loads(raw_data)
fixtures = data.get("data", [])
filtered = [
    f for f in fixtures 
    if f.get("season_week") == "13" 
    and f.get("has_odds") == True
]
print(f"Found {len(filtered)} games in week 13 with odds available")
json.dumps([{"id": f.get("id"), "game": f"{f.get('away_team_display')} @ {f.get('home_team_display')}"} for f in filtered[:5]], indent=2)
        ''',
        data=json_data
    )
    print(result)
    assert "Found" in result and "week 13" in result.lower()
    print("✓ Passed\n")

def test_sorting():
    """Test sorting operations."""
    print("=" * 60)
    print("Test 5: Sorting - Sort games by start date")
    print("=" * 60)
    
    with open('fixture_active_nfl.json', 'r') as f:
        json_data = json.dumps(json.load(f))
    
    result = python_repl(
        command='''
import json
data = json.loads(raw_data)
fixtures = data.get("data", [])
sorted_fixtures = sorted(fixtures, key=lambda x: x.get("start_date", ""))
print(f"Sorted {len(sorted_fixtures)} fixtures by date")
print("First 3 games:")
for fixture in sorted_fixtures[:3]:
    print(f"  {fixture.get('start_date')}: {fixture.get('away_team_display')} @ {fixture.get('home_team_display')}")
        ''',
        data=json_data
    )
    print(result)
    assert "Sorted" in result and "First 3 games" in result
    print("✓ Passed\n")

def test_aggregation():
    """Test data aggregation."""
    print("=" * 60)
    print("Test 6: Aggregation - Count games per team")
    print("=" * 60)
    
    with open('fixture_active_nfl.json', 'r') as f:
        json_data = json.dumps(json.load(f))
    
    result = python_repl(
        command='''
import json
from collections import Counter
data = json.loads(raw_data)
fixtures = data.get("data", [])
all_teams = []
for f in fixtures:
    all_teams.append(f.get("home_team_display"))
    all_teams.append(f.get("away_team_display"))
team_counts = Counter(all_teams)
print(f"Total team appearances: {len(all_teams)}")
print(f"Unique teams: {len(team_counts)}")
print("Top 5 teams by game count:")
for team, count in team_counts.most_common(5):
    print(f"  {team}: {count} games")
        ''',
        data=json_data
    )
    print(result)
    assert "Total team appearances" in result and "Unique teams" in result
    print("✓ Passed\n")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Testing Python REPL Tool with JSON Filtering")
    print("=" * 60 + "\n")
    
    try:
        test_basic_filtering()
        test_date_filtering()
        test_expression_return()
        test_complex_filtering()
        test_sorting()
        test_aggregation()
        
        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

