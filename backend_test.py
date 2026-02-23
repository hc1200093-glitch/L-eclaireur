#!/usr/bin/env python3
"""
L'Éclaireur Backend API Testing Suite
Tests all backend endpoints for the Quebec workers' compensation tool
"""

import requests
import sys
import json
from datetime import datetime
import tempfile
import os

class LEclaireurAPITester:
    def __init__(self, base_url="https://eclaireur-inspect.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        
    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            self.failed_tests.append({"name": name, "details": details})
            print(f"❌ {name} - FAILED: {details}")
        
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_test("Health Check", True)
                    return True
                else:
                    self.log_test("Health Check", False, f"Unexpected response: {data}")
            else:
                self.log_test("Health Check", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
        return False
    
    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "L'Éclaireur" in data.get("message", ""):
                    self.log_test("Root Endpoint", True)
                    return True
                else:
                    self.log_test("Root Endpoint", False, f"Unexpected message: {data}")
            else:
                self.log_test("Root Endpoint", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_test("Root Endpoint", False, f"Exception: {str(e)}")
        return False
    
    def test_visitor_stats(self):
        """Test visitor counter endpoints"""
        try:
            # Get current count
            response = requests.get(f"{self.api_url}/stats/visitors", timeout=10)
            if response.status_code == 200:
                initial_count = response.json().get("count", 0)
                
                # Increment count
                inc_response = requests.post(f"{self.api_url}/stats/visitors/increment", timeout=10)
                if inc_response.status_code == 200:
                    new_count = inc_response.json().get("count", 0)
                    if new_count > initial_count:
                        self.log_test("Visitor Counter", True)
                        return True
                    else:
                        self.log_test("Visitor Counter", False, f"Count not incremented: {initial_count} -> {new_count}")
                else:
                    self.log_test("Visitor Counter", False, f"Increment failed: {inc_response.status_code}")
            else:
                self.log_test("Visitor Counter", False, f"Get count failed: {response.status_code}")
        except Exception as e:
            self.log_test("Visitor Counter", False, f"Exception: {str(e)}")
        return False
    
    def test_testimonials(self):
        """Test testimonials endpoints including moderation"""
        try:
            # Get testimonials
            response = requests.get(f"{self.api_url}/testimonials", timeout=10)
            if response.status_code == 200:
                testimonials = response.json()
                
                # Test content moderation - should be rejected
                bad_testimonial = {
                    "name": "Test User",
                    "message": "Ce médecin est un connard qui m'a mal traité",  # Contains forbidden word
                    "rating": 1
                }
                
                bad_response = requests.post(
                    f"{self.api_url}/testimonials", 
                    json=bad_testimonial,
                    timeout=10
                )
                
                # Should be rejected (400 Bad Request)
                if bad_response.status_code == 400:
                    # Now test a good testimonial
                    good_testimonial = {
                        "name": "Marie Tremblay",
                        "message": "Très utile pour comprendre mon dossier CNESST, je recommande fortement cet outil",
                        "rating": 5
                    }
                    
                    create_response = requests.post(
                        f"{self.api_url}/testimonials", 
                        json=good_testimonial,
                        timeout=10
                    )
                    
                    if create_response.status_code == 200:
                        self.log_test("Testimonials & Moderation", True)
                        return True
                    else:
                        self.log_test("Testimonials & Moderation", False, f"Good testimonial failed: {create_response.status_code}")
                else:
                    self.log_test("Testimonials & Moderation", False, f"Moderation not working - bad content accepted: {bad_response.status_code}")
            else:
                self.log_test("Testimonials & Moderation", False, f"Get failed: {response.status_code}")
        except Exception as e:
            self.log_test("Testimonials & Moderation", False, f"Exception: {str(e)}")
        return False
    
    def test_medecins_endpoints(self):
        """Test physicians database endpoints"""
        try:
            # Get all medecins
            response = requests.get(f"{self.api_url}/medecins", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "disclaimer" in data and "medecins" in data:
                    
                    # Test search functionality
                    search_response = requests.get(f"{self.api_url}/medecins/search/test", timeout=10)
                    if search_response.status_code == 200:
                        search_data = search_response.json()
                        if "medecins" in search_data:
                            self.log_test("Medecins Database", True)
                            return True
                        else:
                            self.log_test("Medecins Database", False, "Search missing medecins field")
                    else:
                        self.log_test("Medecins Database", False, f"Search failed: {search_response.status_code}")
                else:
                    self.log_test("Medecins Database", False, "Missing required fields in response")
            else:
                self.log_test("Medecins Database", False, f"Get medecins failed: {response.status_code}")
        except Exception as e:
            self.log_test("Medecins Database", False, f"Exception: {str(e)}")
        return False
    
    def test_contributions(self):
        """Test contributions endpoint with moderation"""
        try:
            # Test creating a contribution with appropriate Quebec worker data
            test_contribution = {
                "medecin_nom": "TREMBLAY",
                "medecin_prenom": "Jean",
                "type_contribution": "pro_employe",
                "description": "Ce médecin a rendu une décision favorable dans mon dossier CNESST 12345. Rapport détaillé et objectif qui a aidé ma cause au TAT.",
                "source_reference": "Dossier TAT-2024-001"
            }
            
            create_response = requests.post(
                f"{self.api_url}/contributions",
                json=test_contribution,
                timeout=10
            )
            
            if create_response.status_code == 200:
                # Test moderation by trying inappropriate content
                bad_contribution = {
                    "medecin_nom": "TESTEUR",
                    "medecin_prenom": "Bad",
                    "type_contribution": "pro_employe", 
                    "description": "Ce médecin est un salaud qui ne comprend rien",  # Contains forbidden word
                    "source_reference": "Test"
                }
                
                bad_response = requests.post(
                    f"{self.api_url}/contributions",
                    json=bad_contribution,
                    timeout=10
                )
                
                # Should be rejected (400 Bad Request) 
                if bad_response.status_code == 400:
                    self.log_test("Contributions & Moderation", True)
                    return True
                else:
                    self.log_test("Contributions & Moderation", False, f"Moderation not working: {bad_response.status_code}")
            else:
                self.log_test("Contributions & Moderation", False, f"Create failed: {create_response.status_code}")
        except Exception as e:
            self.log_test("Contributions & Moderation", False, f"Exception: {str(e)}")
        return False
    
    def test_medecins_stats(self):
        """Test medecins statistics endpoint"""
        try:
            response = requests.get(f"{self.api_url}/stats/medecins", timeout=10)
            if response.status_code == 200:
                data = response.json()
                required_fields = ["disclaimer", "total_medecins_documentes", "total_contributions", "top_medecins_documentes"]
                if all(field in data for field in required_fields):
                    self.log_test("Medecins Statistics", True)
                    return True
                else:
                    missing = [f for f in required_fields if f not in data]
                    self.log_test("Medecins Statistics", False, f"Missing fields: {missing}")
            else:
                self.log_test("Medecins Statistics", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_test("Medecins Statistics", False, f"Exception: {str(e)}")
        return False
    
    def test_analyze_endpoint_structure(self):
        """Test analyze endpoint structure (without actual file upload)"""
        try:
            # Test with no file (should fail gracefully)
            response = requests.post(f"{self.api_url}/analyze", timeout=10)
            
            # Should return 422 (validation error) for missing file
            if response.status_code == 422:
                self.log_test("Analyze Endpoint Structure", True)
                return True
            else:
                self.log_test("Analyze Endpoint Structure", False, f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.log_test("Analyze Endpoint Structure", False, f"Exception: {str(e)}")
        return False
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("🔍 Starting L'Éclaireur Backend API Tests...")
        print(f"📡 Testing API at: {self.api_url}")
        print("=" * 60)
        
        # Core functionality tests
        self.test_health_endpoint()
        self.test_root_endpoint()
        self.test_visitor_stats()
        
        # Content management tests
        self.test_testimonials()
        self.test_medecins_endpoints()
        self.test_contributions()
        self.test_medecins_stats()
        
        # Analysis endpoint structure test
        self.test_analyze_endpoint_structure()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"  - {test['name']}: {test['details']}")
        
        success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
        print(f"✅ Success Rate: {success_rate:.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = LEclaireurAPITester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())