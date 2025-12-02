#!/usr/bin/env python3
"""Simple test for prop type - single request with shorter timeout."""
import httpx
import json

url = 'http://localhost:8000/api/v1/agent/chat'
payload = {
    'messages': [
        {
            'role': 'user',
            'content': 'Dak Prescott passing props'
        }
    ],
    'session_id': 'test-simple-prop-type'
}

print("Testing: 'Dak Prescott passing props'")
print("=" * 80)

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
                content = ai_message.get('content', '')
                print(f"Response: {content}\n")
                
                # Check for URL in additional_kwargs
                additional_kwargs = ai_message.get('additional_kwargs', {})
                extracted_url = additional_kwargs.get('extracted_url')
                
                if extracted_url:
                    print(f"✅ URL: {extracted_url}\n")
                    
                    if 'prop_type=passing' in extracted_url or 'prop_type%3Dpassing' in extracted_url:
                        print("✅ SUCCESS: prop_type=passing found in URL!")
                    elif 'passing' in extracted_url.lower():
                        print("⚠️  'passing' found in URL but prop_type parameter format unclear")
                        print(f"   Full URL: {extracted_url}")
                    else:
                        print("❌ prop_type=passing NOT found in URL")
                        print(f"   Full URL: {extracted_url}")
                else:
                    print("⚠️  No URL found in additional_kwargs")
                    print(f"   Full message: {json.dumps(ai_message, indent=2)[:500]}")
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text[:500])
            
except httpx.ConnectError:
    print("❌ Connection error - is the server running?")
except httpx.ReadTimeout:
    print("❌ Request timed out - agent may be taking too long")
except Exception as e:
    print(f"❌ Error: {e}")

