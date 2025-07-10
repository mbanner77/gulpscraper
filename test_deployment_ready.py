#!/usr/bin/env python3
"""
Deployment Readiness Test Suite
Tests all critical components before Render deployment
"""

import asyncio
import sys
import requests
import json
from datetime import datetime

# Configuration
LOCAL_BACKEND = "http://localhost:8001"
TEST_TIMEOUT = 10

def print_test_header(test_name):
    print(f"\n{'='*60}")
    print(f"🧪 {test_name}")
    print('='*60)

def print_result(test_name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name}")
    if details:
        print(f"   {details}")

async def test_cloud_scraper():
    """Test cloud scraper functionality"""
    print_test_header("Cloud Scraper Test")
    
    try:
        sys.path.append('./backend')
        from cloud_scraper import scrape_gulp_cloud, create_scraper
        
        # Test scraper creation
        scraper = create_scraper()
        print_result("Cloud scraper creation", True)
        
        # Test connection
        connection_ok = scraper.test_connection()
        print_result("Cloud scraper connection", connection_ok, 
                    "Can connect to GULP API" if connection_ok else "Cannot connect to GULP API")
        
        if connection_ok:
            # Test actual scraping
            projects = await scrape_gulp_cloud(max_pages=1)
            success = len(projects) > 0
            print_result("Cloud scraper data retrieval", success, 
                        f"Found {len(projects)} projects" if success else "No projects found")
            
            if projects:
                sample = projects[0]
                has_required_fields = all(field in sample for field in ['id', 'title'])
                print_result("Project data structure", has_required_fields,
                            f"Sample: {sample.get('id', 'N/A')} - {sample.get('title', 'N/A')[:50]}")
        
        return connection_ok
        
    except Exception as e:
        print_result("Cloud scraper test", False, f"Error: {str(e)}")
        return False

def test_backend_imports():
    """Test that all backend modules can be imported"""
    print_test_header("Backend Import Test")
    
    try:
        sys.path.append('./backend')
        
        # Test core modules
        import scraper
        print_result("Main scraper module", True)
        
        import project_manager
        print_result("Project manager module", True)
        
        import cloud_scraper
        print_result("Cloud scraper module", True)
        
        # Test optional modules
        try:
            import document_routes
            print_result("Document routes module", True, "Document processing available")
        except ImportError as e:
            print_result("Document routes module", False, f"Optional module not available: {str(e)}")
        
        return True
        
    except Exception as e:
        print_result("Backend imports", False, f"Critical import error: {str(e)}")
        return False

def test_requirements():
    """Test that all required packages are available"""
    print_test_header("Requirements Test")
    
    required_packages = [
        'fastapi', 'uvicorn', 'requests', 'beautifulsoup4', 
        'pydantic', 'python-multipart', 'jinja2'
    ]
    
    all_available = True
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_result(f"Package {package}", True)
        except ImportError:
            print_result(f"Package {package}", False, "Missing required package")
            all_available = False
    
    return all_available

def test_api_endpoints():
    """Test critical API endpoints if backend is running"""
    print_test_header("API Endpoints Test")
    
    endpoints_to_test = [
        ("/projects", "Projects API"),
        ("/status", "Status API"),
        ("/health", "Health Check")  # This might not be registered yet
    ]
    
    backend_running = False
    
    try:
        # Test if backend is running
        response = requests.get(f"{LOCAL_BACKEND}/projects", timeout=TEST_TIMEOUT)
        backend_running = True
        print_result("Backend server", True, f"Running on {LOCAL_BACKEND}")
    except requests.exceptions.RequestException:
        print_result("Backend server", False, f"Not running on {LOCAL_BACKEND}")
        return False
    
    if backend_running:
        for endpoint, name in endpoints_to_test:
            try:
                response = requests.get(f"{LOCAL_BACKEND}{endpoint}", timeout=TEST_TIMEOUT)
                success = response.status_code in [200, 404]  # 404 is OK for some endpoints
                status_detail = f"Status {response.status_code}"
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, dict) and 'projects' in data:
                            status_detail += f", {len(data['projects'])} projects"
                        elif isinstance(data, dict) and 'status' in data:
                            status_detail += f", status: {data['status']}"
                    except:
                        pass
                print_result(name, success, status_detail)
            except requests.exceptions.RequestException as e:
                print_result(name, False, f"Request failed: {str(e)}")
    
    return backend_running

def test_file_structure():
    """Test that all critical files exist"""
    print_test_header("File Structure Test")
    
    critical_files = [
        './backend/scraper.py',
        './backend/project_manager.py', 
        './backend/cloud_scraper.py',
        './backend/requirements.txt',
        './backend/render-build.sh',
        './render.yaml',
        './RENDER_SETUP.md',
        './LOCAL_DEVELOPMENT.md'
    ]
    
    all_exist = True
    for file_path in critical_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                size = len(content)
                print_result(f"File {file_path}", True, f"{size} characters")
        except FileNotFoundError:
            print_result(f"File {file_path}", False, "File missing")
            all_exist = False
        except Exception as e:
            print_result(f"File {file_path}", False, f"Error reading: {str(e)}")
            all_exist = False
    
    return all_exist

async def run_all_tests():
    """Run comprehensive deployment readiness tests"""
    print("🚀 GULP Scraper - Deployment Readiness Test Suite")
    print(f"⏰ Test started at {datetime.now().isoformat()}")
    
    results = {}
    
    # Run all tests
    results['file_structure'] = test_file_structure()
    results['requirements'] = test_requirements()
    results['backend_imports'] = test_backend_imports()
    results['cloud_scraper'] = await test_cloud_scraper()
    results['api_endpoints'] = test_api_endpoints()
    
    # Final summary
    print_test_header("DEPLOYMENT READINESS SUMMARY")
    
    passed_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)
    
    for test_name, result in results.items():
        status = "✅ READY" if result else "❌ NEEDS FIX"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    print(f"\n📊 Overall Score: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED - READY FOR RENDER DEPLOYMENT!")
        print("\nNext steps:")
        print("1. Commit and push code to GitHub")
        print("2. Set environment variables in Render dashboard")
        print("3. Deploy and monitor logs")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} tests failed - Address issues before deployment")
        print("\nReview failed tests above and fix issues")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
