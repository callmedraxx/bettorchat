"""
Agent API endpoints.
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator

from app.agents.agent import create_betting_agent
from langchain_core.messages import AIMessage, BaseMessage
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
    Chat with the sports betting agent (local).
    """
    try:
        import uuid
        agent = create_betting_agent()
        
        # Convert request messages to the format expected by the agent
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Create a config with thread_id for the checkpointer
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        
        result = agent.invoke({"messages": messages}, config=config)
        
        # Use LangChain's built-in message serialization
        formatted_messages = [
            msg.model_dump() if hasattr(msg, "model_dump") else msg
            for msg in result["messages"]
        ]
        
        return ChatResponse(messages=formatted_messages)
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
    Stream chat with the sports betting agent (local) - Server-Sent Events.
    Streams only agent responses, not tool calls or intermediate states.
    """
    async def generate() -> AsyncIterator[str]:
        try:
            import uuid
            agent = create_betting_agent()
            
            # Convert request messages to the format expected by the agent
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            # Create a config with thread_id for the checkpointer
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            
            # Stream only final values (not tool calls/thoughts)
            last_message_content = ""
            async for chunk in agent.astream({"messages": messages}, config=config, stream_mode="values"):
                # Extract messages from state
                state = chunk.get("messages", [])
                if state:
                    # Get the last message (should be AIMessage)
                    last_message = state[-1]
                    
                    # Only stream AIMessage content, skip tool calls
                    if isinstance(last_message, AIMessage) and last_message.content:
                        # Stream content chunks (incremental updates)
                        current_content = last_message.content
                        if isinstance(current_content, str):
                            # If content has grown, stream the new part
                            if len(current_content) > len(last_message_content):
                                new_content = current_content[len(last_message_content):]
                                yield f"data: {json.dumps({'type': 'content', 'content': new_content})}\n\n"
                                last_message_content = current_content
                        elif isinstance(current_content, list):
                            # Handle list of content blocks
                            text_parts = [item.get("text", "") if isinstance(item, dict) else str(item) 
                                        for item in current_content if isinstance(item, (str, dict))]
                            current_text = "".join(text_parts)
                            if len(current_text) > len(last_message_content):
                                new_content = current_text[len(last_message_content):]
                                yield f"data: {json.dumps({'type': 'content', 'content': new_content})}\n\n"
                                last_message_content = current_text
            
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
            
            # Create the run (without stream parameter)
            run = await client.runs.create(
                assistant_id=agent_id,
                thread_id=thread_id,
                input=input_data
            )
            
            run_id = run["run_id"]
            
            # Poll and stream updates
            max_wait = 60  # Maximum wait time in seconds
            wait_time = 0
            poll_interval = 0.5  # Poll every 0.5 seconds
            last_state = None
            
            while wait_time < max_wait:
                # Get current run status
                run_status = await client.runs.get(thread_id=thread_id, run_id=run_id)
                status = run_status.get("status")
                
                # Get current thread state
                thread_state = await client.threads.get_state(thread_id=thread_id)
                current_state = thread_state.get("values", {})
                
                # Stream state updates if changed
                if current_state != last_state:
                    update_data = {
                        "type": "update",
                        "status": status,
                        "state": current_state
                    }
                    yield f"data: {json.dumps(update_data)}\n\n"
                    last_state = current_state
                
                # Check if run is complete
                if status in ["success", "error", "cancelled"]:
                    final_data = {
                        "type": "final",
                        "status": status,
                        "state": current_state
                    }
                    yield f"data: {json.dumps(final_data)}\n\n"
                    break
                
                await asyncio.sleep(poll_interval)
                wait_time += poll_interval
            
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

