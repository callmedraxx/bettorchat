#!/bin/bash
# Comprehensive fixture streaming log monitor

echo "=========================================="
echo "FIXTURE STREAMING LOG MONITOR"
echo "=========================================="
echo "Monitoring for:"
echo "  ✓ fetch_upcoming_games tool calls"
echo "  ✓ FixtureStreamManager operations"
echo "  ✓ SSE stream endpoint access (/fixtures/stream)"
echo "  ✓ Session subscriptions"
echo "  ✓ Fixture data pushes"
echo "  ✓ Connection status"
echo ""
echo "Ready! Trigger a conversation in the frontend now."
echo "=========================================="
echo ""

# Follow logs with comprehensive filtering
docker logs chatbot-api --follow --tail 0 2>&1 | \
  grep --line-buffered --color=always -iE "(fetch_upcoming_games|FixtureStreamManager|/fixtures/stream|CRITICAL|Pushing.*fixtures|Subscribed session|Found.*connections|fixture_data|type.*fixtures|session_id|No active connections|Error.*fixture|Error.*stream|GET.*stream|POST.*fixtures)" | \
  sed 's/^/['$(date +%H:%M:%S)'] /'

