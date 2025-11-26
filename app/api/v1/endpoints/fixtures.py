"""
Fixture streaming API endpoints.
Provides SSE endpoint for streaming fixture objects to frontend.
"""
import json
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncIterator, Any
from pydantic import BaseModel, Field

from app.core.fixture_stream import fixture_stream_manager
from app.core.odds_stream import odds_stream_manager
from app.core.fixture_storage import get_fixtures_from_db

# Logger for fixture endpoints
logger = logging.getLogger(__name__)

router = APIRouter()


class SSEEvent(BaseModel):
    """SSE event model for streaming responses."""
    type: str = Field(..., description="Event type: 'connected', 'ping', 'odds', 'fixtures', or 'error'")
    data: Optional[dict] = Field(None, description="Event data payload")
    session_id: Optional[str] = Field(None, description="Session identifier")
    timestamp: Optional[float] = Field(None, description="Event timestamp")
    message: Optional[str] = Field(None, description="Error message (for error events)")


class FixturePushRequest(BaseModel):
    """Request model for pushing fixture data."""
    fixtures: list
    session_id: Optional[str] = None


@router.post("/fixtures/push")
async def push_fixtures(request: FixturePushRequest):
    """
    Push fixture data to the stream queue.
    Called by the agent tool after filtering JSON data.
    
    Args:
        request: FixturePushRequest containing fixtures and optional session_id
        
    Returns:
        Success message
    """
    try:
        if not request.fixtures:
            raise HTTPException(status_code=400, detail="No fixtures provided")
        
        # Use provided session_id or generate one
        session_id = request.session_id or "default"
        
        # Push fixtures to stream manager
        success = await fixture_stream_manager.push_fixtures(
            session_id=session_id,
            fixtures=request.fixtures
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to push fixtures")
        
        return {
            "status": "success",
            "message": f"Pushed {len(request.fixtures)} fixture(s) to stream",
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pushing fixtures: {str(e)}")


@router.get(
    "/fixtures/stream",
    summary="Stream Fixture Data (SSE)",
    description="""
    **Server-Sent Events (SSE) endpoint for streaming fixture notifications to frontend.**
    
    This endpoint streams notification messages when fixtures are fetched by the `fetch_upcoming_games` tool.
    The frontend connects to this endpoint and receives notifications instructing it to fetch fixtures from the API.
    
    **How it works:**
    1. Frontend connects to this endpoint with an optional `session_id`
    2. When `fetch_upcoming_games` tool is called, it saves fixtures to the database and sends a notification to this stream
    3. Frontend receives SSE events with notification messages (not full fixture data)
    4. Frontend should fetch fixtures from `/api/v1/fixtures/fixtures?session_id=<id>` when receiving a notification
    
    **Event Types:**
    - `connected`: Initial connection confirmation
    - `fixtures`: Notification message with action="fetch" (instructs frontend to fetch from API)
    - `ping`: Keep-alive heartbeat (every 30 seconds)
    - `error`: Error message
    
    **Example SSE Event:**
    ```
    data: {"type":"connected","session_id":"user123"}
    
    data: {"type":"fixtures","action":"fetch","session_id":"user123","count":50,"api_endpoint":"/api/v1/fixtures/fixtures?session_id=user123","timestamp":1234567890}
    ```
    
    **Usage:**
    ```javascript
    const eventSource = new EventSource('/api/v1/fixtures/fixtures/stream?session_id=user123');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'fixtures' && data.action === 'fetch') {
            // Fetch fixtures from API endpoint
            fetch(data.api_endpoint)
                .then(res => res.json())
                .then(result => {
                    console.log('Fixtures:', result.fixtures);
                });
        }
    };
    ```
    """,
    response_description="Server-Sent Events stream with fixture data",
    tags=["fixtures", "streaming"]
)
async def stream_fixtures(
    session_id: Optional[str] = Query(
        None, 
        description="Session identifier (user_id or thread_id). Defaults to 'default' if not provided.",
        example="user_123"
    )
):
    """
    Stream fixture objects via Server-Sent Events (SSE).
    
    Returns a continuous stream of fixture data as it becomes available.
    Automatically receives data when `fetch_upcoming_games` tool is called.
    """
    session_id = session_id or "default"
    
    # Log request details
    logger.info(f"[stream_fixtures] ===== SSE CONNECTION REQUEST =====")
    logger.info(f"[stream_fixtures] Session ID: {session_id}")
    logger.info(f"[stream_fixtures] Request received at: {datetime.now().isoformat()}")
    print(f"[CRITICAL stream_fixtures] ===== SSE CONNECTION REQUEST =====")
    print(f"[CRITICAL stream_fixtures] Session ID: {session_id}")
    
    async def generate() -> AsyncIterator[str]:
        """Generator function for SSE streaming."""
        queue = None
        message_count_received = 0
        message_count_sent = 0
        
        try:
            # Subscribe to fixture updates
            logger.info(f"[stream_fixtures] Subscribing to fixture updates for session_id={session_id}")
            print(f"[CRITICAL stream_fixtures] Subscribing to fixture updates for session_id={session_id}")
            queue = await fixture_stream_manager.subscribe(session_id)
            logger.info(f"[stream_fixtures] Successfully subscribed for session_id={session_id}")
            print(f"[CRITICAL stream_fixtures] Successfully subscribed for session_id={session_id}")
            
            # Send initial connection message
            connection_message = {'type': 'connected', 'session_id': session_id}
            message_count_sent += 1
            logger.info(f"[stream_fixtures] SENT message #{message_count_sent}: {json.dumps(connection_message)}")
            print(f"[CRITICAL stream_fixtures] SENT message #{message_count_sent}: type={connection_message['type']}, session_id={connection_message['session_id']}")
            yield f"data: {json.dumps(connection_message)}\n\n"
            
            # Keep connection alive and stream fixture data
            while True:
                try:
                    # Wait for fixture data with timeout
                    fixture_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Log received message
                    message_count_received += 1
                    logger.info(f"[stream_fixtures] RECEIVED message #{message_count_received} from queue for session_id={session_id}")
                    logger.info(f"[stream_fixtures] Message structure: type={fixture_data.get('type', 'unknown')}, keys={list(fixture_data.keys())}")
                    logger.info(f"[stream_fixtures] Full message: {json.dumps(fixture_data, indent=2)}")
                    print(f"[CRITICAL stream_fixtures] RECEIVED message #{message_count_received}: type={fixture_data.get('type', 'unknown')}, session_id={fixture_data.get('session_id', 'N/A')}")
                    if fixture_data.get('action'):
                        print(f"[CRITICAL stream_fixtures] Action: {fixture_data.get('action')}, Count: {fixture_data.get('count', 'N/A')}")
                    
                    # Stream the full JSON data as one SSE event
                    message_count_sent += 1
                    logger.info(f"[stream_fixtures] SENT message #{message_count_sent} to client: {json.dumps(fixture_data)}")
                    print(f"[CRITICAL stream_fixtures] SENT message #{message_count_sent} to client: type={fixture_data.get('type', 'unknown')}")
                    yield f"data: {json.dumps(fixture_data)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    ping_message = {'type': 'ping'}
                    message_count_sent += 1
                    logger.debug(f"[stream_fixtures] SENT ping message #{message_count_sent} (keep-alive)")
                    print(f"[CRITICAL stream_fixtures] SENT ping message #{message_count_sent} (keep-alive)")
                    yield f"data: {json.dumps(ping_message)}\n\n"
                except Exception as e:
                    # Send error and break
                    error_data = {
                        "type": "error",
                        "message": str(e)
                    }
                    message_count_sent += 1
                    logger.error(f"[stream_fixtures] ERROR occurred, SENT error message #{message_count_sent}: {json.dumps(error_data)}")
                    logger.error(f"[stream_fixtures] Exception: {e}", exc_info=True)
                    print(f"[CRITICAL stream_fixtures] ERROR: {str(e)}")
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break
                    
        except Exception as e:
            error_data = {
                "type": "error",
                "message": f"Stream error: {str(e)}"
            }
            logger.error(f"[stream_fixtures] Stream error occurred: {e}", exc_info=True)
            logger.error(f"[stream_fixtures] SENT error message: {json.dumps(error_data)}")
            print(f"[CRITICAL stream_fixtures] Stream error: {str(e)}")
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Cleanup: unsubscribe from updates
            logger.info(f"[stream_fixtures] ===== CONNECTION CLOSING =====")
            logger.info(f"[stream_fixtures] Session ID: {session_id}")
            logger.info(f"[stream_fixtures] Total messages received: {message_count_received}")
            logger.info(f"[stream_fixtures] Total messages sent: {message_count_sent}")
            logger.info(f"[stream_fixtures] Cleaning up connection for session_id={session_id}")
            print(f"[CRITICAL stream_fixtures] ===== CONNECTION CLOSING =====")
            print(f"[CRITICAL stream_fixtures] Session ID: {session_id}, Received: {message_count_received}, Sent: {message_count_sent}")
            if queue:
                await fixture_stream_manager.unsubscribe(session_id, queue)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get(
    "/fixtures",
    summary="Get Fixtures from Database",
    description="""
    Get fixture data stored in PostgreSQL database for a session.
    
    This endpoint retrieves fixtures that were saved when `fetch_upcoming_games` was called.
    Fixtures are stored in their raw format as received from the OpticOdds API.
    
    **Usage:**
    ```javascript
    const response = await fetch('/api/v1/fixtures/fixtures?session_id=user123');
    const data = await response.json();
    console.log('Fixtures:', data.fixtures);
    ```
    """,
    tags=["fixtures"]
)
async def get_fixtures(
    session_id: Optional[str] = Query(
        None,
        description="Session identifier (user_id or thread_id). Defaults to 'default' if not provided.",
        example="user_123"
    ),
    limit: Optional[int] = Query(
        None,
        description="Maximum number of fixtures to return. Returns all if not specified.",
        ge=1,
        le=1000,
        example=100
    )
):
    """
    Get fixtures from database for a session.
    
    Returns fixtures stored in PostgreSQL database in their raw format.
    """
    try:
        session_id = session_id or "default"
        logger.info(f"[get_fixtures] Retrieving fixtures for session_id={session_id}, limit={limit}")
        
        fixtures = get_fixtures_from_db(session_id, limit=limit)
        
        return {
            "status": "success",
            "session_id": session_id,
            "count": len(fixtures),
            "fixtures": fixtures
        }
    except Exception as e:
        logger.error(f"[get_fixtures] Error retrieving fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving fixtures: {str(e)}")


@router.get(
    "/fixtures/latest",
    summary="Get Latest Fixtures (Non-Streaming)",
    description="""
    Get the latest fixture data for a session without establishing a streaming connection.
    
    This is a REST endpoint that returns the most recent fixture data that was pushed
    to the stream for the given session. Useful for one-time fetches or fallback when
    SSE is not available.
    """,
    tags=["fixtures"]
)
async def get_latest_fixtures(
    session_id: Optional[str] = Query(
        None, 
        description="Session identifier. Defaults to 'default' if not provided.",
        example="user_123"
    )
):
    """
    Get latest fixture data for a session (non-streaming API).
    """
    session_id = session_id or "default"
    
    try:
        fixtures = await fixture_stream_manager.get_latest_fixtures(session_id)
        return {
            "status": "success",
            "fixtures": fixtures or [],
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting fixtures: {str(e)}")


@router.get(
    "/odds/stream",
    summary="Stream Odds Data (SSE)",
    description="""
    **Server-Sent Events (SSE) endpoint for streaming odds data to frontend.**
    
    This endpoint streams betting odds data that is automatically emitted by the `fetch_live_odds` tool.
    The frontend connects to this endpoint and receives odds JSON objects as they're pushed.
    
    **How it works:**
    1. Frontend connects to this endpoint with an optional `session_id`
    2. When `fetch_live_odds` tool is called, it automatically pushes odds data to this stream
    3. Frontend receives SSE events with complete odds JSON objects
    
    **Event Types:**
    - `connected`: Initial connection confirmation
    - `odds`: Odds data payload (contains full odds response from OpticOdds API)
    - `ping`: Keep-alive heartbeat (every 30 seconds)
    - `error`: Error message
    
    **Example SSE Event:**
    ```
    data: {"type":"connected","session_id":"user123"}
    
    data: {"type":"odds","data":{"data":[{"id":"20251127C95F3929","odds":[...]}]}}
    ```
    
    **Odds Response Structure:**
    The odds data follows the OpticOdds API response format:
    ```json
    {
      "data": [
        {
          "id": "fixture_id",
          "home_competitors": [...],
          "away_competitors": [...],
          "odds": [
            {
              "sportsbook": "FanDuel",
              "market": "Moneyline",
              "name": "Dallas Cowboys",
              "price": 1800,
              "deep_link": {...}
            }
          ]
        }
      ]
    }
    ```
    
    **Usage:**
    ```javascript
    const eventSource = new EventSource('/api/v1/fixtures/odds/stream?session_id=user123');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'odds') {
            console.log('Received odds:', data.data);
        }
    };
    ```
    """,
    response_description="Server-Sent Events stream with odds data",
    tags=["odds", "streaming"]
)
async def stream_odds(
    session_id: Optional[str] = Query(
        None, 
        description="Session identifier (user_id or thread_id). Defaults to 'default' if not provided.",
        example="user_123"
    )
):
    """
    Stream odds data via Server-Sent Events (SSE).
    
    Returns a continuous stream of odds data as it becomes available.
    Automatically receives data when `fetch_live_odds` tool is called.
    """
    session_id = session_id or "default"
    
    async def generate() -> AsyncIterator[str]:
        """Generator function for SSE streaming."""
        queue = None
        try:
            # Subscribe to odds updates
            queue = await odds_stream_manager.subscribe(session_id)
            
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            
            # Keep connection alive and stream odds data
            while True:
                try:
                    # Wait for odds data with timeout
                    odds_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Stream the full JSON data as one SSE event
                    yield f"data: {json.dumps(odds_data)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                except Exception as e:
                    # Send error and break
                    error_data = {
                        "type": "error",
                        "message": str(e)
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break
                    
        except Exception as e:
            error_data = {
                "type": "error",
                "message": f"Stream error: {str(e)}"
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Cleanup: unsubscribe from updates
            if queue:
                await odds_stream_manager.unsubscribe(session_id, queue)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get(
    "/odds/latest",
    summary="Get Latest Odds (Non-Streaming)",
    description="""
    Get the latest odds data for a session without establishing a streaming connection.
    
    This is a REST endpoint that returns the most recent odds data that was pushed
    to the stream for the given session. Useful for one-time fetches or fallback when
    SSE is not available.
    """,
    tags=["odds"]
)
async def get_latest_odds(
    session_id: Optional[str] = Query(
        None, 
        description="Session identifier. Defaults to 'default' if not provided.",
        example="user_123"
    )
):
    """
    Get latest odds data for a session (non-streaming API).
    """
    session_id = session_id or "default"
    
    try:
        odds = await odds_stream_manager.get_latest_odds(session_id)
        return {
            "status": "success",
            "odds": odds,
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting odds: {str(e)}")

