"""
Fixture streaming API endpoints.
Provides SSE endpoint for streaming fixture objects to frontend.
"""
import json
import asyncio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncIterator
from pydantic import BaseModel

from app.core.fixture_stream import fixture_stream_manager
from app.core.odds_stream import odds_stream_manager

router = APIRouter()


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


@router.get("/fixtures/stream")
async def stream_fixtures(
    session_id: Optional[str] = Query(None, description="Session identifier (user_id or thread_id)")
):
    """
    SSE endpoint for streaming fixture objects to frontend.
    Frontend connects to this endpoint and receives fixture data as it's pushed.
    
    Args:
        session_id: Optional session identifier. If not provided, uses "default"
        
    Returns:
        StreamingResponse with Server-Sent Events
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


@router.get("/fixtures/latest")
async def get_latest_fixtures(
    session_id: Optional[str] = Query(None, description="Session identifier")
):
    """
    Get latest fixture data for a session (non-streaming API).
    
    Args:
        session_id: Optional session identifier. If not provided, uses "default"
        
    Returns:
        Latest fixture data or empty list
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


@router.get("/odds/stream")
async def stream_odds(
    session_id: Optional[str] = Query(None, description="Session identifier (user_id or thread_id)")
):
    """
    SSE endpoint for streaming odds data to frontend.
    Frontend connects to this endpoint and receives odds data as it's pushed.
    
    Args:
        session_id: Optional session identifier. If not provided, uses "default"
        
    Returns:
        StreamingResponse with Server-Sent Events
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


@router.get("/odds/latest")
async def get_latest_odds(
    session_id: Optional[str] = Query(None, description="Session identifier")
):
    """
    Get latest odds data for a session (non-streaming API).
    
    Args:
        session_id: Optional session identifier. If not provided, uses "default"
        
    Returns:
        Latest odds data or None
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

