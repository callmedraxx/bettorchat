#!/bin/bash
# Monitor fixture streaming logs

echo "=== Monitoring Fixture Streaming Logs ==="
echo "Watching for:"
echo "  - fetch_upcoming_games calls"
echo "  - FixtureStreamManager operations"
echo "  - SSE stream connections"
echo "  - Fixture data pushes"
echo "  - Session subscriptions"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

docker logs chatbot-api --follow --tail 0 2>&1 | \
  grep --line-buffered -iE "(fetch_upcoming_games|FixtureStreamManager|fixture.*stream|/fixtures/stream|CRITICAL|Pushing.*fixtures|Subscribed session|Found.*connections|fixture_data|type.*fixtures|session_id|No active connections|Error.*fixture|Error.*stream)" | \
  while IFS= read -r line; do
    timestamp=$(date '+%H:%M:%S')
    echo "[$timestamp] $line"
  done

