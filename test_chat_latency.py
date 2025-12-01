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
                timeout=60
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
                
                # Check all messages for tool calls and tool results
                print(f"  All messages breakdown:")
                url_found = False
                for idx, msg in enumerate(messages):
                    role = msg.get("role", "unknown")
                    if role == "assistant":
                        tool_calls = msg.get("tool_calls", [])
                        if tool_calls:
                            print(f"    Message {idx} (assistant): {len(tool_calls)} tool call(s)")
                            for tc in tool_calls:
                                tool_name = tc.get('name', 'unknown')
                                print(f"      - {tool_name}")
                                if tool_name == "build_opticodds_url":
                                    print(f"        ✅ build_opticodds_url called!")
                    elif role == "tool":
                        tool_name = msg.get('name', 'unknown')
                        tool_content = msg.get('content', '')
                        print(f"    Message {idx} (tool): {tool_name}")
                        if "/api/v1/opticodds/proxy" in str(tool_content):
                            print(f"      ✅ URL found in tool result!")
                            url_found = True
                            # Extract and show URL
                            import re
                            url_match = re.search(r'/api/v1/opticodds/proxy/[^\s\n?]+(?:\?[^\s\n]+)?', str(tool_content))
                            if url_match:
                                print(f"      URL: {url_match.group(0)[:100]}...")
                
                # Check if URL was generated
                content = last_ai_message.get("content", "") if last_ai_message else ""
                if not url_found:
                    if "/api/v1/opticodds/proxy" in str(content):
                        print(f"  ✅ URL found in response content")
                        url_found = True
                    else:
                        print(f"  ⚠️  No URL found in response (check tool messages above)")
                
                # Print full response for debugging (show all messages)
                print(f"\n  Full messages breakdown:")
                for idx, msg in enumerate(messages):
                    print(f"    [{idx}] {msg.get('type', 'unknown')} - role: {msg.get('role', 'N/A')}")
                    if msg.get('type') == 'tool':
                        print(f"        Tool: {msg.get('name', 'unknown')}")
                        content_preview = str(msg.get('content', ''))[:200]
                        print(f"        Content: {content_preview}...")
                
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
    test_chat_latency("show me the player props for jameson williams", num_tests=3)

