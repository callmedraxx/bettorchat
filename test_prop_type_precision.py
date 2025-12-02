#!/usr/bin/env python3
"""
Test script to verify prop type filtering precision.
Tests that requests like "Dak Prescott passing props" only return passing-related markets.
"""
import httpx
import json
import sys

def test_prop_type_precision():
    """Test that prop_type filtering works correctly."""
    url = 'http://localhost:8000/api/v1/agent/chat'
    
    test_cases = [
        {
            'name': 'Dak Prescott passing props',
            'request': 'show me Dak Prescott passing props for tonight\'s game',
            'expected_prop_type': 'passing'
        },
        {
            'name': 'Dak Prescott rushing props',
            'request': 'show me Dak Prescott rushing props',
            'expected_prop_type': 'rushing'
        }
    ]
    
    print("=" * 80)
    print("Testing Prop Type Filtering Precision")
    print("=" * 80)
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print(f"Request: \"{test_case['request']}\"")
        print("-" * 80)
        
        payload = {
            'messages': [
                {
                    'role': 'user',
                    'content': test_case['request']
                }
            ],
            'session_id': f'test-prop-type-{i}'
        }
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get('messages', [])
                    
                    # Find the AI response
                    ai_message = None
                    for msg in messages:
                        if msg.get('role') == 'assistant' or msg.get('type') == 'ai':
                            ai_message = msg
                            break
                    
                    if ai_message:
                        content = ai_message.get('content', '')
                        print(f"Response Content: {content}")
                        print()
                        
                        # Check for URL in additional_kwargs (where the endpoint stores extracted URLs)
                        additional_kwargs = ai_message.get('additional_kwargs', {})
                        extracted_url = additional_kwargs.get('extracted_url')
                        
                        if extracted_url:
                            print(f"✅ URL was built successfully")
                            print(f"URL: {extracted_url}")
                            print()
                            
                            # Check if prop_type is in the URL
                            expected = test_case['expected_prop_type']
                            if f'prop_type={expected}' in extracted_url or f'prop_type%3D{expected}' in extracted_url:
                                print(f"✅ prop_type={expected} parameter found in URL")
                                print("   This means the agent is correctly using prop_type filtering!")
                            elif expected in extracted_url.lower():
                                print(f"⚠️  '{expected}' found in URL but prop_type parameter format unclear")
                                print(f"   URL contains '{expected}' but may not be in prop_type parameter format")
                            else:
                                print(f"❌ prop_type={expected} parameter NOT found in URL")
                                print("   This means the agent may not be using prop_type filtering")
                                print(f"   Expected: prop_type={expected}")
                                print(f"   URL: {extracted_url[:200]}")
                        else:
                            print("⚠️  No URL found in response")
                            print("   Checking for tool calls...")
                            
                            # Check for tool calls that might contain the URL
                            tool_calls = ai_message.get('tool_calls', [])
                            if tool_calls:
                                print(f"Tool calls found: {len(tool_calls)}")
                                for tc in tool_calls:
                                    print(f"  Tool: {tc.get('name', 'unknown')}")
                                    if 'args' in tc:
                                        args = tc.get('args', {})
                                        if 'prop_type' in args:
                                            print(f"  ✅ prop_type found in tool call: {args.get('prop_type')}")
                                        print(f"  Args keys: {list(args.keys())}")
                            else:
                                print("   No tool calls found in response")
                                print(f"   Full message: {json.dumps(ai_message, indent=2)[:500]}")
                    else:
                        print("⚠️  No AI message found in response")
                        print(f"   Full response: {json.dumps(data, indent=2)[:500]}")
                else:
                    print(f"❌ Error: HTTP {response.status_code}")
                    print(response.text[:500])
                    
        except httpx.ConnectError:
            print("❌ Connection error - is the server running on localhost:8000?")
            print("   Try: uvicorn app.main:app --reload")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print()
        print("=" * 80)
        print()
    
    print("Test completed!")

if __name__ == '__main__':
    test_prop_type_precision()

