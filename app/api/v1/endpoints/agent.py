"""
Agent API endpoints.
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator

from app.agents.agent import create_research_agent
from app.agents.langgraph_client import get_langgraph_client, get_agent_id

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the research agent (local).
    """
    try:
        agent = create_research_agent()
        
        # Convert request messages to the format expected by the agent
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        result = agent.invoke({"messages": messages})
        
        return ChatResponse(messages=result["messages"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")


@router.post("/chat/deployed", response_model=ChatResponse)
async def chat_deployed(request: ChatRequest):
    """
    Chat with the deployed LangGraph agent on LangSmith.
    """
    try:
        client = get_langgraph_client()
        agent_id = get_agent_id()
        
        if not agent_id:
            raise HTTPException(
                status_code=400, 
                detail="LANGGRAPH_AGENT_ID must be set in configuration"
            )
        
        # Convert request messages to the format expected by LangGraph
        # The input format depends on your agent's expected input schema
        input_data = {"messages": [{"role": msg.role, "content": msg.content} for msg in request.messages]}
        
        # Create a thread
        thread = await client.threads.create()
        thread_id = thread["thread_id"]
        
        # Create and run the agent
        run = await client.runs.create(
            assistant_id=agent_id,
            thread_id=thread_id,
            input=input_data
        )
        
        run_id = run["run_id"]
        
        # Poll for completion
        max_wait = 60  # Maximum wait time in seconds
        wait_time = 0
        poll_interval = 0.5  # Poll every 0.5 seconds
        
        while wait_time < max_wait:
            run_status = await client.runs.get(thread_id=thread_id, run_id=run_id)
            status = run_status.get("status")
            
            if status in ["success", "error", "cancelled"]:
                break
            
            await asyncio.sleep(poll_interval)
            wait_time += poll_interval
        
        # Get the final state from the thread
        thread_state = await client.threads.get_state(thread_id=thread_id)
        
        # Extract messages from the state
        # The structure depends on your agent's state schema
        state_values = thread_state.get("values", {})
        messages = state_values.get("messages", [])
        
        return ChatResponse(messages=messages)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat with the research agent (local) - Server-Sent Events.
    """
    async def generate() -> AsyncIterator[str]:
        try:
            agent = create_research_agent()
            
            # Convert request messages to the format expected by the agent
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            # Stream the agent execution
            async for chunk in agent.astream({"messages": messages}, stream_mode="updates"):
                # Format chunk as SSE
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/chat/deployed/stream")
async def chat_deployed_stream(request: ChatRequest):
    """
    Stream chat with the deployed LangGraph agent on LangSmith - Server-Sent Events.
    """
    async def generate() -> AsyncIterator[str]:
        try:
            client = get_langgraph_client()
            agent_id = get_agent_id()
            
            if not agent_id:
                error_data = {"type": "error", "message": "LANGGRAPH_AGENT_ID must be set in configuration"}
                yield f"data: {json.dumps(error_data)}\n\n"
                return
            
            # Convert request messages to the format expected by LangGraph
            input_data = {"messages": [{"role": msg.role, "content": msg.content} for msg in request.messages]}
            
            # Create a thread
            thread = await client.threads.create()
            thread_id = thread["thread_id"]
            
            # Create and stream the run
            run = await client.runs.create(
                assistant_id=agent_id,
                thread_id=thread_id,
                input=input_data,
                stream=True  # Enable streaming
            )
            
            run_id = run["run_id"]
            
            # Stream run events
            async for event in client.runs.stream(thread_id=thread_id, run_id=run_id):
                # Format event as SSE
                yield f"data: {json.dumps(event)}\n\n"
            
            # Get final state
            thread_state = await client.threads.get_state(thread_id=thread_id)
            final_data = {
                "type": "final",
                "state": thread_state.get("values", {})
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except ValueError as e:
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as e:
            error_data = {"type": "error", "message": f"Error processing chat request: {str(e)}"}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

