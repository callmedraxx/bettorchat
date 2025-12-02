#!/usr/bin/env python3
"""Test the actual URL endpoint to verify prop_type filtering precision."""
import httpx
import json

# Test the URL that was generated
url = 'http://localhost:8000/api/v1/nfl/odds'
params = {
    'prop_type': 'receiving',
    'player_id': 'E207E864C191',
    'group_by_fixture': 'true'
}

print("=" * 80)
print("Testing URL Precision: Receiving Props Only")
print("=" * 80)
print(f"URL: {url}")
print(f"Params: {params}")
print("-" * 80)
print()

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Get fixtures data
            fixtures = data.get('data', [])
            print(f"✅ Response received: {len(fixtures)} fixture(s)")
            print()
            
            # Collect all markets from all fixtures
            all_markets = []
            receiving_markets = []
            non_receiving_markets = []
            
            for fixture in fixtures:
                odds = fixture.get('odds', [])
                for odd in odds:
                    market = odd.get('market', '')
                    if market:
                        all_markets.append(market)
                        
                        # Check if it's a receiving market
                        market_lower = market.lower()
                        if 'receiving' in market_lower:
                            receiving_markets.append(market)
                        elif 'player' in market_lower:
                            # It's a player prop but not receiving
                            if 'passing' in market_lower or 'rushing' in market_lower:
                                non_receiving_markets.append(market)
            
            # Remove duplicates
            all_markets_unique = list(set(all_markets))
            receiving_markets_unique = list(set(receiving_markets))
            non_receiving_markets_unique = list(set(non_receiving_markets))
            
            print(f"Total unique markets found: {len(all_markets_unique)}")
            print(f"Receiving-related markets: {len(receiving_markets_unique)}")
            print(f"Non-receiving player prop markets: {len(non_receiving_markets_unique)}")
            print()
            
            if receiving_markets_unique:
                print("✅ Receiving markets found:")
                for market in sorted(receiving_markets_unique):
                    print(f"   - {market}")
                print()
            
            if non_receiving_markets_unique:
                print("❌ NON-RECEIVING markets found (should NOT be here):")
                for market in sorted(non_receiving_markets_unique):
                    print(f"   - {market}")
                print()
                print("⚠️  PRECISION ISSUE: Non-receiving props are being returned!")
            else:
                print("✅ PRECISION VERIFIED: Only receiving-related markets returned")
                print("   No passing or rushing props found in response")
            
            # Check for any player prop markets that aren't receiving
            player_prop_markets = [m for m in all_markets_unique if 'player' in m.lower() and 'receiving' not in m.lower()]
            if player_prop_markets:
                passing_rushing = [m for m in player_prop_markets if 'passing' in m.lower() or 'rushing' in m.lower()]
                if passing_rushing:
                    print()
                    print("❌ FAILED: Found passing/rushing props when only receiving was requested:")
                    for market in passing_rushing:
                        print(f"   - {market}")
                else:
                    print()
                    print("✅ All player prop markets are receiving-related")
            
            print()
            print("=" * 80)
            print("Summary:")
            print(f"  - Total markets: {len(all_markets_unique)}")
            print(f"  - Receiving markets: {len(receiving_markets_unique)}")
            print(f"  - Non-receiving player props: {len(non_receiving_markets_unique)}")
            
            if len(non_receiving_markets_unique) == 0:
                print()
                print("🎉 SUCCESS: Precision filtering is working correctly!")
                print("   Only receiving props are returned, no passing or rushing props.")
            else:
                print()
                print("⚠️  WARNING: Some non-receiving props were returned")
                
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text[:500])
            
except httpx.ConnectError:
    print("❌ Connection error - is the server running?")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

