"""
Migration script to add structured_data column and common field columns to tool_results table.

Run this script to update the database schema:
    python migrations/add_tool_result_structured_data.py

Or execute the SQL directly in your database.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base
from app.models.tool_result import ToolResult
from sqlalchemy import text
from app.core.config import settings

def migrate():
    """Add structured_data column and common field columns to tool_results table."""
    
    print("Starting migration: Add structured_data and common fields to tool_results table")
    
    # Check if we're using PostgreSQL or SQLite
    is_postgresql = (
        settings.ENVIRONMENT == "production" 
        and settings.DATABASE_URL 
        and "postgresql" in settings.DATABASE_URL
    )
    
    with engine.begin() as conn:  # Use begin() for automatic transaction management
        # Check if columns already exist
        if is_postgresql:
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'tool_results' 
                AND column_name IN ('structured_data', 'fixture_id', 'team_id', 'player_id', 'league_id')
            """)
        else:
            # SQLite
            check_query = text("""
                SELECT name 
                FROM pragma_table_info('tool_results') 
                WHERE name IN ('structured_data', 'fixture_id', 'team_id', 'player_id', 'league_id')
            """)
        
        existing_columns = [row[0] for row in conn.execute(check_query)]
        
        if 'structured_data' in existing_columns:
            print("Migration already applied - columns exist. Skipping.")
            return
        
        print("Adding new columns...")
        
        # Add columns
        if is_postgresql:
            # PostgreSQL: Use JSONB for structured_data
            conn.execute(text("""
                ALTER TABLE tool_results 
                ADD COLUMN IF NOT EXISTS structured_data JSONB,
                ADD COLUMN IF NOT EXISTS fixture_id VARCHAR,
                ADD COLUMN IF NOT EXISTS team_id VARCHAR,
                ADD COLUMN IF NOT EXISTS player_id VARCHAR,
                ADD COLUMN IF NOT EXISTS league_id VARCHAR
            """))
            
            # Add indexes
            print("Creating indexes...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_fixture_id ON tool_results(fixture_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_team_id ON tool_results(team_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_player_id ON tool_results(player_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_league_id ON tool_results(league_id)"))
            
            # Add GIN index for JSONB queries (PostgreSQL only)
            print("Creating GIN index for JSONB queries...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_structured_data_gin ON tool_results USING GIN (structured_data)"))
        else:
            # SQLite: Use JSON for structured_data
            # SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN, so we check first
            try:
                conn.execute(text("""
                    ALTER TABLE tool_results 
                    ADD COLUMN structured_data JSON
                """))
            except Exception:
                pass  # Column might already exist
            
            try:
                conn.execute(text("ALTER TABLE tool_results ADD COLUMN fixture_id VARCHAR"))
            except Exception:
                pass
            
            try:
                conn.execute(text("ALTER TABLE tool_results ADD COLUMN team_id VARCHAR"))
            except Exception:
                pass
            
            try:
                conn.execute(text("ALTER TABLE tool_results ADD COLUMN player_id VARCHAR"))
            except Exception:
                pass
            
            try:
                conn.execute(text("ALTER TABLE tool_results ADD COLUMN league_id VARCHAR"))
            except Exception:
                pass
            
            # Add indexes
            print("Creating indexes...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_fixture_id ON tool_results(fixture_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_team_id ON tool_results(team_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_player_id ON tool_results(player_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tool_results_league_id ON tool_results(league_id)"))
        
        print("Migration completed successfully!")
        
        # Optionally migrate existing data
        print("\nWould you like to migrate existing data? (parse full_result and populate structured_data)")
        print("This can be done later by running: python migrations/migrate_existing_tool_results.py")
        print("Or manually by calling save_tool_result_to_db() again for existing records.")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

