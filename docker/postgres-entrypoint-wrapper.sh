#!/bin/bash
set -e

# Wrapper script that ensures database exists on every container start
# This runs after PostgreSQL starts, ensuring the database is always available

DB_NAME="${POSTGRES_DB:-bettorchatdb}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

# Function to ensure database exists
ensure_database() {
    echo "Ensuring database '${DB_NAME}' exists..."
    
    # Wait for PostgreSQL to be fully ready
    until pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; do
        echo "Waiting for PostgreSQL to be ready..."
        sleep 1
    done
    
    # Give it a moment to fully initialize
    sleep 2
    
    # Check and create database if it doesn't exist
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}') THEN
                CREATE DATABASE "${DB_NAME}";
                RAISE NOTICE 'Database "${DB_NAME}" created successfully.';
            ELSE
                RAISE NOTICE 'Database "${DB_NAME}" already exists.';
            END IF;
        END
        \$\$;
        
        -- Ensure user has all privileges
        GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO "$POSTGRES_USER";
EOSQL
    
    echo "Database '${DB_NAME}' is ensured to exist."
}

# Run the database check in the background after a delay
# This gives PostgreSQL time to start
(
    sleep 5
    ensure_database
) &

# Call the original PostgreSQL entrypoint
exec /usr/local/bin/docker-entrypoint.sh "$@"

