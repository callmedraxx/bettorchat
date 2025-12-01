#!/usr/bin/env python3
"""
Test script to measure latency of Claude Haiku 4.5 model
for fetching upcoming NFL games.
"""
import time
import sys
import os
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.agent import create_betting_agent
from app.agents.tools.betting_tools import _current_session_id

def test_nfl_games_latency():
    """Test the agent with a request to fetch upcoming NFL games and measure latency."""
    
    print("=" * 80)
    print("Testing Claude Haiku 4.5 Latency - Fetch Upcoming NFL Games")
    print("=" * 80)
    print()
    
    # Set session ID
    session_id = "test-session-haiku"
    _current_session_id.set(session_id)
    
    # Create agent
    print("Creating agent with Claude Haiku 4.5...")
    agent_start = time.time()
    agent = create_betting_agent()
    agent_creation_time = (time.time() - agent_start) * 1000
    print(f"✓ Agent created in {agent_creation_time:.2f}ms")
    print()
    
    # Test message
    test_message = "show me upcoming NFL games"
    print(f"Test request: '{test_message}'")
    print()
    
    # Prepare messages
    messages = [{"role": "user", "content": test_message}]
    config = {"configurable": {"thread_id": session_id}}
    
    # Measure total latency
    print("Sending request to agent...")
    print("-" * 80)
    
    start_time = time.time()
    first_token_time = None
    
    try:
        # Invoke agent and measure time
        result = agent.invoke({"messages": messages}, config=config)
        
        end_time = time.time()
        total_latency = (end_time - start_time) * 1000
        
        # Extract response
        response_messages = result.get("messages", [])
        if response_messages:
            last_message = response_messages[-1]
            if hasattr(last_message, 'content'):
                response_content = last_message.content
            else:
                response_content = str(last_message)
        else:
            response_content = "No response"
        
        print("-" * 80)
        print()
        print("RESULTS:")
        print("=" * 80)
        print(f"Total Latency: {total_latency:.2f}ms ({total_latency/1000:.3f}s)")
        print(f"Agent Creation Time: {agent_creation_time:.2f}ms")
        print(f"Request Processing Time: {total_latency - agent_creation_time:.2f}ms")
        print()
        print("Response Preview:")
        print("-" * 80)
        # Show first 500 chars of response
        preview = str(response_content)[:500]
        print(preview)
        if len(str(response_content)) > 500:
            print("...")
        print("-" * 80)
        print()
        
        # Check for tool calls
        tool_calls = []
        for msg in response_messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
            elif isinstance(msg, dict) and 'tool_calls' in msg:
                tool_calls.extend(msg.get('tool_calls', []))
        
        if tool_calls:
            print(f"Tool Calls Made: {len(tool_calls)}")
            for i, tool_call in enumerate(tool_calls, 1):
                tool_name = tool_call.get('name', 'unknown') if isinstance(tool_call, dict) else getattr(tool_call, 'name', 'unknown')
                print(f"  {i}. {tool_name}")
        else:
            print("No tool calls detected in response")
        print()
        
        return {
            "total_latency_ms": total_latency,
            "agent_creation_ms": agent_creation_time,
            "request_processing_ms": total_latency - agent_creation_time,
            "success": True,
            "response_length": len(str(response_content)),
            "tool_calls_count": len(tool_calls)
        }
        
    except Exception as e:
        end_time = time.time()
        total_latency = (end_time - start_time) * 1000
        print("-" * 80)
        print()
        print("ERROR:")
        print("=" * 80)
        print(f"Error occurred after {total_latency:.2f}ms")
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return {
            "total_latency_ms": total_latency,
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    result = test_nfl_games_latency()
    
    print()
    print("=" * 80)
    if result.get("success"):
        print("✓ Test completed successfully!")
        print(f"  Total latency: {result['total_latency_ms']:.2f}ms")
        print(f"  Request processing: {result['request_processing_ms']:.2f}ms")
    else:
        print("✗ Test failed!")
        print(f"  Error: {result.get('error', 'Unknown error')}")
    print("=" * 80)

