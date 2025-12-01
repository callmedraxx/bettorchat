#!/bin/bash
set -e

echo "Waiting for database to be ready..."

# Wait for PostgreSQL to be ready
# In Docker Compose, the postgres service is accessible at hostname "postgres"
if [ -n "$DATABASE_URL" ] && command -v pg_isready > /dev/null 2>&1; then
    echo "Waiting for PostgreSQL to be ready..."
    # Try to extract host from DATABASE_URL, default to "postgres" for Docker Compose
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p' || echo "postgres")
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p' || echo "5432")
    
    # Default to postgres:5432 if parsing failed
    if [ -z "$DB_HOST" ] || [ "$DB_HOST" = "$DATABASE_URL" ]; then
        DB_HOST="postgres"
    fi
    if [ -z "$DB_PORT" ] || [ "$DB_PORT" = "$DATABASE_URL" ]; then
        DB_PORT="5432"
    fi
    
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U postgres > /dev/null 2>&1; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            echo "ERROR: PostgreSQL did not become ready after $MAX_RETRIES attempts"
            exit 1
        fi
        echo "PostgreSQL is unavailable - sleeping (attempt $RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    done
    echo "PostgreSQL is ready!"
elif [ -n "$DATABASE_URL" ]; then
    echo "WARNING: pg_isready not available, skipping database readiness check"
    echo "Waiting 5 seconds for database to initialize..."
    sleep 5
fi

# Ensure the database exists before running migrations
if [ -n "$DATABASE_URL" ] && python -c "import psycopg2" > /dev/null 2>&1; then
    echo "Ensuring database exists..."
    python << EOF
import os
import sys
from urllib.parse import urlparse

try:
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        sys.exit(0)
    
    # Parse the database URL
    parsed = urlparse(database_url)
    db_name = parsed.path.lstrip('/').split('?')[0]
    
    if not db_name:
        db_name = 'bettorchatdb'
    
    # Create connection URL to postgres database (which always exists)
    admin_url = f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres"
    
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    
    # Connect to postgres database to check/create target database
    conn = psycopg2.connect(admin_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    exists = cursor.fetchone()
    
    if exists:
        print(f"Database '{db_name}' already exists.")
    else:
        print(f"Creating database '{db_name}'...")
        cursor.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Database '{db_name}' created successfully.")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"WARNING: Could not verify/create database: {e}")
    print("Continuing anyway - database may already exist or will be created by PostgreSQL")
    sys.exit(0)
EOF
elif [ -n "$DATABASE_URL" ]; then
    echo "WARNING: psycopg2 not available, cannot verify database exists"
    echo "Database should be created automatically by PostgreSQL container"
fi

echo "Running database migrations..."

# Run migration scripts with better error handling
cd /app
if python migrations/add_tool_result_structured_data.py; then
    echo "Migration add_tool_result_structured_data completed successfully"
else
    echo "WARNING: Migration add_tool_result_structured_data failed or already applied"
fi

if python migrations/create_odds_entries_table.py; then
    echo "Migration create_odds_entries_table completed successfully"
else
    echo "ERROR: Migration create_odds_entries_table failed!"
    echo "This is critical - the odds_entries table is required."
    exit 1
fi

if python migrations/fix_odds_timestamp_precision.py; then
    echo "Migration fix_odds_timestamp_precision completed successfully"
else
    echo "WARNING: Migration fix_odds_timestamp_precision failed or already applied"
fi

echo "Starting application..."

# Execute the main command
exec "$@"

