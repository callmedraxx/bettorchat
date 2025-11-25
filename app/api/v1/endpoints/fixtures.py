"""
Fixture streaming API endpoints.
Provides SSE endpoint for streaming fixture objects to frontend.
"""
import json
import asyncio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncIterator
from pydantic import BaseModel, Field

from app.core.fixture_stream import fixture_stream_manager
from app.core.odds_stream import odds_stream_manager

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
    **Server-Sent Events (SSE) endpoint for streaming fixture objects to frontend.**
    
    This endpoint streams fixture data that is automatically emitted by the `fetch_upcoming_games` tool.
    The frontend connects to this endpoint and receives fixture JSON objects as they're pushed.
    
    **How it works:**
    1. Frontend connects to this endpoint with an optional `session_id`
    2. When `fetch_upcoming_games` tool is called, it automatically pushes fixture data to this stream
    3. Frontend receives SSE events with complete fixture JSON objects
    
    **Event Types:**
    - `connected`: Initial connection confirmation
    - `fixtures`: Fixture data payload (contains full fixture objects)
    - `ping`: Keep-alive heartbeat (every 30 seconds)
    - `error`: Error message
    
    **Example SSE Event:**
    ```
    data: {"type":"connected","session_id":"user123"}
    
    data: {"type":"fixtures","data":[{"id":"20251127C95F3929","home_team":"Dallas Cowboys",...}]}
    ```
    
    **Usage:**
    ```javascript
    const eventSource = new EventSource('/api/v1/fixtures/fixtures/stream?session_id=user123');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'fixtures') {
            console.log('Received fixtures:', data.data);
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
    
    async def generate() -> AsyncIterator[str]:
        """Generator function for SSE streaming."""
        queue = None
        try:
            # Subscribe to fixture updates
            queue = await fixture_stream_manager.subscribe(session_id)
            
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            
            # Keep connection alive and stream fixture data
            while True:
                try:
                    # Wait for fixture data with timeout
                    fixture_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Stream the full JSON data as one SSE event
                    yield f"data: {json.dumps(fixture_data)}\n\n"
                    
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

