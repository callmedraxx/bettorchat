"""
Example streaming endpoint to demonstrate AI streaming pattern.
This can be removed or modified when you add your actual services.
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter()


@router.get("/stream/example")
async def example_stream():
    """
    Example streaming endpoint demonstrating AI streaming pattern.
    Replace this with your actual AI service integration.
    """
    async def generate():
        """Generator function for streaming response."""
        messages = [
            "Hello",
            " from",
            " the",
            " chatbot",
            " API!",
            " This",
            " is",
            " a",
            " streaming",
            " example.",
        ]
        
        for message in messages:
            chunk = {
                "content": message,
                "type": "token"
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.1)  # Simulate processing delay
        
        # Send completion signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
        }
    )

