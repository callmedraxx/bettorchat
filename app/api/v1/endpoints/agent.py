"""
Agent API endpoints.
"""
import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, AsyncIterator, Tuple

from app.agents.agent import create_betting_agent
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from app.agents.langgraph_client import get_langgraph_client, get_agent_id

# Import Anthropic error types for better error handling
try:
    from anthropic import BadRequestError, APIError, APIConnectionError, RateLimitError
except ImportError:
    # Fallback if anthropic package structure is different
    BadRequestError = Exception
    APIError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception

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
    import uuid
    import traceback
    from app.agents.tools.betting_tools import _current_session_id
    
    # Log incoming request
    session_id = request.session_id or "new-session"
    message_count = len(request.messages)
    last_message = request.messages[-1].content[:100] if request.messages else "no messages"
    logger.info(f"[chat] REQUEST RECEIVED - session_id: {session_id}, messages: {message_count}, last_message: {last_message}...")
    
    try:
        agent = create_betting_agent()
        
        # Convert request messages to the format expected by the agent
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Use provided session_id or generate a new one
        thread_id = request.session_id if request.session_id else str(uuid.uuid4())
        
        logger.info(f"[chat] Processing chat request for thread_id: {thread_id}")
        
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
        
        logger.info(f"[chat] Successfully processed chat request for thread_id: {thread_id}, response_messages: {len(formatted_messages)}")
        return ChatResponse(messages=formatted_messages)
    except (BadRequestError, APIError) as e:
        # Handle Anthropic API errors gracefully
        error_traceback = traceback.format_exc()
        error_message = str(e)
        
        # Extract error message from various possible structures
        error_msg = error_message
        try:
            # Try to get error body if available
            if hasattr(e, 'body'):
                error_body = e.body
                if isinstance(error_body, dict):
                    error_detail = error_body.get('error', {})
                    if isinstance(error_detail, dict):
                        error_msg = error_detail.get('message', error_message)
            # Also check response attribute if available
            elif hasattr(e, 'response'):
                response = e.response
                if hasattr(response, 'json'):
                    try:
                        error_body = response.json()
                        if isinstance(error_body, dict):
                            error_detail = error_body.get('error', {})
                            if isinstance(error_detail, dict):
                                error_msg = error_detail.get('message', error_message)
                    except:
                        pass
        except Exception as extract_error:
            logger.debug(f"[chat] Could not extract detailed error message: {extract_error}")
        
        # Check for credit/billing errors
        error_msg_lower = error_msg.lower()
        if 'credit' in error_msg_lower or 'balance' in error_msg_lower or 'billing' in error_msg_lower or 'too low' in error_msg_lower:
            user_message = "I'm unable to process your request right now due to API service limitations. Please try again later or contact support if the issue persists."
            logger.warning(f"[chat] API credit/billing error for session_id: {session_id} - {error_msg}")
            logger.debug(f"[chat] Full traceback:\n{error_traceback}")
            raise HTTPException(status_code=503, detail=user_message)
        else:
            logger.error(f"[chat] API error for session_id: {session_id} - {error_msg}")
            logger.debug(f"[chat] Full traceback:\n{error_traceback}")
            raise HTTPException(status_code=400, detail="Error processing chat request. Please try again.")
    except (APIConnectionError, RateLimitError) as e:
        # Handle connection and rate limit errors
        error_traceback = traceback.format_exc()
        error_message = str(e)
        if isinstance(e, RateLimitError):
            user_message = "The service is currently experiencing high demand. Please try again in a moment."
            logger.warning(f"[chat] Rate limit error for session_id: {session_id}")
            logger.debug(f"[chat] Full traceback:\n{error_traceback}")
            raise HTTPException(status_code=429, detail=user_message)
        else:
            user_message = "I'm having trouble connecting to the service. Please check your internet connection and try again."
            logger.error(f"[chat] Connection error for session_id: {session_id} - {error_message}")
            logger.debug(f"[chat] Full traceback:\n{error_traceback}")
            raise HTTPException(status_code=503, detail=user_message)
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"[chat] ERROR processing chat request for session_id: {session_id}")
        logger.error(f"[chat] Error message: {str(e)}")
        logger.error(f"[chat] Full traceback:\n{error_traceback}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again.")


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


@router.options("/chat/stream")
async def chat_stream_options(request: Request):
    """Handle CORS preflight requests for /chat/stream endpoint."""
    from fastapi import Response
    from app.core.config import settings
    
    # Get origin from request
    origin = request.headers.get("origin")
    
    # Check if origin is allowed
    allowed_origins = settings.BACKEND_CORS_ORIGINS
    if isinstance(allowed_origins, str):
        allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]
    
    # Check if origin matches allowed origins or regex patterns
    is_allowed = False
    if origin:
        # Check exact match
        if origin in allowed_origins:
            is_allowed = True
        # Check regex patterns (lovable and bettorchat domains)
        import re
        lovable_pattern = r"https?://.*\.lovableproject\.com|https?://.*\.lovable\.dev|https?://.*\.lovable\.app"
        bettorchat_pattern = r"https?://.*\.bettorchat\.app"
        if re.match(lovable_pattern, origin) or re.match(bettorchat_pattern, origin):
            is_allowed = True
    
    # Use origin if allowed, otherwise use first allowed origin or "*"
    allow_origin = origin if is_allowed else (allowed_origins[0] if allowed_origins else "*")
    
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        }
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat with the sports betting agent (local) - Server-Sent Events.
    Streams only AI agent responses (tool responses are disabled).
    
    Args:
        request: ChatRequest containing messages and optional session_id
            - messages: List of chat messages
            - session_id: Optional session identifier for maintaining conversation context.
                         If not provided, a new UUID will be generated.
    """
    import traceback
    
    # Log incoming request
    session_id = request.session_id or "new-session"
    message_count = len(request.messages)
    last_message = request.messages[-1].content[:100] if request.messages else "no messages"
    logger.info(f"[chat/stream] REQUEST RECEIVED - session_id: {session_id}, messages: {message_count}, last_message: {last_message}...")
    
    async def generate() -> AsyncIterator[str]:
        try:
            logger.info(f"[chat/stream] Starting stream generation for session_id: {session_id}")
            import uuid
            from datetime import datetime
            from app.agents.tools.betting_tools import _current_session_id
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from app.core.config import settings
            
            # Use AsyncPostgresSaver for async streaming operations
            # This is the proper async version that supports aget_tuple
            async_checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
            async_checkpointer = await async_checkpointer_cm.__aenter__()
            
            # Setup tables if needed (only first time)
            try:
                await async_checkpointer.setup()
                logger.info("[chat/stream] AsyncPostgresSaver initialized and tables created/verified")
            except Exception as setup_error:
                logger.warning(f"[chat/stream] AsyncPostgresSaver setup failed (tables may already exist): {setup_error}")
            
            logger.info(f"[chat/stream] Using AsyncPostgresSaver for persistent state")
            agent = create_betting_agent(checkpointer=async_checkpointer)
            
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
            # Track URLs sent to avoid duplicates (using URL as key)
            sent_urls = set()
            # Track tool_call_ids we've already processed for URL generation
            processed_tool_call_ids = set()
            # Track previous message count to detect new messages
            previous_message_count = 0
            last_message_content = ""
            
            # Buffer for incomplete internal thoughts (<-- ... -->)
            thought_buffer = ""
            in_thought = False
            def _is_final_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> bool:
                """Determine if a tool call is final (directly answers user) or intermediate (gathers data).
                
                Final tools are those that directly provide the data the user requested.
                Intermediate tools are used to gather information needed to construct the final request.
                
                Args:
                    tool_name: Name of the tool being called
                    tool_args: Arguments passed to the tool
                
                Returns:
                    True if this is a final tool call, False if intermediate
                """
                # Tools that are typically final (directly answer user requests)
                final_tools = {
                    "fetch_live_odds",  # Direct odds query - final answer
                    "fetch_player_props",  # Direct player props query - final answer
                    "fetch_live_game_stats",  # Direct stats query - final answer
                    "fetch_upcoming_games",  # Direct schedule query - final answer (unless stream_output=False)
                    "fetch_injury_reports",  # Direct injury query - final answer
                    "fetch_futures",  # Direct futures query - final answer
                    "fetch_historical_odds",  # Direct historical query - final answer
                }
                
                # Tools that are typically intermediate (gather data for other tools)
                intermediate_tools = {
                    "build_opticodds_url",  # Helper tool to build URLs - not a data-fetching tool
                    "fetch_available_sportsbooks",  # Used to find which sportsbooks to use
                    "fetch_available_sports",  # Used to find available sports
                    "fetch_available_leagues",  # Used to find available leagues
                    "fetch_available_markets",  # Used to find available markets
                    "fetch_players",  # Used to find player_id for other queries
                    "fetch_teams",  # Used to find team_id for other queries
                    "get_current_datetime",  # Used to get current date for queries
                    "query_tool_results",  # Used to find previously fetched data
                    "query_odds_entries",  # Used to query stored odds
                }
                
                # Check if tool is explicitly marked as intermediate (stream_output=False)
                if "stream_output" in tool_args and tool_args.get("stream_output") is False:
                    return False  # Explicitly marked as intermediate
                
                # Check explicit final/intermediate lists
                if tool_name in final_tools:
                    # For fetch_upcoming_games, check if it's being used as intermediate
                    if tool_name == "fetch_upcoming_games":
                        # If stream_output is False, it's intermediate (used to get fixture_ids)
                        if tool_args.get("stream_output") is False:
                            return False
                    return True  # Final tool
                
                if tool_name in intermediate_tools:
                    return False  # Intermediate tool
                
                # Default: if tool has stream_output=True or not specified, assume it's final
                # This handles edge cases where we're not sure
                return tool_args.get("stream_output", True) is not False
            
            # Use stream_mode="values" for incremental AIMessage updates
            # and track all messages to detect ToolMessages
            async for chunk in agent.astream({"messages": messages}, config=config, stream_mode="values"):
                # Extract messages from state
                state = chunk.get("messages", [])
                if state:
                    current_message_count = len(state)
                    
                    # Check for new messages (ToolMessages or AIMessages with tool_calls)
                    # Also check all AIMessages in state for tool_calls we might have missed
                    if current_message_count > previous_message_count:
                        # Process new messages
                        new_messages = state[previous_message_count:]
                    else:
                        # No new messages, but check existing AIMessages for tool_calls we might have missed
                        new_messages = []
                    
                    # Check all AIMessages in current state for tool_calls (including existing ones that might have been updated)
                    for message in state:
                        if isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls:
                                logger.debug(f"[chat_stream] Found AIMessage with {len(message.tool_calls)} tool call(s)")
                                for tool_call in message.tool_calls:
                                    tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                                    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                                    tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                                    
                                    logger.debug(f"[chat_stream] Processing tool call: {tool_name}, id: {tool_call_id}, args keys: {list(tool_args.keys()) if tool_args else 'none'}")
                                    
                                    if tool_call_id and tool_name:
                                        # Always track tool calls in map (needed for ToolMessage processing)
                                        tool_call_map[tool_call_id] = tool_name
                                        logger.debug(f"[chat_stream] Mapped tool_call_id {tool_call_id} -> {tool_name}")
                                        
                                        # Skip if we've already processed this tool_call_id for URL generation
                                        if tool_call_id in processed_tool_call_ids:
                                            logger.debug(f"[chat_stream] Already processed tool_call_id {tool_call_id} for URL generation, skipping")
                                            continue
                                        
                                        # Skip build_opticodds_url - we'll extract URL from its ToolMessage result instead
                                        if tool_name == "build_opticodds_url":
                                            logger.info(f"[chat_stream] ✅ AI called build_opticodds_url tool - will extract URL from ToolMessage result")
                                            continue
                                        
                                        # Warn if AI calls data-fetching tools without calling build_opticodds_url first
                                        data_fetching_tools = {"fetch_live_odds", "fetch_upcoming_games", "fetch_player_props", "fetch_live_game_stats", "fetch_injury_reports", "fetch_futures", "fetch_historical_odds"}
                                        if tool_name in data_fetching_tools:
                                            # Check if build_opticodds_url was called recently for this tool
                                            build_url_called = False
                                            for prev_msg in state:
                                                if isinstance(prev_msg, (AIMessage, ToolMessage)):
                                                    if isinstance(prev_msg, AIMessage) and hasattr(prev_msg, "tool_calls"):
                                                        for tc in prev_msg.tool_calls:
                                                            tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                                                            if tc_name == "build_opticodds_url":
                                                                tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                                                if tc_args.get("tool_name") == tool_name:
                                                                    build_url_called = True
                                                                    break
                                                    elif isinstance(prev_msg, ToolMessage):
                                                        prev_tool_name = tool_call_map.get(prev_msg.name if hasattr(prev_msg, "name") else None)
                                                        if prev_tool_name == "build_opticodds_url":
                                                            build_url_called = True
                                                            break
                                                    if build_url_called:
                                                        break
                                            
                                            if not build_url_called:
                                                logger.warning(f"[chat_stream] ⚠️ AI called {tool_name} WITHOUT calling build_opticodds_url first! This violates the mandatory workflow.")
                                        
                                        # Only send URLs for "final" tools that directly answer user's request
                                        # Skip intermediate tools used to gather data
                                        is_final_tool = _is_final_tool_call(tool_name, tool_args)
                                        logger.debug(f"[chat_stream] Tool {tool_name} is_final_tool: {is_final_tool}")
                                        
                                        if is_final_tool:
                                            # Mark as processed before building URL to avoid duplicates
                                            processed_tool_call_ids.add(tool_call_id)
                                            
                                            # Build and send OpticOdds URL early if this is an OpticOdds tool
                                            try:
                                                from app.core.url_builder import build_opticodds_url_from_tool_call
                                                logger.debug(f"[chat_stream] Building URL for tool {tool_name} with args: {list(tool_args.keys())}")
                                                url = build_opticodds_url_from_tool_call(tool_name, tool_args)
                                                logger.debug(f"[chat_stream] URL builder returned: {url[:100] if url else 'None'}...")
                                                if url:
                                                    # Prevent duplicate URLs (same URL sent multiple times)
                                                    if url not in sent_urls:
                                                        sent_urls.add(url)
                                                        
                                                        # Create tool-specific type identifier (e.g., 'fetch_live_odds_url')
                                                        url_type = f"{tool_name}_url"
                                                        
                                                        # Include metadata for frontend
                                                        url_data = {
                                                            'type': url_type,
                                                            'url': url,
                                                            'tool_name': tool_name,
                                                            'session_id': thread_id,
                                                            'timestamp': datetime.now().isoformat()
                                                        }
                                                        
                                                        # Send URL as separate JSON event with tool-specific type
                                                        yield f"data: {json.dumps(url_data)}\n\n"
                                                        logger.info(f"[chat_stream] Sent final OpticOdds URL ({url_type}): {url[:100]}...")
                                                    else:
                                                        logger.debug(f"[chat_stream] Skipping duplicate URL for tool {tool_name}")
                                                else:
                                                    # Provide more detailed error about missing parameters
                                                    missing_details = []
                                                    if tool_name == "fetch_live_odds":
                                                        if "sportsbook" not in tool_args or not tool_args.get("sportsbook"):
                                                            missing_details.append("sportsbook (required)")
                                                        if not any(key in tool_args and tool_args.get(key) for key in ["fixture_id", "team_id", "player_id"]):
                                                            missing_details.append("at least one of: fixture_id, team_id, or player_id (required)")
                                                    elif tool_name == "fetch_player_props":
                                                        if "sportsbook" not in tool_args or not tool_args.get("sportsbook"):
                                                            missing_details.append("sportsbook (required)")
                                                        if not any(key in tool_args and tool_args.get(key) for key in ["fixture_id", "player_id"]):
                                                            missing_details.append("at least one of: fixture_id or player_id (required)")
                                                    
                                                    if missing_details:
                                                        logger.warning(f"[chat_stream] Could not build valid URL for tool {tool_name} - missing: {', '.join(missing_details)}. Args provided: {list(tool_args.keys())}")
                                                    else:
                                                        logger.warning(f"[chat_stream] Could not build valid URL for tool {tool_name} - missing required parameters. Args: {list(tool_args.keys())}")
                                            except Exception as url_error:
                                                logger.error(f"[chat_stream] Error building URL for tool {tool_name}: {url_error}", exc_info=True)
                                        else:
                                            logger.debug(f"[chat_stream] Skipping intermediate tool URL: {tool_name}")
                                    else:
                                        logger.debug(f"[chat_stream] Skipping tool call - missing id or name. id: {tool_call_id}, name: {tool_name}")
                        
                        # Also check ToolMessages - extract URLs from build_opticodds_url tool results
                        elif isinstance(message, ToolMessage):
                            # ToolMessage.name might be tool_call_id OR tool name - need to find the actual tool_call_id
                            # by searching for AIMessages with matching tool calls
                            tool_name_from_message = message.name if hasattr(message, "name") else None
                            
                            # Find the AIMessage that called this tool to get the actual tool_call_id
                            actual_tool_call_id = None
                            tool_name = None
                            for prev_message in state:
                                if isinstance(prev_message, AIMessage) and hasattr(prev_message, "tool_calls"):
                                    for tc in prev_message.tool_calls:
                                        tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                                        tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                                        
                                        # Check if this tool_call matches the ToolMessage
                                        # ToolMessage.name could be either tool_call_id or tool name
                                        if tc_id == tool_name_from_message or tc_name == tool_name_from_message:
                                            actual_tool_call_id = tc_id
                                            tool_name = tc_name
                                            tool_call_map[tc_id] = tc_name  # Ensure it's in the map
                                            break
                                    if actual_tool_call_id:
                                        break
                            
                            # Fallback: if we couldn't find it, use the message name as tool name
                            if not tool_name:
                                tool_name = tool_name_from_message
                            
                            logger.debug(f"[chat_stream] Processing ToolMessage: message.name={tool_name_from_message}, found tool_name={tool_name}, tool_call_id={actual_tool_call_id}")
                            
                            # Special handling for build_opticodds_url tool - extract URL from tool result
                            # ToolMessage means the tool has completed (got 200 response or error)
                            if tool_name == "build_opticodds_url":
                                logger.info(f"[chat_stream] 🔍 Found build_opticodds_url ToolMessage - extracting URL from result")
                                try:
                                    # Extract URL from tool result (format: "URL: /api/v1/opticodds/proxy/...")
                                    tool_content = message.content if hasattr(message, "content") else str(message)
                                    logger.debug(f"[chat_stream] build_opticodds_url tool result (first 500 chars): {str(tool_content)[:500]}")
                                    
                                    # Check if tool result contains an error
                                    if isinstance(tool_content, str):
                                        if "Error" in tool_content or "error" in tool_content.lower():
                                            logger.warning(f"[chat_stream] build_opticodds_url returned an error: {tool_content[:200]}")
                                            # Don't send URL if there was an error
                                            continue
                                    
                                    if isinstance(tool_content, str):
                                        # Look for "URL: " prefix
                                        url_match = None
                                        for line in tool_content.split('\n'):
                                            if line.strip().startswith("URL: "):
                                                url_match = line.strip()[5:].strip()  # Remove "URL: " prefix
                                                logger.debug(f"[chat_stream] Found URL via 'URL: ' prefix: {url_match[:100]}")
                                                break
                                        
                                        if not url_match:
                                            # Try to find URL pattern directly
                                            import re
                                            url_pattern = r'/api/v1/opticodds/proxy/[^\s\n?]+(?:\?[^\s\n]+)?'
                                            match = re.search(url_pattern, tool_content)
                                            if match:
                                                url_match = match.group(0)
                                                logger.debug(f"[chat_stream] Found URL via regex pattern: {url_match[:100]}")
                                        
                                        # Only send URL if it's valid and tool completed successfully
                                        if url_match and url_match not in sent_urls:
                                            logger.info(f"[chat_stream] ✅ Extracted URL from build_opticodds_url: {url_match[:100]}...")
                                            sent_urls.add(url_match)
                                            
                                            # Try to get the actual tool_name from the tool call args
                                            # Use the actual_tool_call_id we found earlier
                                            actual_tool_name = None
                                            if actual_tool_call_id:
                                                for prev_message in state:
                                                    if isinstance(prev_message, AIMessage) and hasattr(prev_message, "tool_calls"):
                                                        for tc in prev_message.tool_calls:
                                                            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                                                            if tc_id == actual_tool_call_id:
                                                                tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                                                                if tc_name == "build_opticodds_url":
                                                                    tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                                                    actual_tool_name = tc_args.get("tool_name")
                                                                    logger.debug(f"[chat_stream] Found actual_tool_name from tool call args: {actual_tool_name}")
                                                                    break
                                                    if actual_tool_name:
                                                        break
                                            
                                            # Use actual tool name for type identifier if available
                                            # Special case: fetch_players for player info should use player_info_url
                                            if actual_tool_name == "fetch_players":
                                                url_type = "player_info_url"
                                            elif actual_tool_name:
                                                url_type = f"{actual_tool_name}_url"
                                            else:
                                                url_type = "opticodds_url"
                                            
                                            url_data = {
                                                'type': url_type,
                                                'url': url_match,
                                                'tool_name': actual_tool_name or 'build_opticodds_url',
                                                'session_id': thread_id,
                                                'timestamp': datetime.now().isoformat()
                                            }
                                            
                                            # Tool has completed successfully (ToolMessage means completion)
                                            # Send URL to frontend
                                            yield f"data: {json.dumps(url_data)}\n\n"
                                            logger.info(f"[chat_stream] Sent OpticOdds URL from build_opticodds_url tool ({url_type}): {url_match[:100]}...")
                                        elif not url_match:
                                            logger.warning(f"[chat_stream] ⚠️ build_opticodds_url completed but no URL found in result. Content preview: {tool_content[:300]}")
                                        elif url_match in sent_urls:
                                            logger.debug(f"[chat_stream] Skipping duplicate URL: {url_match[:100]}")
                                except Exception as url_extract_error:
                                    logger.error(f"[chat_stream] ❌ Error extracting URL from build_opticodds_url result: {url_extract_error}", exc_info=True)
                            
                            # Also check if we haven't sent a URL yet for other tools, try to extract parameters from stored tool results
                            elif tool_name and actual_tool_call_id and actual_tool_call_id not in processed_tool_call_ids:
                                # Try to get tool result and extract parameters from structured_data
                                try:
                                    from app.core.tool_result_db import get_tool_result_from_db
                                    tool_result_str = get_tool_result_from_db(actual_tool_call_id)
                                    if tool_result_str:
                                        try:
                                            tool_result = json.loads(tool_result_str) if isinstance(tool_result_str, str) else tool_result_str
                                            # Extract common fields (fixture_id, team_id, etc.) from structured_data
                                            structured_data = tool_result.get("structured_data") if isinstance(tool_result, dict) else None
                                            if structured_data:
                                                # Build tool_args from extracted fields
                                                extracted_args = {}
                                                if isinstance(structured_data, dict):
                                                    if "id" in structured_data:
                                                        extracted_args["fixture_id"] = str(structured_data["id"])
                                                    if "fixture_id" in structured_data:
                                                        extracted_args["fixture_id"] = str(structured_data["fixture_id"])
                                                    if "team_id" in structured_data:
                                                        extracted_args["team_id"] = str(structured_data["team_id"])
                                                    if "player_id" in structured_data:
                                                        extracted_args["player_id"] = str(structured_data["player_id"])
                                                elif isinstance(structured_data, list) and structured_data:
                                                    # Extract from first item
                                                    first_item = structured_data[0]
                                                    if isinstance(first_item, dict):
                                                        if "id" in first_item:
                                                            extracted_args["fixture_id"] = str(first_item["id"])
                                                        if "fixture_id" in first_item:
                                                            extracted_args["fixture_id"] = str(first_item["fixture_id"])
                                                
                                                # For fetch_live_odds, we need sportsbook - use defaults
                                                if tool_name == "fetch_live_odds":
                                                    extracted_args["sportsbook"] = "draftkings,fanduel,betmgm"
                                                
                                                logger.debug(f"[chat_stream] Extracted args from tool result for {actual_tool_call_id}: {list(extracted_args.keys())}")
                                                is_final_tool = _is_final_tool_call(tool_name, extracted_args)
                                                if is_final_tool:
                                                    from app.core.url_builder import build_opticodds_url_from_tool_call
                                                    url = build_opticodds_url_from_tool_call(tool_name, extracted_args)
                                                    if url and url not in sent_urls:
                                                        processed_tool_call_ids.add(actual_tool_call_id)
                                                        sent_urls.add(url)
                                                        url_type = f"{tool_name}_url"
                                                        url_data = {
                                                            'type': url_type,
                                                            'url': url,
                                                            'tool_name': tool_name,
                                                            'session_id': thread_id,
                                                            'timestamp': datetime.now().isoformat()
                                                        }
                                                        yield f"data: {json.dumps(url_data)}\n\n"
                                                        logger.info(f"[chat_stream] Sent OpticOdds URL from ToolMessage ({url_type}): {url[:100]}...")
                                        except (json.JSONDecodeError, AttributeError) as parse_error:
                                            logger.debug(f"[chat_stream] Could not parse tool result for {actual_tool_call_id}: {parse_error}")
                                except Exception as tool_msg_error:
                                    logger.debug(f"[chat_stream] Could not extract URL from ToolMessage for {actual_tool_call_id}: {tool_msg_error}")
                            # Tool responses are not streamed to frontend - they use dedicated SSE streams
                    
                    # Stream AIMessage content (incremental updates)
                    # Get the last message (should be AIMessage)
                    last_message = state[-1]
                    if isinstance(last_message, AIMessage) and last_message.content:
                        current_content = last_message.content
                        if isinstance(current_content, str):
                            # Normal incremental streaming - no marker handling needed
                            if len(current_content) > len(last_message_content):
                                new_content = current_content[len(last_message_content):]
                                
                                # Handle internal thoughts buffering (<-- ... -->)
                                # Buffer incomplete thoughts and only stream when complete
                                content_to_stream = ""
                                
                                # Add new content to buffer
                                thought_buffer += new_content
                                
                                # Process buffer to find complete thoughts
                                while thought_buffer:
                                    if not in_thought:
                                        # Look for opening marker <--
                                        open_marker_pos = thought_buffer.find("<--")
                                        if open_marker_pos != -1:
                                            # Stream everything before the opening marker
                                            content_to_stream += thought_buffer[:open_marker_pos]
                                            # Start buffering from the opening marker
                                            thought_buffer = thought_buffer[open_marker_pos:]
                                            in_thought = True
                                        else:
                                            # No opening marker found, stream everything
                                            content_to_stream += thought_buffer
                                            thought_buffer = ""
                                    else:
                                        # We're inside a thought, look for closing marker -->
                                        close_marker_pos = thought_buffer.find("-->")
                                        if close_marker_pos != -1:
                                            # Found closing marker, include the complete thought
                                            complete_thought = thought_buffer[:close_marker_pos + 3]
                                            content_to_stream += complete_thought
                                            # Remove the complete thought from buffer
                                            thought_buffer = thought_buffer[close_marker_pos + 3:]
                                            in_thought = False
                                        else:
                                            # Closing marker not found yet, keep buffering
                                            break
                                
                                # Stream accumulated content if any
                                if content_to_stream:
                                    yield f"data: {json.dumps({'type': 'content', 'content': content_to_stream})}\n\n"
                                
                                last_message_content = current_content
                        elif isinstance(current_content, list):
                            # Handle list of content blocks
                            text_parts = [item.get("text", "") if isinstance(item, dict) else str(item) 
                                        for item in current_content if isinstance(item, (str, dict))]
                            current_text = "".join(text_parts)
                            if len(current_text) > len(last_message_content):
                                new_content = current_text[len(last_message_content):]
                                
                                # Handle internal thoughts buffering (<-- ... -->)
                                # Buffer incomplete thoughts and only stream when complete
                                content_to_stream = ""
                                
                                # Add new content to buffer
                                thought_buffer += new_content
                                
                                # Process buffer to find complete thoughts
                                while thought_buffer:
                                    if not in_thought:
                                        # Look for opening marker <--
                                        open_marker_pos = thought_buffer.find("<--")
                                        if open_marker_pos != -1:
                                            # Stream everything before the opening marker
                                            content_to_stream += thought_buffer[:open_marker_pos]
                                            # Start buffering from the opening marker
                                            thought_buffer = thought_buffer[open_marker_pos:]
                                            in_thought = True
                                        else:
                                            # No opening marker found, stream everything
                                            content_to_stream += thought_buffer
                                            thought_buffer = ""
                                    else:
                                        # We're inside a thought, look for closing marker -->
                                        close_marker_pos = thought_buffer.find("-->")
                                        if close_marker_pos != -1:
                                            # Found closing marker, include the complete thought
                                            complete_thought = thought_buffer[:close_marker_pos + 3]
                                            content_to_stream += complete_thought
                                            # Remove the complete thought from buffer
                                            thought_buffer = thought_buffer[close_marker_pos + 3:]
                                            in_thought = False
                                        else:
                                            # Closing marker not found yet, keep buffering
                                            break
                                
                                # Stream accumulated content if any
                                if content_to_stream:
                                    yield f"data: {json.dumps({'type': 'content', 'content': content_to_stream})}\n\n"
                                
                                last_message_content = current_text
                    
                    previous_message_count = current_message_count
            
            # Flush any remaining buffered content (in case stream ends with incomplete thought)
            if thought_buffer:
                # Stream any remaining buffer content (even if incomplete)
                yield f"data: {json.dumps({'type': 'content', 'content': thought_buffer})}\n\n"
                thought_buffer = ""
            
            # Send completion signal
            logger.info(f"[chat/stream] Stream completed successfully for session_id: {session_id}")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except (BadRequestError, APIError) as e:
            # Handle Anthropic API errors gracefully
            import traceback
            error_traceback = traceback.format_exc()
            error_message = str(e)
            
            # Extract error message from various possible structures
            error_msg = error_message
            try:
                # Try to get error body if available
                if hasattr(e, 'body'):
                    error_body = e.body
                    if isinstance(error_body, dict):
                        error_detail = error_body.get('error', {})
                        if isinstance(error_detail, dict):
                            error_msg = error_detail.get('message', error_message)
                # Also check response attribute if available
                elif hasattr(e, 'response'):
                    response = e.response
                    if hasattr(response, 'json'):
                        try:
                            error_body = response.json()
                            if isinstance(error_body, dict):
                                error_detail = error_body.get('error', {})
                                if isinstance(error_detail, dict):
                                    error_msg = error_detail.get('message', error_message)
                        except:
                            pass
            except Exception as extract_error:
                logger.debug(f"[chat/stream] Could not extract detailed error message: {extract_error}")
            
            # Check for credit/billing errors
            error_msg_lower = error_msg.lower()
            if 'credit' in error_msg_lower or 'balance' in error_msg_lower or 'billing' in error_msg_lower or 'too low' in error_msg_lower:
                user_message = "I'm unable to process your request right now due to API service limitations. Please try again later or contact support if the issue persists."
                logger.warning(f"[chat/stream] API credit/billing error for session_id: {session_id} - {error_msg}")
            else:
                user_message = "I encountered an error processing your request. Please try again."
                logger.error(f"[chat/stream] API error for session_id: {session_id} - {error_msg}")
            
            # Log full error for debugging but don't expose it to user
            logger.debug(f"[chat/stream] Full traceback:\n{error_traceback}")
            
            # Send user-friendly error message
            error_data = {
                "type": "error", 
                "message": user_message,
                "error_type": "api_error"
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        except (APIConnectionError, RateLimitError) as e:
            # Handle connection and rate limit errors
            import traceback
            error_traceback = traceback.format_exc()
            error_message = str(e)
            
            if isinstance(e, RateLimitError):
                user_message = "The service is currently experiencing high demand. Please try again in a moment."
                logger.warning(f"[chat/stream] Rate limit error for session_id: {session_id}")
            else:
                user_message = "I'm having trouble connecting to the service. Please check your internet connection and try again."
                logger.error(f"[chat/stream] Connection error for session_id: {session_id} - {error_message}")
            
            logger.debug(f"[chat/stream] Full traceback:\n{error_traceback}")
            
            error_data = {
                "type": "error",
                "message": user_message,
                "error_type": "connection_error" if isinstance(e, APIConnectionError) else "rate_limit_error"
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        except Exception as e:
            # Handle all other errors
            import traceback
            error_traceback = traceback.format_exc()
            error_message = str(e)
            
            # Check if this is a database connection error
            is_db_error = False
            db_error_message = None
            try:
                import psycopg
                if isinstance(e, psycopg.OperationalError) or "consuming input failed" in error_message or "server closed the connection" in error_message:
                    is_db_error = True
                    db_error_message = "Database connection was lost. Please try again."
            except ImportError:
                # psycopg not available, check error message
                if "consuming input failed" in error_message or "server closed the connection" in error_message or "OperationalError" in str(type(e)):
                    is_db_error = True
                    db_error_message = "Database connection was lost. Please try again."
            
            logger.error(f"[chat/stream] ERROR in stream generation for session_id: {session_id}")
            logger.error(f"[chat/stream] Error message: {error_message}")
            if is_db_error:
                logger.warning(f"[chat/stream] Database connection error detected - this may be transient")
            logger.error(f"[chat/stream] Full traceback:\n{error_traceback}")
            
            # Provide appropriate error message based on error type
            if is_db_error:
                user_message = db_error_message or "I'm having trouble connecting to the database. Please try again in a moment."
                error_type = "database_error"
            else:
                user_message = "I encountered an unexpected error processing your request. Please try again."
                error_type = "unexpected_error"
            
            error_data = {
                "type": "error", 
                "message": user_message,
                "error_type": error_type
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    try:
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"[chat/stream] ERROR creating StreamingResponse for session_id: {session_id}")
        logger.error(f"[chat/stream] Error message: {str(e)}")
        logger.error(f"[chat/stream] Full traceback:\n{error_traceback}")
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")
    
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

