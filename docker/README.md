# Database Persistence Solution

This directory contains scripts to ensure the `bettorchatdb` database is **always** available, even if it gets accidentally deleted.

## Problem

The PostgreSQL Docker image only creates the database specified in `POSTGRES_DB` on **first initialization** when the data directory is empty. If the database is deleted later (e.g., by a script, migration, or manual action), it won't be automatically recreated.

## Solution

1. **Initialization Script** (`postgres-init/01-init-db.sh`): Runs on first container startup to create the database
2. **Always-Ensure Script** (`ensure-db-always.sh`): Runs via healthcheck to recreate the database if it's missing
3. **Named Volume** (`bettorchat_postgres_data`): Explicitly named volume to prevent accidental deletion

## How It Works

The healthcheck in `docker-compose.yml`:
- Checks if PostgreSQL is ready
- Verifies the `bettorchatdb` database exists
- If missing, runs `ensure-db-always.sh` to recreate it automatically
- Retries up to 20 times with 15-second start period

## Protecting Your Data

To prevent accidental data loss:

1. **Never run**: `docker-compose down -v` (this deletes volumes!)
2. **Use**: `docker-compose down` (keeps volumes intact)
3. **Backup regularly**: Use `docker exec bettorchat-postgres pg_dump -U postgres bettorchatdb > backup.sql`

## Files

- `postgres-init/01-init-db.sh`: Creates database on first initialization
- `ensure-db-always.sh`: Ensures database exists on every healthcheck (can be run manually)
- `postgres-entrypoint-wrapper.sh`: Alternative wrapper approach (not currently used)
- `postgres-startup.sh`: Alternative startup script (not currently used)

