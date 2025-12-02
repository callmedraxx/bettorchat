#!/usr/bin/env python3
"""Test all prop types to verify precision filtering."""
import httpx
import json

test_cases = [
    {"request": "Dak Prescott passing props", "expected": "passing"},
    {"request": "show me CMC rushing props", "expected": "rushing"},
    {"request": "receiving props for Tyreek Hill", "expected": "receiving"},
]

url = 'http://localhost:8000/api/v1/agent/chat'

print("=" * 80)
print("Testing All Prop Types")
print("=" * 80)
print()

for i, test in enumerate(test_cases, 1):
    print(f"Test {i}: {test['request']}")
    print(f"Expected prop_type: {test['expected']}")
    print("-" * 80)
    
    payload = {
        'messages': [{'role': 'user', 'content': test['request']}],
        'session_id': f'test-prop-type-{i}'
    }
    
    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                
                ai_message = None
                for msg in messages:
                    if msg.get('role') == 'assistant' or msg.get('type') == 'ai':
                        ai_message = msg
                        break
                
                if ai_message:
                    additional_kwargs = ai_message.get('additional_kwargs', {})
                    extracted_url = additional_kwargs.get('extracted_url', '')
                    
                    if extracted_url:
                        expected_param = f"prop_type={test['expected']}"
                        if expected_param in extracted_url or f"prop_type%3D{test['expected']}" in extracted_url:
                            print(f"✅ SUCCESS: {expected_param} found in URL")
                            print(f"   URL: {extracted_url[:100]}...")
                        else:
                            print(f"❌ FAILED: {expected_param} NOT found in URL")
                            print(f"   URL: {extracted_url}")
                    else:
                        print("❌ No URL found in response")
                else:
                    print("❌ No AI message found")
            else:
                print(f"❌ HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()
    print("=" * 80)
    print()

print("Test completed!")

