#!/bin/sh
set -e

# This script runs every time the container starts (via command override)
# It ensures the database exists before PostgreSQL starts accepting connections

echo "PostgreSQL startup script: Ensuring database exists..."

# Wait for PostgreSQL to be ready
until pg_isready -U "${POSTGRES_USER:-postgres}" > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL to be ready..."
    sleep 1
done

# Small delay to ensure PostgreSQL is fully initialized
sleep 3

# Ensure database exists
DB_NAME="${POSTGRES_DB:-bettorchatdb}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

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

echo "Database '${DB_NAME}' ensured to exist."
echo "PostgreSQL is ready."

# Start a background process that periodically checks and ensures database exists
(
    while true; do
        sleep 60  # Check every minute
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "
            SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'
        " > /dev/null 2>&1 || {
            echo "WARNING: Database '${DB_NAME}' not found, recreating..."
            psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
                CREATE DATABASE "${DB_NAME}";
                GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO "$POSTGRES_USER";
EOSQL
        }
    done
) &

wait

