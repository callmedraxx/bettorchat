"""
Migration script to create odds_entries table for storing individual odds entries.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
from app.core.database import Base
from app.models.odds_entry import OddsEntry

def run_migration():
    """Create odds_entries table if it doesn't exist."""
    print("Starting migration: Create odds_entries table")
    
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
        # Check if table already exists
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if "odds_entries" in existing_tables:
            print("Table 'odds_entries' already exists. Skipping.")
            return
        
        print("Creating 'odds_entries' table...")
        
        # Create table - create_all handles transactions internally
        Base.metadata.create_all(bind=engine, tables=[OddsEntry.__table__])
        
        # Verify table was created
        inspector = inspect(engine)
        if "odds_entries" in inspector.get_table_names():
            print("Successfully created 'odds_entries' table")
            print("Migration completed successfully")
        else:
            raise Exception("Table creation appeared to succeed but table not found")
            
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

