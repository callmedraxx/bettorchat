"""
Migration script to fix odds_timestamp column precision to accommodate Unix timestamps.

The original column was Numeric(15, 6) which only allows 9 digits before the decimal.
Unix timestamps can be 10 digits, so we need to increase to Numeric(20, 6).
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

def run_migration():
    """Alter odds_timestamp column to increase precision."""
    print("Starting migration: Fix odds_timestamp precision")
    
    # Check if DATABASE_URL is configured
    if not settings.DATABASE_URL:
        print("No DATABASE_URL configured. Skipping migration.")
        return
    
    # Use the same engine configuration as the main app
    is_postgresql = settings.DATABASE_URL.startswith("postgresql")
    
    if is_postgresql:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
        )
    else:
        engine = create_engine(settings.DATABASE_URL)
    
    try:
        # Check if table exists
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if "odds_entries" not in existing_tables:
            print("Table 'odds_entries' does not exist. Skipping migration.")
            return
        
        # Check current column definition
        columns = inspector.get_columns("odds_entries")
        odds_timestamp_col = next((col for col in columns if col["name"] == "odds_timestamp"), None)
        
        if not odds_timestamp_col:
            print("Column 'odds_timestamp' does not exist. Skipping migration.")
            return
        
        # Check if already migrated (precision >= 20)
        current_type = str(odds_timestamp_col["type"])
        if "NUMERIC(20" in current_type.upper() or "NUMERIC(20," in current_type.upper():
            print("Column 'odds_timestamp' already has precision >= 20. Skipping migration.")
            return
        
        print(f"Current odds_timestamp type: {current_type}")
        print("Altering column to NUMERIC(20, 6)...")
        
        with engine.begin() as conn:
            # Alter column to increase precision
            # PostgreSQL allows altering numeric precision
            conn.execute(text("""
                ALTER TABLE odds_entries 
                ALTER COLUMN odds_timestamp TYPE NUMERIC(20, 6)
            """))
            
            print("Successfully altered 'odds_timestamp' column to NUMERIC(20, 6)")
            print("Migration completed successfully")
            
    except Exception as e:
        print(f"ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)

