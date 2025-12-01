#!/usr/bin/env python3
"""
Test latency of the /api/v1/agent/chat endpoint.
"""
import requests
import time
import json
from datetime import datetime

# API endpoint
BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/agent/chat"

def test_chat_latency(query: str, num_tests: int = 3):
    """Test the latency of the chat endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing Chat Endpoint Latency")
    print(f"{'='*60}")
    print(f"Query: {query}")
    print(f"Number of tests: {num_tests}")
    print(f"Endpoint: {CHAT_ENDPOINT}\n")
    
    latencies = []
    
    for i in range(num_tests):
        print(f"Test {i+1}/{num_tests}...")
        
        # Prepare request
        payload = {
            "messages": [
                {"role": "user", "content": query}
            ]
        }
        
        # Measure time
        start_time = time.time()
        try:
            response = requests.post(
                CHAT_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            
            if response.status_code == 200:
                result = response.json()
                messages = result.get("messages", [])
                
                # Find the last AI message
                ai_messages = [msg for msg in messages if msg.get("role") == "assistant"]
                last_ai_message = ai_messages[-1] if ai_messages else None
                
                # Check for tool calls
                tool_calls = []
                if last_ai_message and "tool_calls" in last_ai_message:
                    tool_calls = last_ai_message.get("tool_calls", [])
                
                # Extract tool names
                tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                
                print(f"  ✅ Success - Latency: {latency:.2f}ms")
                print(f"  Status: {response.status_code}")
                print(f"  Messages: {len(messages)}")
                print(f"  Tool calls: {len(tool_calls)}")
                if tool_names:
                    print(f"  Tools called: {', '.join(tool_names)}")
                
                # Check all messages for tool calls
                print(f"  All messages breakdown:")
                for idx, msg in enumerate(messages):
                    role = msg.get("role", "unknown")
                    if role == "assistant":
                        tool_calls = msg.get("tool_calls", [])
                        if tool_calls:
                            print(f"    Message {idx} (assistant): {len(tool_calls)} tool call(s)")
                            for tc in tool_calls:
                                print(f"      - {tc.get('name', 'unknown')}")
                    elif role == "tool":
                        print(f"    Message {idx} (tool): {msg.get('name', 'unknown')}")
                
                # Check if URL was generated
                content = last_ai_message.get("content", "") if last_ai_message else ""
                print(f"  Content preview: {str(content)[:500]}...")
                if "/api/v1/opticodds/proxy" in str(content):
                    print(f"  ✅ URL found in response")
                else:
                    print(f"  ⚠️  No URL found in response")
                
                # Print full response for debugging
                print(f"\n  Full response JSON (first 1000 chars):")
                print(f"  {json.dumps(result, indent=2)[:1000]}...")
                
                latencies.append(latency)
            else:
                print(f"  ❌ Error - Status: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print(f"  ❌ Timeout after 30 seconds")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
        
        print()
    
    # Calculate statistics
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        print(f"{'='*60}")
        print(f"Latency Statistics:")
        print(f"{'='*60}")
        print(f"Average: {avg_latency:.2f}ms")
        print(f"Min: {min_latency:.2f}ms")
        print(f"Max: {max_latency:.2f}ms")
        print(f"Tests: {len(latencies)}/{num_tests} successful")
        print(f"{'='*60}\n")
    else:
        print(f"{'='*60}")
        print(f"No successful tests completed")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    test_chat_latency("fetch upcoming nfl games", num_tests=3)

