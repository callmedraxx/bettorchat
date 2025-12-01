#!/usr/bin/env python3
"""
Direct test of PythonREPL class with JSON filtering from fixture_active_nfl.json
"""
import sys
import os
import json
import io
from contextlib import redirect_stdout, redirect_stderr

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import just the PythonREPL class
from app.agents.tools.python_tools import PythonREPL

def test_filtering():
    """Test filtering operations."""
    print("=" * 60)
    print("Test 1: Filter games with 'Chiefs' in team name")
    print("=" * 60)
    
    repl = PythonREPL()
    
    # Load JSON data
    with open('fixture_active_nfl.json', 'r') as f:
        data = json.load(f)
        repl.globals['data'] = data
        repl.globals['raw_data'] = json.dumps(data)
    
    result = repl.run('''
import json
fixtures = data.get("data", [])
filtered = [f for f in fixtures if "Chiefs" in f.get("home_team_display", "") or "Chiefs" in f.get("away_team_display", "")]
print(f"Found {len(filtered)} games with Chiefs")
for fixture in filtered[:3]:
    print(f"  {fixture.get('away_team_display')} @ {fixture.get('home_team_display')} - {fixture.get('start_date')}")
    ''')
    print(result)
    assert "Found" in result and "Chiefs" in result
    print("✓ Passed\n")

def test_date_filtering():
    """Test filtering by date."""
    print("=" * 60)
    print("Test 2: Filter games on 2025-11-27")
    print("=" * 60)
    
    repl = PythonREPL()
    with open('fixture_active_nfl.json', 'r') as f:
        data = json.load(f)
        repl.globals['data'] = data
        repl.globals['raw_data'] = json.dumps(data)
    
    result = repl.run('''
target_date = "2025-11-27"
fixtures = data.get("data", [])
filtered = [f for f in fixtures if f.get("start_date", "").startswith(target_date)]
print(f"Found {len(filtered)} games on {target_date}")
for fixture in filtered:
    print(f"  {fixture.get('away_team_display')} @ {fixture.get('home_team_display')}")
    ''')
    print(result)
    assert "Found" in result
    print("✓ Passed\n")

def test_expression_return():
    """Test expression evaluation."""
    print("=" * 60)
    print("Test 3: Expression - Count games by week")
    print("=" * 60)
    
    repl = PythonREPL()
    with open('fixture_active_nfl.json', 'r') as f:
        data = json.load(f)
        repl.globals['data'] = data
        repl.globals['raw_data'] = json.dumps(data)
    
    result = repl.run('''
from collections import Counter
fixtures = data.get("data", [])
week_counts = Counter(f.get("season_week", "Unknown") for f in fixtures)
json.dumps(dict(week_counts), indent=2)
    ''')
    print(result)
    assert "13" in result or "14" in result
    print("✓ Passed\n")

def test_complex_filtering():
    """Test complex filtering."""
    print("=" * 60)
    print("Test 4: Complex filter - Week 13 games with odds")
    print("=" * 60)
    
    repl = PythonREPL()
    with open('fixture_active_nfl.json', 'r') as f:
        data = json.load(f)
        repl.globals['data'] = data
        repl.globals['raw_data'] = json.dumps(data)
    
    result = repl.run('''
fixtures = data.get("data", [])
filtered = [f for f in fixtures if f.get("season_week") == "13" and f.get("has_odds") == True]
print(f"Found {len(filtered)} games in week 13 with odds")
json.dumps([{"id": f.get("id"), "game": f"{f.get('away_team_display')} @ {f.get('home_team_display')}"} for f in filtered[:5]], indent=2)
    ''')
    print(result)
    assert "Found" in result and "week 13" in result.lower()
    print("✓ Passed\n")

def test_sorting():
    """Test sorting."""
    print("=" * 60)
    print("Test 5: Sort games by start date")
    print("=" * 60)
    
    repl = PythonREPL()
    with open('fixture_active_nfl.json', 'r') as f:
        data = json.load(f)
        repl.globals['data'] = data
        repl.globals['raw_data'] = json.dumps(data)
    
    result = repl.run('''
fixtures = data.get("data", [])
sorted_fixtures = sorted(fixtures, key=lambda x: x.get("start_date", ""))
print(f"Sorted {len(sorted_fixtures)} fixtures by date")
print("First 3 games:")
for fixture in sorted_fixtures[:3]:
    print(f"  {fixture.get('start_date')}: {fixture.get('away_team_display')} @ {fixture.get('home_team_display')}")
    ''')
    print(result)
    assert "Sorted" in result
    print("✓ Passed\n")

def test_aggregation():
    """Test aggregation."""
    print("=" * 60)
    print("Test 6: Count games per team")
    print("=" * 60)
    
    repl = PythonREPL()
    with open('fixture_active_nfl.json', 'r') as f:
        data = json.load(f)
        repl.globals['data'] = data
        repl.globals['raw_data'] = json.dumps(data)
    
    result = repl.run('''
from collections import Counter
fixtures = data.get("data", [])
all_teams = []
for f in fixtures:
    all_teams.append(f.get("home_team_display"))
    all_teams.append(f.get("away_team_display"))
team_counts = Counter(all_teams)
print(f"Total team appearances: {len(all_teams)}")
print(f"Unique teams: {len(team_counts)}")
print("Top 5 teams:")
for team, count in team_counts.most_common(5):
    print(f"  {team}: {count} games")
    ''')
    print(result)
    assert "Total team appearances" in result
    print("✓ Passed\n")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Testing Python REPL Tool with JSON Filtering")
    print("=" * 60 + "\n")
    
    try:
        test_filtering()
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

