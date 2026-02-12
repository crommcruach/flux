#!/usr/bin/env python3
"""
Simple test script for ArtNet Routing API endpoints

Tests all 17 endpoints with minimal requests.
Run this AFTER starting the main application.

Usage:
    python tests/test_artnet_api_endpoints.py
"""

import requests
import json

BASE_URL = "http://localhost:5050"  # Adjust if using different port

def test_endpoint(method, path, data=None, expected_status=200):
    """Test a single endpoint"""
    url = f"{BASE_URL}{path}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data or {})
        elif method == "PUT":
            response = requests.put(url, json=data or {})
        elif method == "DELETE":
            response = requests.delete(url)
        else:
            print(f"❌ Unknown method: {method}")
            return False
        
        if response.status_code == expected_status:
            print(f"✅ {method:6} {path:40} -> {response.status_code}")
            return True
        else:
            print(f"❌ {method:6} {path:40} -> {response.status_code} (expected {expected_status})")
            print(f"   Response: {response.text[:100]}")
            return False
    except requests.ConnectionError:
        print(f"❌ {method:6} {path:40} -> CONNECTION ERROR")
        print("   Make sure the server is running!")
        return False
    except Exception as e:
        print(f"❌ {method:6} {path:40} -> ERROR: {e}")
        return False


def main():
    print("\n" + "=" * 80)
    print("ArtNet Routing API Endpoint Tests")
    print("=" * 80 + "\n")
    
    results = []
    
    # Test 1: Get initial state (should be empty)
    print("1. State Management")
    results.append(test_endpoint("GET", "/api/artnet/routing/state"))
    
    # Test 2: Get objects (should be empty initially)
    print("\n2. Object Endpoints")
    results.append(test_endpoint("GET", "/api/artnet/routing/objects"))
    
    # Test 3: Get outputs (should be empty initially)
    print("\n3. Output Endpoints")
    results.append(test_endpoint("GET", "/api/artnet/routing/outputs"))
    
    # Test 4: Sync from editor (might be empty if no shapes)
    print("\n4. Sync Endpoint")
    results.append(test_endpoint("POST", "/api/artnet/routing/sync", {"removeOrphaned": False}))
    
    # Test 5: Create a test object (will fail if no valid data, but endpoint should respond)
    print("\n5. Create Object (expected to fail without valid data)")
    test_data = {
        "id": "obj-test-123",
        "name": "Test Object",
        "sourceShapeId": "shape-test",
        "type": "matrix",
        "points": [],
        "ledType": "RGB",
        "channelsPerPixel": 3,
        "channelOrder": "RGB",
        "universeStart": 1,
        "universeEnd": 1
    }
    create_result = test_endpoint("POST", "/api/artnet/routing/objects", test_data, expected_status=201)
    results.append(create_result)
    
    # Test 6: Get the created object (only if create succeeded)
    if create_result:
        print("\n6. Get Single Object")
        results.append(test_endpoint("GET", "/api/artnet/routing/objects/obj-test-123"))
        
        # Test 7: Update the object
        print("\n7. Update Object")
        results.append(test_endpoint("PUT", "/api/artnet/routing/objects/obj-test-123", {
            "name": "Updated Test Object",
            "ledType": "RGBW"
        }))
        
        # Test 8: Delete the object
        print("\n8. Delete Object")
        results.append(test_endpoint("DELETE", "/api/artnet/routing/objects/obj-test-123"))
    else:
        print("\n   Skipping object GET/PUT/DELETE tests (create failed)")
        results.extend([False, False, False])
    
    # Test 9: Create a test output
    print("\n9. Create Output")
    output_data = {
        "id": "out-test-456",
        "name": "Test Output",
        "targetIP": "192.168.1.10",
        "subnet": "255.255.255.0",
        "startUniverse": 1,
        "fps": 30
    }
    output_create = test_endpoint("POST", "/api/artnet/routing/outputs", output_data, expected_status=201)
    results.append(output_create)
    
    # Test 10: Get single output (only if create succeeded)
    if output_create:
        print("\n10. Get Single Output")
        results.append(test_endpoint("GET", "/api/artnet/routing/outputs/out-test-456"))
        
        # Test 11: Update output
        print("\n11. Update Output")
        results.append(test_endpoint("PUT", "/api/artnet/routing/outputs/out-test-456", {
            "fps": 60
        }))
        
        # Test 12: Delete output
        print("\n12. Delete Output")
        results.append(test_endpoint("DELETE", "/api/artnet/routing/outputs/out-test-456"))
    else:
        print("\n   Skipping output GET/PUT/DELETE tests (create failed)")
        results.extend([False, False, False])
    
    # Test 13: Assignment operations (expected to fail without valid IDs)
    print("\n13. Assignment Operations (expected to fail without valid objects)")
    results.append(test_endpoint("POST", "/api/artnet/routing/assign", {
        "objectId": "obj-nonexistent",
        "outputId": "out-nonexistent"
    }, expected_status=404))
    
    # Test 14: Unassignment operations
    print("\n14. Unassignment Operations")
    results.append(test_endpoint("POST", "/api/artnet/routing/unassign", {
        "objectId": "obj-nonexistent",
        "outputId": "out-nonexistent"
    }, expected_status=404))
    
    # Test 15: Set state
    print("\n15. Set State")
    results.append(test_endpoint("POST", "/api/artnet/routing/state", {
        "state": {
            "objects": {},
            "outputs": {}
        }
    }))
    
    # Print summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {total - passed}")
    print(f"Success Rate: {(passed/total*100):.1f}%\n")
    
    if passed == total:
        print("🎉 All API endpoints are working!")
    else:
        print("⚠️  Some endpoints failed. Check the output above for details.")


if __name__ == "__main__":
    main()
