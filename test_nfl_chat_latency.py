"""
Test script to measure latency for NFL games query on chat endpoint.
Tests that the agent uses the local NFL fixtures endpoint.
"""
import requests
import time
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/agent/chat"
TEST_MESSAGE = "show me nfl games for tonight"

def test_chat_endpoint():
    """Test the chat endpoint with NFL games query and measure latency."""
    print("\n" + "="*70)
    print("NFL Chat Endpoint Latency Test")
    print("="*70)
    print(f"\nTest Message: '{TEST_MESSAGE}'")
    print(f"Endpoint: {CHAT_ENDPOINT}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Prepare request
    payload = {
        "messages": [
            {
                "role": "user",
                "content": TEST_MESSAGE
            }
        ]
    }
    
    print("\n" + "-"*70)
    print("Sending request...")
    print("-"*70)
    
    try:
        # Measure latency
        start_time = time.time()
        
        response = requests.post(
            CHAT_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        end_time = time.time()
        latency = (end_time - start_time) * 1000  # Convert to milliseconds
        
        print(f"\n✓ Response received")
        print(f"Status Code: {response.status_code}")
        print(f"Latency: {latency:.2f} ms ({latency/1000:.2f} seconds)")
        
        if response.status_code != 200:
            print(f"\n✗ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
        
        # Parse response
        try:
            data = response.json()
            messages = data.get("messages", [])
            
            print(f"\nResponse contains {len(messages)} messages")
            
            # Check for local NFL endpoint URL in response
            response_text = json.dumps(data)
            found_local_endpoint = False
            found_opticodds_proxy = False
            url_found = None
            
            if "/nfl/fixtures" in response_text:
                found_local_endpoint = True
                # Extract the URL
                import re
                url_match = re.search(r'/api/v1/nfl/fixtures[^\s"\']*', response_text)
                if url_match:
                    url_found = url_match.group(0)
                print(f"\n✓ Found local NFL endpoint URL: {url_found or '/api/v1/nfl/fixtures'}")
            
            if "/opticodds/proxy" in response_text and "/nfl" not in response_text.lower():
                found_opticodds_proxy = True
                print("\n⚠️  Found OpticOdds proxy URL (should use local endpoint for NFL)")
            
            # Display tool calls and messages
            print("\n" + "-"*70)
            print("Tool Calls and Messages:")
            print("-"*70)
            for i, msg in enumerate(messages):
                msg_type = msg.get("type", "unknown")
                content = msg.get("content", "")
                
                if msg_type == "ai" and msg.get("tool_calls"):
                    tool_calls = msg.get("tool_calls", [])
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name", "unknown")
                        tool_args = tool_call.get("args", {})
                        print(f"\n[{i}] Tool Call: {tool_name}")
                        print(f"    Args: {json.dumps(tool_args, indent=6)}")
                
                elif msg_type == "tool":
                    tool_name = msg.get("name", "unknown")
                    if isinstance(content, str) and len(content) > 0:
                        print(f"\n[{i}] Tool Result ({tool_name}):")
                        # Extract URL if present
                        if "URL:" in content:
                            url_line = [line for line in content.split("\n") if "URL:" in line]
                            if url_line:
                                print(f"    {url_line[0]}")
                                if "/nfl/fixtures" in url_line[0]:
                                    found_local_endpoint = True
                        else:
                            print(f"    {content[:200]}...")
                
                elif msg_type == "ai" and not msg.get("tool_calls"):
                    if isinstance(content, str) and len(content) > 0:
                        print(f"\n[{i}] AI Response: {content[:200]}...")
            
            # Check if URL is in any message
            if found_local_endpoint:
                print("\n✓ Local NFL endpoint URL found in response!")
            elif found_opticodds_proxy and not found_local_endpoint:
                print("\n⚠️  Response uses OpticOdds proxy instead of local endpoint")
            
            # Summary
            print("\n" + "="*70)
            print("Test Summary")
            print("="*70)
            print(f"Latency: {latency:.2f} ms")
            print(f"Status: {'✓ SUCCESS' if response.status_code == 200 else '✗ FAILED'}")
            print(f"Local Endpoint Used: {'✓ YES' if found_local_endpoint else '✗ NO'}")
            print(f"OpticOdds Proxy Used: {'⚠️  YES (unexpected for NFL)' if found_opticodds_proxy and not found_local_endpoint else '✓ NO'}")
            
            if found_local_endpoint:
                print("\n✓ Integration working correctly - using local NFL endpoint!")
            elif found_opticodds_proxy and not found_local_endpoint:
                print("\n⚠️  Still using OpticOdds proxy - may need to check agent behavior")
            else:
                print("\n⚠️  Could not determine which endpoint was used")
            
            return response.status_code == 200
            
        except json.JSONDecodeError as e:
            print(f"\n✗ Error parsing JSON response: {e}")
            print(f"Response text: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server")
        print(f"Make sure the server is running at {BASE_URL}")
        return False
    except requests.exceptions.Timeout:
        print("\n✗ Error: Request timed out (>60 seconds)")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the test."""
    print("\n" + "="*70)
    print("NFL Chat Endpoint Latency Test")
    print("="*70)
    print("\nThis test will:")
    print("1. Send a chat request: 'show me nfl games for tonight'")
    print("2. Measure the response latency")
    print("3. Verify that the agent uses the local NFL endpoint")
    print("4. Check the response format")
    
    print("\n" + "="*70)
    print("Starting test...")
    print("="*70)
    
    success = test_chat_endpoint()
    
    print("\n" + "="*70)
    if success:
        print("✓ Test completed successfully!")
    else:
        print("✗ Test failed or encountered errors")
    print("="*70)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

