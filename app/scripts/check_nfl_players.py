#!/usr/bin/env python3
"""
Quick script to check if NFL players are in the database.
"""
import sys

# Add /app to path
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from app.core.nfl_players_db import get_player_count, get_players_by_team
from app.core.nfl_teams import get_team_by_name

def main():
    print("=" * 60)
    print("NFL Players Database Check")
    print("=" * 60)
    
    # Get total count
    count = get_player_count()
    print(f"\nTotal players in database: {count}")
    
    if count > 0:
        # Test a team lookup
        detroit_lions = get_team_by_name("Detroit Lions")
        if detroit_lions:
            team_id = detroit_lions.get("id")
            players = get_players_by_team(team_id, active_only=True)
            print(f"\nSample: Detroit Lions has {len(players)} players in database")
            if players:
                print(f"  Example: {players[0].name} (ID: {players[0].id})")
        
        print("\n✅ Database contains players!")
    else:
        print("\n❌ Database is empty - run fetch script first")
    
    print("=" * 60)
    return 0 if count > 0 else 1

if __name__ == "__main__":
    sys.exit(main())

