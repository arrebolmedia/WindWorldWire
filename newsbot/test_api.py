#!/usr/bin/env python3
"""Test script for the ingestor FastAPI endpoints."""

import requests
import json
import os
import time


def test_endpoints():
    """Test the ingestor API endpoints."""
    base_url = "http://localhost:8001"
    
    print("🧪 Testing NewsBot Ingestor API")
    print(f"Base URL: {base_url}")
    print("=" * 50)
    
    # Test health check
    print("\n1. Testing /healthz endpoint...")
    try:
        response = requests.get(f"{base_url}/healthz", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test root endpoint
    print("\n2. Testing / endpoint...")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
    
    # Test config endpoint
    print("\n3. Testing /config endpoint...")
    try:
        response = requests.get(f"{base_url}/config", timeout=10)
        print(f"Status: {response.status_code}")
        config_data = response.json()
        print(f"Manual run enabled: {config_data.get('manual_run_enabled', False)}")
        print(f"Window hours: {config_data.get('config', {}).get('window_hours', 'not set')}")
    except Exception as e:
        print(f"❌ Config endpoint failed: {e}")
    
    # Test manual run endpoint
    print("\n4. Testing /run endpoint...")
    manual_run_enabled = os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    
    if not manual_run_enabled:
        print("⚠️  Manual runs disabled. Set ALLOW_MANUAL_RUN=true to test.")
        print("Testing with disabled state...")
        
        try:
            response = requests.post(f"{base_url}/run", timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Expected error: {e}")
    else:
        print("✅ Manual runs enabled. Running ingestion...")
        
        try:
            # Test with custom window hours
            response = requests.post(
                f"{base_url}/run",
                params={"window_hours": 1},  # Small window for testing
                timeout=60  # Longer timeout for actual processing
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Ingestion completed successfully!")
                print(f"Status: {result['status']}")
                print(f"Message: {result['message']}")
                
                stats = result['stats']
                print("\nStatistics:")
                print(f"  - Runtime: {stats.get('runtime_seconds', 0)}s")
                print(f"  - Sources OK: {stats.get('sources_ok', 0)}")
                print(f"  - Sources 304: {stats.get('sources_304', 0)}")
                print(f"  - Sources Error: {stats.get('sources_error', 0)}")
                print(f"  - Items Total: {stats.get('items_total', 0)}")
                print(f"  - Items Inserted: {stats.get('items_inserted', 0)}")
                print(f"  - Items Duplicated: {stats.get('items_duplicated', 0)}")
                print(f"  - Items SimHash Filtered: {stats.get('items_simhash_filtered', 0)}")
                
                if stats.get('errors'):
                    print(f"  - Errors: {len(stats['errors'])}")
                    print("    First few errors:")
                    for error in stats['errors'][:3]:
                        print(f"      - {error}")
            else:
                print(f"❌ Ingestion failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Run endpoint failed: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 API testing completed!")


if __name__ == "__main__":
    print("Starting API tests...")
    print("Make sure the ingestor service is running:")
    print("  python -m newsbot.ingestor.app")
    print("\nTo enable manual runs:")
    print("  export ALLOW_MANUAL_RUN=true")
    print("  # or on Windows:")
    print("  set ALLOW_MANUAL_RUN=true")
    
    input("\nPress Enter when the service is ready...")
    
    test_endpoints()