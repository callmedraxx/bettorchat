#!/usr/bin/env python3
"""
Test script to measure latency of /chat endpoint with agent caching.
"""
import time
import sys
import os
import requests
import json
from datetime import datetime

def test_chat_endpoint_latency(base_url: str = "http://localhost:8000", num_requests: int = 2):
    """Test the /chat endpoint with a request to fetch upcoming NFL games."""
    
    print("=" * 80)
    print("Testing /chat Endpoint Latency - Fetch Upcoming NFL Games")
    print("=" * 80)
    print(f"Base URL: {base_url}")
    print(f"Number of requests: {num_requests} (first creates agent, subsequent reuse cache)")
    print()
    
    endpoint = f"{base_url}/api/v1/agent/chat"
    
    # Test message
    test_message = "show me upcoming NFL games"
    print(f"Test request: '{test_message}'")
    print()
    
    results = []
    
    for i in range(num_requests):
        print(f"\n{'='*80}")
        print(f"Request #{i+1}")
        print(f"{'='*80}")
        
        # Prepare request
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": test_message
                }
            ],
            "session_id": f"test-session-{i+1}"
        }
        
        print(f"Sending request to {endpoint}...")
        print("-" * 80)
        
        start_time = time.time()
        
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60  # 60 second timeout
            )
            
            end_time = time.time()
            total_latency = (end_time - start_time) * 1000
            
            if response.status_code == 200:
                result_data = response.json()
                messages = result_data.get("messages", [])
                
                print("-" * 80)
                print()
                print(f"✓ Request #{i+1} completed successfully")
                print(f"  Status Code: {response.status_code}")
                print(f"  Total Latency: {total_latency:.2f}ms ({total_latency/1000:.3f}s)")
                print(f"  Response Messages: {len(messages)}")
                
                # Extract response content
                if messages:
                    last_message = messages[-1]
                    if isinstance(last_message, dict):
                        content = last_message.get("content", "")
                    else:
                        content = str(last_message)
                    
                    print()
                    print("Response Preview:")
                    print("-" * 80)
                    preview = str(content)[:300]
                    print(preview)
                    if len(str(content)) > 300:
                        print("...")
                    print("-" * 80)
                
                results.append({
                    "request_num": i + 1,
                    "latency_ms": total_latency,
                    "success": True,
                    "status_code": response.status_code,
                    "message_count": len(messages)
                })
            else:
                print("-" * 80)
                print()
                print(f"✗ Request #{i+1} failed")
                print(f"  Status Code: {response.status_code}")
                print(f"  Response: {response.text[:500]}")
                
                results.append({
                    "request_num": i + 1,
                    "latency_ms": total_latency,
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:200]
                })
                
        except requests.exceptions.Timeout:
            end_time = time.time()
            total_latency = (end_time - start_time) * 1000
            print(f"✗ Request #{i+1} timed out after {total_latency:.2f}ms")
            results.append({
                "request_num": i + 1,
                "latency_ms": total_latency,
                "success": False,
                "error": "Timeout"
            })
        except Exception as e:
            end_time = time.time()
            total_latency = (end_time - start_time) * 1000
            print(f"✗ Request #{i+1} error: {str(e)}")
            results.append({
                "request_num": i + 1,
                "latency_ms": total_latency,
                "success": False,
                "error": str(e)
            })
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if r.get("success")]
    if successful:
        latencies = [r["latency_ms"] for r in successful]
        print(f"Successful Requests: {len(successful)}/{num_requests}")
        print(f"Average Latency: {sum(latencies)/len(latencies):.2f}ms")
        print(f"Min Latency: {min(latencies):.2f}ms")
        print(f"Max Latency: {max(latencies):.2f}ms")
        
        if len(successful) > 1:
            first_latency = successful[0]["latency_ms"]
            subsequent_latencies = [r["latency_ms"] for r in successful[1:]]
            avg_subsequent = sum(subsequent_latencies) / len(subsequent_latencies)
            improvement = first_latency - avg_subsequent
            improvement_pct = (improvement / first_latency) * 100
            
            print()
            print("Caching Impact:")
            print(f"  First Request (agent creation): {first_latency:.2f}ms")
            print(f"  Subsequent Requests (cached): {avg_subsequent:.2f}ms (avg)")
            print(f"  Improvement: {improvement:.2f}ms ({improvement_pct:.1f}% faster)")
    else:
        print("No successful requests")
    
    failed = [r for r in results if not r.get("success")]
    if failed:
        print()
        print(f"Failed Requests: {len(failed)}")
        for r in failed:
            print(f"  Request #{r['request_num']}: {r.get('error', 'Unknown error')}")
    
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test /chat endpoint latency")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=2,
        help="Number of requests to make (default: 2)"
    )
    
    args = parser.parse_args()
    
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if server is running
    try:
        health_check = requests.get(f"{args.url}/health", timeout=2)
        print(f"✓ Server is running")
    except:
        print(f"⚠ Warning: Could not connect to {args.url}")
        print("  Make sure the server is running with: uvicorn app.main:app --reload")
        print()
    
    results = test_chat_endpoint_latency(args.url, args.requests)

