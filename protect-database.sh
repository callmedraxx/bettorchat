#!/bin/bash
# Script to protect database volume from accidental deletion

set -e

VOLUME_NAME="bettorchat_postgres_data"

echo "Database Protection Script"
echo "=========================="
echo ""
echo "Checking volume protection status..."

# Check if volume exists
if docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "✓ Volume '$VOLUME_NAME' exists"
    
    # Get volume info
    VOLUME_INFO=$(docker volume inspect "$VOLUME_NAME" | grep -A 5 '"Mountpoint"')
    echo "Volume location: $VOLUME_INFO"
    
    # Check if we can add a protection marker
    echo ""
    echo "To protect your database:"
    echo "1. Never run: docker-compose down -v"
    echo "2. Always use: docker-compose down"
    echo "3. Backup your database regularly"
    echo ""
    echo "To backup now, run:"
    echo "  docker exec bettorchat-postgres pg_dump -U postgres bettorchatdb > backup_\$(date +%Y%m%d_%H%M%S).sql"
    echo ""
else
    echo "⚠ Volume '$VOLUME_NAME' does not exist yet"
    echo "It will be created when you run: docker-compose up -d"
fi

