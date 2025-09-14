"""
FastAPI Trender API Testing Guide
=================================

This script provides examples of how to test the Trender API endpoints.
"""

import json

# API Configuration
API_BASE = "http://localhost:8002"
HEADERS = {"Content-Type": "application/json"}

def show_curl_examples():
    """Show curl command examples for testing the API."""
    
    print("🌐 FastAPI Trender API Testing Guide")
    print("=" * 50)
    
    print("\n📋 Available Endpoints:")
    print("  • GET  /healthz      → Health check")
    print("  • GET  /            → Service information")
    print("  • POST /trend/run   → Global trending analysis")
    print("  • POST /topics/run  → Per-topic analysis")
    
    print("\n🔧 Starting the Server:")
    print("  cd newsbot")
    print("  uv run python -m newsbot.trender.app")
    print("  # Server will start on http://localhost:8002")
    
    print("\n📊 Test Commands:")
    
    print("\n1. Health Check:")
    print("curl -X GET http://localhost:8002/healthz")
    print("Expected response: {\"status\": \"ok\", \"service\": \"trender\"}")
    
    print("\n2. Service Info:")
    print("curl -X GET http://localhost:8002/")
    print("Expected response: Service info with endpoints and configuration")
    
    print("\n3. Global Trending Analysis:")
    trending_request = {
        "window_hours": 3,
        "k_global": 5
    }
    print("curl -X POST http://localhost:8002/trend/run \\")
    print("     -H \"Content-Type: application/json\" \\")
    print(f"     -d '{json.dumps(trending_request, indent=2)}'")
    
    print("\n4. Per-Topic Analysis:")
    topics_request = {
        "window_hours": 3
    }
    print("curl -X POST http://localhost:8002/topics/run \\")
    print("     -H \"Content-Type: application/json\" \\")
    print(f"     -d '{json.dumps(topics_request, indent=2)}'")
    
    print("\n🔐 With Basic Authentication (if enabled):")
    print("Set environment variables:")
    print("  export TRENDER_AUTH_ENABLED=true")
    print("  export TRENDER_USERNAME=admin")
    print("  export TRENDER_PASSWORD=secret")
    
    print("\nThen add authentication to requests:")
    print("curl -X POST http://localhost:8002/trend/run \\")
    print("     -u admin:secret \\")
    print("     -H \"Content-Type: application/json\" \\")
    print(f"     -d '{json.dumps(trending_request, indent=2)}'")
    
    print("\n⚙️ Environment Variables:")
    print("  • ALLOW_MANUAL_RUN=true (default: true)")
    print("  • TRENDER_AUTH_ENABLED=false (default: false)")
    print("  • TRENDER_USERNAME=admin (if auth enabled)")
    print("  • TRENDER_PASSWORD=secret (if auth enabled)")
    
    print("\n📋 Request Validation:")
    print("TrendRunRequest:")
    print("  • window_hours: int (1-168 hours)")
    print("  • k_global: int (1-100 picks)")
    print("\nTopicsRunRequest:")
    print("  • window_hours: int (1-168 hours)")
    
    print("\n📊 Response Formats:")
    
    print("\nTrendRunResponse:")
    trend_response_example = {
        "status": "success",
        "message": "Found 8 trending picks (5 global, 3 topic-specific)",
        "counts": {
            "global_picks": 5,
            "topic_picks": 3,
            "total_picks": 8
        },
        "selection": {
            "global_picks": [
                {
                    "cluster_id": 101,
                    "composite_score": 0.92,
                    "final_score": 0.92,
                    "selection_type": "global",
                    "rank": 1
                }
            ],
            "topic_picks": [
                {
                    "cluster_id": 102,
                    "composite_score": 0.85,
                    "final_score": 0.765,
                    "selection_type": "topic",
                    "topic_key": "taiwan_seguridad",
                    "topic_priority": 0.9,
                    "rank": 1
                }
            ],
            "total_picks": 8
        }
    }
    print(json.dumps(trend_response_example, indent=2))
    
    print("\nTopicsRunResponse:")
    topics_response_example = {
        "status": "success", 
        "message": "Found 12 trending picks across 4 topics",
        "counts": {
            "total_topics": 4,
            "total_picks": 12,
            "topics_with_picks": 3
        },
        "topics": {
            "taiwan_seguridad": {
                "global_picks": [],
                "topic_picks": [
                    {
                        "cluster_id": 201,
                        "composite_score": 0.88,
                        "final_score": 0.792,
                        "selection_type": "topic",
                        "topic_key": "taiwan_seguridad",
                        "topic_priority": 0.9,
                        "rank": 1
                    }
                ],
                "total_picks": 1,
                "counts": {"global_picks": 0, "topic_picks": 1}
            }
        }
    }
    print(json.dumps(topics_response_example, indent=2))


def show_python_examples():
    """Show Python examples for testing the API."""
    
    print("\n" + "=" * 50)
    print("🐍 Python Client Examples")
    print("=" * 50)
    
    python_example = '''
import httpx
import asyncio
import json

async def test_trender_api():
    """Test the Trender API with httpx."""
    
    base_url = "http://localhost:8002"
    
    async with httpx.AsyncClient() as client:
        
        # Health check
        response = await client.get(f"{base_url}/healthz")
        print("Health check:", response.json())
        
        # Global trending
        trend_data = {"window_hours": 3, "k_global": 5}
        response = await client.post(
            f"{base_url}/trend/run",
            json=trend_data
        )
        print("Trending analysis:", response.json())
        
        # Topics analysis  
        topics_data = {"window_hours": 3}
        response = await client.post(
            f"{base_url}/topics/run",
            json=topics_data
        )
        print("Topics analysis:", response.json())

# Run the test
asyncio.run(test_trender_api())
'''
    
    print(python_example)


def show_postman_collection():
    """Show Postman collection format."""
    
    print("\n" + "=" * 50)
    print("📮 Postman Collection")
    print("=" * 50)
    
    postman_collection = {
        "info": {
            "name": "NewsBot Trender API",
            "description": "API for testing trending topics analysis",
            "version": "1.0.0"
        },
        "item": [
            {
                "name": "Health Check",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{base_url}}/healthz",
                        "host": ["{{base_url}}"],
                        "path": ["healthz"]
                    }
                }
            },
            {
                "name": "Service Info",
                "request": {
                    "method": "GET", 
                    "header": [],
                    "url": {
                        "raw": "{{base_url}}/",
                        "host": ["{{base_url}}"],
                        "path": [""]
                    }
                }
            },
            {
                "name": "Global Trending Analysis",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps({
                            "window_hours": 3,
                            "k_global": 5
                        }, indent=2)
                    },
                    "url": {
                        "raw": "{{base_url}}/trend/run",
                        "host": ["{{base_url}}"],
                        "path": ["trend", "run"]
                    }
                }
            },
            {
                "name": "Per-Topic Analysis",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type", 
                            "value": "application/json"
                        }
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps({
                            "window_hours": 3
                        }, indent=2)
                    },
                    "url": {
                        "raw": "{{base_url}}/topics/run",
                        "host": ["{{base_url}}"],
                        "path": ["topics", "run"]
                    }
                }
            }
        ],
        "variable": [
            {
                "key": "base_url",
                "value": "http://localhost:8002",
                "type": "string"
            }
        ]
    }
    
    print("Save this as 'trender-api.postman_collection.json':")
    print(json.dumps(postman_collection, indent=2))


if __name__ == "__main__":
    show_curl_examples()
    show_python_examples()
    show_postman_collection()
    
    print("\n" + "=" * 60)
    print("🎯 FastAPI Trender API is ready for testing!")
    print("=" * 60)
    print("Start the server and try the examples above.")
    print("The API provides comprehensive trending analysis")
    print("with proper validation, error handling, and authentication.")
    print("=" * 60)