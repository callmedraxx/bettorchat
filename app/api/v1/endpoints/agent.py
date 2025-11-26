"""
Agent API endpoints.
"""
import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator

from app.agents.agent import create_betting_agent
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from app.agents.langgraph_client import get_langgraph_client, get_agent_id

# Logger for agent endpoints
logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the sports betting agent (local).
    
    Args:
        request: ChatRequest containing messages and optional session_id
            - messages: List of chat messages
            - session_id: Optional session identifier for maintaining conversation context.
                         If not provided, a new UUID will be generated.
    """
    try:
        import uuid
        from app.agents.tools.betting_tools import _current_session_id
        
        agent = create_betting_agent()
        
        # Convert request messages to the format expected by the agent
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Use provided session_id or generate a new one
        thread_id = request.session_id if request.session_id else str(uuid.uuid4())
        
        # Set the session_id in context so tools can access it
        _current_session_id.set(thread_id)
        
        # Create a config with thread_id for the checkpointer
        config = {"configurable": {"thread_id": thread_id}}
        
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
    Streams agent responses and tool responses when tools have stream_output=True.
    
    Args:
        request: ChatRequest containing messages and optional session_id
            - messages: List of chat messages
            - session_id: Optional session identifier for maintaining conversation context.
                         If not provided, a new UUID will be generated.
    """
    async def generate() -> AsyncIterator[str]:
        try:
            import uuid
            from app.agents.tools.betting_tools import _current_session_id
            
            agent = create_betting_agent()
            
            # Convert request messages to the format expected by the agent
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            # Use provided session_id or generate a new one
            thread_id = request.session_id if request.session_id else str(uuid.uuid4())
            
            # Set the session_id in context so tools can access it
            _current_session_id.set(thread_id)
            
            # Create a config with thread_id for the checkpointer
            config = {"configurable": {"thread_id": thread_id}}
            
            # Tools that support streaming (have stream_output parameter that defaults to True)
            # These tools store their results in the database for quick access
            STREAMING_TOOLS = {
                "fetch_live_odds",
                "fetch_upcoming_games",
            }
            
            # Track seen tool messages to avoid duplicates (using tool_call_id as key)
            seen_tool_call_ids = set()
            # Track tool calls: map tool_call_id -> tool_name
            tool_call_map = {}
            # Track previous message count to detect new messages
            previous_message_count = 0
            last_message_content = ""
            
            # Use stream_mode="values" for incremental AIMessage updates
            # and track all messages to detect ToolMessages
            async for chunk in agent.astream({"messages": messages}, config=config, stream_mode="values"):
                # Extract messages from state
                state = chunk.get("messages", [])
                if state:
                    current_message_count = len(state)
                    
                    # Check for new messages (ToolMessages or AIMessages with tool_calls)
                    if current_message_count > previous_message_count:
                        # Process new messages
                        new_messages = state[previous_message_count:]
                        
                        for message in new_messages:
                            # Track tool calls from AIMessage to get tool names
                            if isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls:
                                for tool_call in message.tool_calls:
                                    tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                                    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                                    if tool_call_id and tool_name:
                                        tool_call_map[tool_call_id] = tool_name
                            
                            # Stream ToolMessage responses for streaming tools
                            elif isinstance(message, ToolMessage):
                                # Get tool name from tool_call_id
                                tool_call_id = getattr(message, "tool_call_id", None)
                                
                                # Check if we've already streamed this tool message
                                if tool_call_id and tool_call_id not in seen_tool_call_ids:
                                    seen_tool_call_ids.add(tool_call_id)
                                    
                                    tool_name = tool_call_map.get(tool_call_id)
                                    
                                    # If we can't get tool name from map, try to get it from message attributes
                                    if not tool_name:
                                        tool_name = getattr(message, "name", None)
                                    
                                    # Stream full tool response if it's a streaming tool
                                    if tool_name in STREAMING_TOOLS:
                                        tool_content = message.content
                                        
                                        # Check if result was truncated by LangGraph
                                        from app.core.tool_result_storage import (
                                            is_truncated_message,
                                            extract_tool_call_id_from_truncated,
                                            get_tool_result
                                        )
                                        
                                        if tool_content and is_truncated_message(tool_content):
                                            full_result = None
                                            
                                            # First, try to get from database using tool_call_id
                                            from app.core.tool_result_db import get_tool_result_from_db, save_tool_result_to_db
                                            full_result = get_tool_result_from_db(tool_call_id)
                                            if full_result:
                                                logger.info(f"[chat_stream] Retrieved full result from database for tool_call_id={tool_call_id}, size={len(full_result)}")
                                            
                                            # If not in database, try to read from LangGraph's filesystem path
                                            if not full_result:
                                                truncated_id = extract_tool_call_id_from_truncated(tool_content)
                                                if truncated_id and truncated_id == tool_call_id:
                                                    try:
                                                        filesystem_path = f"/large_tool_results/{truncated_id}"
                                                        import os
                                                        if os.path.exists(filesystem_path):
                                                            with open(filesystem_path, 'r', encoding='utf-8') as f:
                                                                full_result = f.read()
                                                            logger.info(f"[chat_stream] Read full result from LangGraph filesystem: {filesystem_path}, size={len(full_result)}")
                                                            
                                                            # Store in database for future use
                                                            save_tool_result_to_db(
                                                                tool_call_id=tool_call_id,
                                                                session_id=thread_id,
                                                                tool_name=tool_name or "unknown",
                                                                full_result=full_result
                                                            )
                                                            logger.info(f"[chat_stream] Stored full result in database for tool_call_id={tool_call_id}")
                                                    except Exception as fs_error:
                                                        logger.warning(f"[chat_stream] Could not read from filesystem {filesystem_path}: {fs_error}")
                                            
                                            # Fallback: Try to get most recent result for this tool_name and session from database
                                            if not full_result and tool_name:
                                                try:
                                                    from app.core.database import SessionLocal
                                                    from app.models.tool_result import ToolResult
                                                    db = SessionLocal()
                                                    try:
                                                        # Get most recent result for this tool_name and session
                                                        recent_result = db.query(ToolResult).filter(
                                                            ToolResult.tool_name == tool_name,
                                                            ToolResult.session_id == thread_id
                                                        ).order_by(ToolResult.created_at.desc()).first()
                                                        
                                                        if recent_result and recent_result.full_result:
                                                            # Update it with the correct tool_call_id
                                                            recent_result.tool_call_id = tool_call_id
                                                            db.commit()
                                                            full_result = recent_result.full_result
                                                            logger.info(f"[chat_stream] Retrieved and updated most recent result from database for tool_name={tool_name}, tool_call_id={tool_call_id}, size={len(full_result)}")
                                                    finally:
                                                        db.close()
                                                except Exception as db_error:
                                                    logger.warning(f"[chat_stream] Could not retrieve from database fallback: {db_error}")
                                            
                                            # Fallback: Try to get from in-memory storage
                                            if not full_result:
                                                full_result = get_tool_result(tool_call_id)
                                                if full_result:
                                                    logger.info(f"[chat_stream] Retrieved full result from in-memory storage for tool_call_id={tool_call_id}, size={len(full_result)}")
                                            
                                            if full_result:
                                                tool_content = full_result
                                                logger.info(f"[chat_stream] Using full result for tool_call_id={tool_call_id}, total size={len(full_result)}")
                                            else:
                                                logger.warning(f"[chat_stream] Could not retrieve full result for tool_call_id={tool_call_id}, using truncated version")
                                        
                                        if tool_content:
                                            # Stream the full tool response (now with full content if available)
                                            tool_response_data = {
                                                'type': 'tool_response',
                                                'tool_name': tool_name,
                                                'content': tool_content
                                            }
                                            yield f"data: {json.dumps(tool_response_data)}\n\n"
                    
                    # Stream AIMessage content (incremental updates)
                    # Get the last message (should be AIMessage)
                    last_message = state[-1]
                    if isinstance(last_message, AIMessage) and last_message.content:
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
                    
                    previous_message_count = current_message_count
            
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

