#!/usr/bin/env python3
"""
Test script to measure streaming endpoint latency.
Measures time from request start to when build_opticodds_url streams the URL.
"""
import requests
import time
import json
from datetime import datetime

def test_stream_latency():
    url = 'http://localhost:8000/api/v1/agent/chat/stream'
    payload = {
        'messages': [{'role': 'user', 'content': 'show me nfl games fixtures for tonight'}],
        'session_id': f'test-stream-{int(time.time())}'
    }
    
    print('=' * 70)
    print('Streaming Endpoint Latency Test')
    print('=' * 70)
    print()
    print(f'Test Message: "show me nfl games fixtures for tonight"')
    print(f'Endpoint: {url}')
    print(f'Timestamp: {datetime.now().isoformat()}')
    print()
    print('-' * 70)
    print('Starting stream...')
    print('-' * 70)
    print()
    
    start_time = time.time()
    url_received_time = None
    first_chunk_time = None
    url_data = None
    chunks_received = 0
    
    try:
        response = requests.post(url, json=payload, stream=True, timeout=60)
        
        if response.status_code != 200:
            print(f'✗ Error: Status {response.status_code}')
            print(f'Response: {response.text[:500]}')
            return
        
        print('✓ Stream connection established')
        print()
        
        # Parse Server-Sent Events
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # Track first chunk received
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    first_chunk_latency = (first_chunk_time - start_time) * 1000
                    print(f'⏱️  First chunk received: {first_chunk_latency:.2f} ms')
                
                chunks_received += 1
                
                # Parse SSE format: "data: {json}"
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)
                        data_type = data.get('type', 'unknown')
                        
                        # Check if this is a URL event
                        if 'url' in data or data_type.endswith('_url'):
                            if url_received_time is None:
                                url_received_time = time.time()
                                url_latency = (url_received_time - start_time) * 1000
                                url_data = data
                                
                                print()
                                print('=' * 70)
                                print('🎯 URL RECEIVED!')
                                print('=' * 70)
                                print(f'Latency: {url_latency:.2f} ms ({url_latency/1000:.2f} seconds)')
                                print(f'Type: {data_type}')
                                print(f'URL: {data.get("url", "N/A")}')
                                print(f'Tool: {data.get("tool_name", "N/A")}')
                                print()
                                
                                # Continue to see if there are more events
                                continue
                        
                        # Log other event types
                        if url_received_time is None:
                            if data_type == 'error':
                                error_msg = data.get("message", "Unknown error")
                                error_details = data.get("error_details", "")
                                error_type = data.get("error_type", "")
                                print(f'❌ Error Event: {error_msg}')
                                if error_details:
                                    print(f'   Details: {error_details}')
                                if error_type:
                                    print(f'   Type: {error_type}')
                            else:
                                print(f'📦 Event: {data_type}')
                                if data:
                                    print(f'   Data: {json.dumps(data, indent=2)[:200]}')
                    
                    except json.JSONDecodeError:
                        # Not JSON, might be plain text
                        if url_received_time is None:
                            print(f'📝 Text chunk: {data_str[:100]}...')
        
        end_time = time.time()
        total_latency = (end_time - start_time) * 1000
        
        print()
        print('=' * 70)
        print('Test Summary')
        print('=' * 70)
        
        if url_received_time:
            url_latency = (url_received_time - start_time) * 1000
            print(f'✅ URL Received: {url_latency:.2f} ms ({url_latency/1000:.2f} seconds)')
        else:
            print('❌ URL NOT RECEIVED in stream')
        
        if first_chunk_time:
            first_chunk_latency = (first_chunk_time - start_time) * 1000
            print(f'⏱️  First Chunk: {first_chunk_latency:.2f} ms ({first_chunk_latency/1000:.2f} seconds)')
        
        print(f'📊 Total Stream Duration: {total_latency:.2f} ms ({total_latency/1000:.2f} seconds)')
        print(f'📦 Total Chunks Received: {chunks_received}')
        
        if url_data:
            print()
            print('URL Details:')
            print(f'  - Type: {url_data.get("type")}')
            print(f'  - Tool: {url_data.get("tool_name")}')
            print(f'  - URL: {url_data.get("url")}')
            
            # Check if it's the local NFL endpoint
            url_str = url_data.get("url", "")
            if "/api/v1/nfl/fixtures" in url_str:
                print()
                print('✅ Using local NFL endpoint!')
            elif "/api/v1/opticodds/proxy" in url_str:
                print()
                print('⚠️  Using OpticOdds proxy (not local endpoint)')
        
    except requests.exceptions.Timeout:
        elapsed = (time.time() - start_time) * 1000
        print(f'✗ Request timed out after {elapsed:.2f} ms')
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        print(f'✗ Error: {str(e)}')
        print(f'Latency before error: {elapsed:.2f} ms')
        import traceback
        traceback.print_exc()
    
    print()
    print('=' * 70)
    print('✓ Test completed!')
    print('=' * 70)

if __name__ == '__main__':
    test_stream_latency()

