#!/bin/bash
set -e

# This script ensures the database exists on every container start
# It runs after PostgreSQL is up, so we can use psql commands

DB_NAME="${POSTGRES_DB:-bettorchatdb}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

echo "Checking if database '${DB_NAME}' exists..."

# Wait for PostgreSQL to be ready
until pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 1
done

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

echo "Database '${DB_NAME}' is ensured to exist."

