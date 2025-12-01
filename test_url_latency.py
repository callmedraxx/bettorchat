#!/usr/bin/env python3
"""
Test script to measure URL appearance latency in streaming endpoint.
Measures time from request start to when build_opticodds_url streams the URL.
"""
import requests
import time
import json
from datetime import datetime

def test_url_latency():
    url = 'http://localhost:8000/api/v1/agent/chat/stream'
    payload = {
        'messages': [{'role': 'user', 'content': 'show me nfl games fixtures for tonight'}],
        'session_id': f'test-url-latency-{int(time.time())}'
    }
    
    print('=' * 70)
    print('URL Appearance Latency Test')
    print('=' * 70)
    print()
    print(f'Query: "show me nfl games fixtures for tonight"')
    print(f'Endpoint: {url}')
    print()
    print('Measuring time from request start to URL appearance...')
    print()
    
    start_time = time.time()
    url_received_time = None
    url_data = None
    
    try:
        response = requests.post(url, json=payload, stream=True, timeout=60)
        
        if response.status_code != 200:
            print(f'✗ Error: Status {response.status_code}')
            return
        
        # Parse Server-Sent Events
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # Parse SSE format: "data: {json}"
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)
                        
                        # Check if this is a URL event
                        if 'url' in data or (data.get('type', '').endswith('_url')):
                            if url_received_time is None:
                                url_received_time = time.time()
                                url_latency_ms = (url_received_time - start_time) * 1000
                                url_latency_sec = url_latency_ms / 1000
                                url_data = data
                                
                                print('=' * 70)
                                print('🎯 URL APPEARED!')
                                print('=' * 70)
                                print()
                                print(f'⏱️  Latency: {url_latency_ms:.2f} ms ({url_latency_sec:.2f} seconds)')
                                print()
                                print('URL Details:')
                                print(f'  Type: {data.get("type", "N/A")}')
                                print(f'  Tool: {data.get("tool_name", "N/A")}')
                                print(f'  URL: {data.get("url", "N/A")}')
                                print()
                                
                                # Check if it's the local NFL endpoint
                                url_str = data.get("url", "")
                                if "/api/v1/nfl/fixtures" in url_str:
                                    print('✅ Using local NFL endpoint')
                                elif "/api/v1/opticodds/proxy" in url_str:
                                    print('⚠️  Using OpticOdds proxy')
                                
                                print()
                                print('=' * 70)
                                return url_latency_ms
                    
                    except json.JSONDecodeError:
                        continue
        
        # If we get here, URL was not received
        elapsed = (time.time() - start_time) * 1000
        print(f'❌ URL NOT RECEIVED after {elapsed:.2f} ms')
        return None
        
    except requests.exceptions.Timeout:
        elapsed = (time.time() - start_time) * 1000
        print(f'✗ Request timed out after {elapsed:.2f} ms')
        return None
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        print(f'✗ Error: {str(e)}')
        print(f'Latency before error: {elapsed:.2f} ms')
        return None

if __name__ == '__main__':
    latency = test_url_latency()
    if latency:
        print(f'\n📊 Result: URL appeared in {latency:.2f} ms ({latency/1000:.2f} seconds)')
    else:
        print('\n❌ Failed to measure URL latency')

