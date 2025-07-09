#!/usr/bin/env python3
"""
Test script to verify all API endpoints are working correctly.
Run this locally before deploying to Render.
"""

import requests
import json
import sys

def test_endpoint(url, name):
    """Test a single endpoint and return the result."""
    try:
        print(f"\n🔍 Testing {name}: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2)}")
                print(f"   ✅ {name} - SUCCESS")
                return True
            except json.JSONDecodeError:
                print(f"   Response text: {response.text[:200]}...")
                print(f"   ❌ {name} - Invalid JSON response")
                return False
        else:
            print(f"   Response: {response.text[:200]}...")
            print(f"   ❌ {name} - HTTP Error {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ {name} - Connection Error: {str(e)}")
        return False

def main():
    """Main test function."""
    print("🚀 Testing GULP Job Scraper API Endpoints")
    print("=" * 50)
    
    # Define base URL
    base_url = "http://localhost:8001"  # Change this for deployed version
    
    # Define endpoints to test
    endpoints = [
        (f"{base_url}/health", "Global Health Check"),
        (f"{base_url}/documents/health", "Document Health Check"),
        (f"{base_url}/documents/list", "Document List"),
        (f"{base_url}/api/email/config", "Email Config"),
        (f"{base_url}/projects", "Projects List"),
    ]
    
    # Test each endpoint
    results = []
    for url, name in endpoints:
        success = test_endpoint(url, name)
        results.append((name, success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} - {name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Ready for deployment.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
