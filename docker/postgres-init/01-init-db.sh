#!/bin/bash
set -e

# This script runs when PostgreSQL container starts
# It ensures the database exists even if the volume was reused/recreated

DB_NAME="${POSTGRES_DB:-bettorchatdb}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

echo "PostgreSQL initialization script starting..."
echo "Ensuring database '${DB_NAME}' exists..."

# Connect to PostgreSQL and ensure database exists
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    -- Create database if it doesn't exist
    SELECT 'CREATE DATABASE "${DB_NAME}"'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')
    \gexec
    
    -- Grant all privileges to the user
    GRANT ALL PRIVILEGES ON DATABASE "${DB_NAME}" TO "$POSTGRES_USER";
EOSQL

echo "Database '${DB_NAME}' ensured to exist."

