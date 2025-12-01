#!/bin/sh
set -e

# This script ensures the database exists on EVERY container start
# It's called by the healthcheck and can be run anytime

DB_NAME="${POSTGRES_DB:-bettorchatdb}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; do
    sleep 1
done

# Give PostgreSQL a moment to fully initialize
sleep 2

# Check if database exists
DB_EXISTS=$(psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null || echo "")

if [ -z "$DB_EXISTS" ]; then
    echo "Database '${DB_NAME}' does not exist. Creating..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
        CREATE DATABASE "${DB_NAME}";
        GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO "$POSTGRES_USER";
EOSQL
    echo "Database '${DB_NAME}' created successfully."
else
    echo "Database '${DB_NAME}' already exists."
fi

exit 0

