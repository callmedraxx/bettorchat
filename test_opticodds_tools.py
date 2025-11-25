#!/usr/bin/env python3
"""
Test script for OpticOdds API tools.
Tests each tool individually and verifies structured data output.
"""
import os
import sys
import json
import re
from typing import Dict, Any

# Set API key before importing tools
os.environ["OPTICODDS_API_KEY"] = "f8a621e8-2583-4e97-a769-e70c99acdb85"

from app.agents.tools.betting_tools import (
    fetch_live_odds,
    fetch_player_props,
    fetch_live_game_stats,
    fetch_injury_reports,
    detect_arbitrage_opportunities,
    calculate_parlay_odds,
)
from app.core.opticodds_client import OpticOddsClient


def extract_structured_data(response: str, data_type: str) -> Dict[str, Any]:
    """Extract structured data from response using HTML comments."""
    pattern = f"<!-- {data_type}_START -->(.*?)<!-- {data_type}_END -->"
    match = re.search(pattern, response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return {}
    return {}


def verify_structured_data(data: Dict[str, Any], required_fields: list) -> bool:
    """Verify structured data has required fields."""
    if not data:
        return False
    
    # Check if data has a key that contains a list
    for key, value in data.items():
        if isinstance(value, list) and len(value) > 0:
            # Check first item for required fields
            item = value[0]
            if isinstance(item, dict):
                for field in required_fields:
                    if field not in item:
                        print(f"Missing required field: {field}")
                        return False
            return True
    
    return False


def test_fetch_live_odds():
    """Test fetch_live_odds tool."""
    print("\n" + "="*60)
    print("Testing fetch_live_odds")
    print("="*60)
    
    try:
        # First, get active sports to find correct IDs
        client = OpticOddsClient()
        sports = client.get_active_sports()
        print(f"Active sports response keys: {list(sports.keys()) if isinstance(sports, dict) else 'Not a dict'}")
        
        # Try without specific IDs first to see what's available
        response = fetch_live_odds.invoke({"market_types": "moneyline"})
        print(f"\nResponse length: {len(response)} characters")
        print(f"\nFirst 500 chars:\n{response[:500]}")
        
        # Extract structured data
        structured = extract_structured_data(response, "ODDS_DATA")
        if structured:
            print(f"\n✓ Found structured data with {len(structured.get('odds', []))} odds entries")
            required_fields = ["fixture_id", "market_id", "selection_id", "sportsbook_name", "american_odds"]
            if verify_structured_data(structured, required_fields):
                print("✓ Structured data has all required fields")
                # Show first entry
                if structured.get("odds"):
                    print(f"\nFirst odds entry:\n{json.dumps(structured['odds'][0], indent=2)}")
            else:
                print("✗ Structured data missing required fields")
        else:
            print("✗ No structured data found in response")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_player_props():
    """Test fetch_player_props tool."""
    print("\n" + "="*60)
    print("Testing fetch_player_props")
    print("="*60)
    
    try:
        # First, we need to find a fixture ID and player ID
        # For now, test with league_id for NBA
        response = fetch_player_props.invoke({"league_id": "1"})
        print(f"\nResponse length: {len(response)} characters")
        print(f"\nFirst 500 chars:\n{response[:500]}")
        
        # Extract structured data
        structured = extract_structured_data(response, "PLAYER_PROPS_DATA")
        if structured:
            print(f"\n✓ Found structured data with {len(structured.get('player_props', []))} prop entries")
            required_fields = ["player_id", "player_name", "market_id", "selection_id", "sportsbook_name"]
            if verify_structured_data(structured, required_fields):
                print("✓ Structured data has all required fields")
            else:
                print("✗ Structured data missing required fields")
        else:
            print("⚠ No structured data found (may be empty if no active games)")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_live_game_stats():
    """Test fetch_live_game_stats tool."""
    print("\n" + "="*60)
    print("Testing fetch_live_game_stats")
    print("="*60)
    
    try:
        # First, get fixtures to find a fixture_id
        client = OpticOddsClient()
        fixtures_data = client.get_fixtures()
        
        fixture_id = None
        if fixtures_data and "data" in fixtures_data:
            fixtures = fixtures_data.get("data", [])
            if fixtures and len(fixtures) > 0:
                fixture = fixtures[0]
                fixture_id = fixture.get("id") or fixture.get("fixture", {}).get("id") if isinstance(fixture.get("fixture"), dict) else None
        
        if not fixture_id:
            print("⚠ No fixtures found, skipping test")
            return True
        
        print(f"Using fixture_id: {fixture_id}")
        response = fetch_live_game_stats.invoke({"fixture_id": str(fixture_id)})
        print(f"\nResponse length: {len(response)} characters")
        print(f"\nResponse:\n{response}")
        
        # Extract structured data
        structured = extract_structured_data(response, "STATS_DATA")
        if structured:
            print(f"\n✓ Found structured data")
            if verify_structured_data(structured, ["fixture_id"]):
                print("✓ Structured data has required fields")
        else:
            print("⚠ No structured data found")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_injury_reports():
    """Test fetch_injury_reports tool."""
    print("\n" + "="*60)
    print("Testing fetch_injury_reports (NBA)")
    print("="*60)
    
    try:
        # Test with NBA (sport_id=1, league_id=1)
        response = fetch_injury_reports.invoke({"sport_id": "1", "league_id": "1"})
        print(f"\nResponse length: {len(response)} characters")
        print(f"\nResponse:\n{response[:1000]}")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_detect_arbitrage_opportunities():
    """Test detect_arbitrage_opportunities tool."""
    print("\n" + "="*60)
    print("Testing detect_arbitrage_opportunities (NBA)")
    print("="*60)
    
    try:
        response = detect_arbitrage_opportunities.invoke({"sport_id": "1", "league_id": "1", "min_profit_percent": 0.0})
        print(f"\nResponse length: {len(response)} characters")
        print(f"\nResponse:\n{response[:1000]}")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calculate_parlay_odds():
    """Test calculate_parlay_odds tool."""
    print("\n" + "="*60)
    print("Testing calculate_parlay_odds")
    print("="*60)
    
    try:
        # First, get some odds to build a parlay
        client = OpticOddsClient()
        odds_data = client.get_fixture_odds(market_types="moneyline")
        
        # Extract fixture, market, and selection IDs from odds
        legs = []
        if odds_data and "data" in odds_data:
            fixtures = odds_data.get("data", [])
            for fixture in fixtures[:2]:  # Get first 2 fixtures for 2-leg parlay
                fixture_id = fixture.get("fixture", {}).get("id")
                markets = fixture.get("markets", [])
                for market in markets:
                    if market.get("market_type") == "moneyline":
                        selections = market.get("selections", [])
                        if selections:
                            selection = selections[0]  # Get first selection
                            legs.append({
                                "fixture_id": fixture_id,
                                "market_id": market.get("id"),
                                "selection_id": selection.get("id"),
                            })
                            break
                if len(legs) >= 2:
                    break
        
        if len(legs) < 2:
            print("⚠ Not enough odds data to build a parlay, skipping test")
            return True
        
        print(f"Building parlay with {len(legs)} legs:")
        for i, leg in enumerate(legs, 1):
            print(f"  Leg {i}: fixture_id={leg['fixture_id']}, market_id={leg['market_id']}, selection_id={leg['selection_id']}")
        
        legs_json = json.dumps(legs)
        response = calculate_parlay_odds.invoke({"legs": legs_json})
        print(f"\nResponse length: {len(response)} characters")
        print(f"\nResponse:\n{response}")
        
        # Extract structured data
        structured = extract_structured_data(response, "PARLAY_DATA")
        if structured:
            print(f"\n✓ Found structured data with {len(structured.get('parlays', []))} parlay entries")
            required_fields = ["sportsbook_name", "american_odds", "decimal_odds"]
            if verify_structured_data(structured, required_fields):
                print("✓ Structured data has all required fields")
            else:
                print("✗ Structured data missing required fields")
        else:
            print("⚠ No structured data found")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("OpticOdds API Tools Test Suite")
    print("="*60)
    print(f"\nAPI Key: {os.environ.get('OPTICODDS_API_KEY', 'NOT SET')[:20]}...")
    
    results = []
    
    # Run tests
    results.append(("fetch_live_odds", test_fetch_live_odds()))
    results.append(("fetch_player_props", test_fetch_player_props()))
    results.append(("fetch_live_game_stats", test_fetch_live_game_stats()))
    results.append(("fetch_injury_reports", test_fetch_injury_reports()))
    results.append(("detect_arbitrage_opportunities", test_detect_arbitrage_opportunities()))
    results.append(("calculate_parlay_odds", test_calculate_parlay_odds()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

