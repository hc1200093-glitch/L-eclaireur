#!/usr/bin/env python3
"""
Backend API Tests for L'Éclaireur Application
Tests the FastAPI endpoints without consuming LLM credits
"""

import requests
import sys
import io
from datetime import datetime

class LEclaireurAPITester:
    def __init__(self, base_url="https://bonjour-e1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details
        })

    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy" and data.get("service") == "L'Éclaireur":
                    self.log_test("Health Endpoint", True)
                    return True
                else:
                    self.log_test("Health Endpoint", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("Health Endpoint", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Health Endpoint", False, f"Exception: {str(e)}")
            return False

    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "Bienvenue sur L'Éclaireur API" in data.get("message", ""):
                    self.log_test("Root Endpoint", True)
                    return True
                else:
                    self.log_test("Root Endpoint", False, f"Unexpected message: {data}")
                    return False
            else:
                self.log_test("Root Endpoint", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Root Endpoint", False, f"Exception: {str(e)}")
            return False

    def test_analyze_endpoint_structure(self):
        """Test /api/analyze endpoint accepts multipart/form-data (without actual file)"""
        try:
            # Test with no file - should return 422 (validation error)
            response = requests.post(f"{self.api_url}/analyze", timeout=10)
            
            if response.status_code == 422:
                self.log_test("Analyze Endpoint Structure", True, "Correctly rejects empty request")
                return True
            else:
                self.log_test("Analyze Endpoint Structure", False, f"Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Analyze Endpoint Structure", False, f"Exception: {str(e)}")
            return False

    def test_analyze_endpoint_file_validation(self):
        """Test /api/analyze endpoint file validation (with non-PDF file)"""
        try:
            # Create a fake text file to test validation
            fake_file = io.BytesIO(b"This is not a PDF file")
            files = {'file': ('test.txt', fake_file, 'text/plain')}
            
            response = requests.post(f"{self.api_url}/analyze", files=files, timeout=10)
            
            if response.status_code == 400:
                data = response.json()
                if "PDF" in data.get("detail", ""):
                    self.log_test("Analyze File Validation", True, "Correctly rejects non-PDF files")
                    return True
                else:
                    self.log_test("Analyze File Validation", False, f"Unexpected error message: {data}")
                    return False
            else:
                self.log_test("Analyze File Validation", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Analyze File Validation", False, f"Exception: {str(e)}")
            return False

    def test_analyses_endpoint(self):
        """Test /api/analyses endpoint (get history)"""
        try:
            response = requests.get(f"{self.api_url}/analyses", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Analyses History Endpoint", True, f"Returns list with {len(data)} items")
                    return True
                else:
                    self.log_test("Analyses History Endpoint", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_test("Analyses History Endpoint", False, f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Analyses History Endpoint", False, f"Exception: {str(e)}")
            return False

    def test_cors_headers(self):
        """Test CORS configuration"""
        try:
            response = requests.options(f"{self.api_url}/health", timeout=10)
            
            cors_headers = [
                'Access-Control-Allow-Origin',
                'Access-Control-Allow-Methods',
                'Access-Control-Allow-Headers'
            ]
            
            has_cors = any(header in response.headers for header in cors_headers)
            
            if has_cors:
                self.log_test("CORS Configuration", True, "CORS headers present")
                return True
            else:
                self.log_test("CORS Configuration", False, "No CORS headers found")
                return False
                
        except Exception as e:
            self.log_test("CORS Configuration", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting L'Éclaireur Backend API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Run tests
        self.test_health_endpoint()
        self.test_root_endpoint()
        self.test_analyze_endpoint_structure()
        self.test_analyze_endpoint_file_validation()
        self.test_analyses_endpoint()
        self.test_cors_headers()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All backend tests passed!")
            return True
        else:
            print("⚠️  Some backend tests failed")
            failed_tests = [test for test in self.test_results if not test["success"]]
            print("\nFailed tests:")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
            return False

def main():
    """Main test runner"""
    tester = LEclaireurAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())