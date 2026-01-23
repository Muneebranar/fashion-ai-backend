#!/usr/bin/env python3
"""
Backend Verification Script
Run this to verify your backend is set up correctly
"""

import requests
import json
import sys
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"

def print_success(message):
    print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")

def print_error(message):
    print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")

def print_info(message):
    print(f"{Fore.BLUE}ℹ️  {message}{Style.RESET_ALL}")

def print_warning(message):
    print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")

def test_health_check():
    """Test if backend is running"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Testing Health Check...{Style.RESET_ALL}")
    print("="*50)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Backend is running!")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Database: {data.get('database')}")
            print_info(f"Version: {data.get('version')}")
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to backend!")
        print_info("Make sure the backend is running on port 8000")
        print_info("Run: python app/main.py")
        return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_root_endpoint():
    """Test root endpoint"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Testing Root Endpoint...{Style.RESET_ALL}")
    print("="*50)
    
    try:
        response = requests.get(BASE_URL, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Root endpoint working!")
            print_info(f"App: {data.get('name')}")
            print_info(f"Version: {data.get('version')}")
            print_info(f"Docs: {BASE_URL}{data.get('docs')}")
            return True
        else:
            print_error(f"Root endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_admin_login():
    """Test admin login"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Testing Admin Login...{Style.RESET_ALL}")
    print("="*50)
    
    try:
        credentials = {
            "email": "admin@fashionai.com",
            "password": "FashionAI@2025!Secure"
        }
        
        response = requests.post(
            f"{API_URL}/auth/login",
            json=credentials,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Admin login successful!")
            print_info(f"User: {data.get('user', {}).get('full_name')}")
            print_info(f"Email: {data.get('user', {}).get('email')}")
            print_info(f"Token: {data.get('access_token', '')[:50]}...")
            return data.get('access_token')
        else:
            print_error(f"Login failed with status {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None

def test_get_current_user(token):
    """Test getting current user with token"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Testing Get Current User...{Style.RESET_ALL}")
    print("="*50)
    
    if not token:
        print_warning("Skipping - no token available")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(
            f"{API_URL}/user/me",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Get current user successful!")
            print_info(f"Name: {data.get('full_name')}")
            print_info(f"Email: {data.get('email')}")
            print_info(f"Admin: {data.get('is_admin', False)}")
            return True
        else:
            print_error(f"Get user failed with status {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_clothing_endpoints(token):
    """Test clothing endpoints"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Testing Clothing Endpoints...{Style.RESET_ALL}")
    print("="*50)
    
    if not token:
        print_warning("Skipping - no token available")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # Test get clothing items
        response = requests.get(
            f"{API_URL}/clothing",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            items_count = len(data) if isinstance(data, list) else data.get('total', 0)
            print_success(f"Get clothing items successful! ({items_count} items)")
        else:
            print_error(f"Get clothing failed with status {response.status_code}")
            return False
        
        # Test get stats
        response = requests.get(
            f"{API_URL}/clothing/stats",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Get clothing stats successful!")
            print_info(f"Total items: {data.get('total_items', 0)}")
            print_info(f"Favorites: {data.get('favorites_count', 0)}")
            print_info(f"Categories: {data.get('categories', 0)}")
            return True
        else:
            print_error(f"Get stats failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def test_registration():
    """Test user registration"""
    print("\n" + "="*50)
    print(f"{Fore.CYAN}Testing User Registration...{Style.RESET_ALL}")
    print("="*50)
    
    try:
        import time
        test_email = f"test{int(time.time())}@example.com"
        
        user_data = {
            "full_name": "Test User",
            "email": test_email,
            "password": "TestPass123"
        }
        
        response = requests.post(
            f"{API_URL}/auth/register",
            json=user_data,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            print_success("Registration successful!")
            print_info(f"User: {data.get('user', {}).get('full_name')}")
            print_info(f"Email: {data.get('user', {}).get('email')}")
            return True
        else:
            print_error(f"Registration failed with status {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def run_all_tests():
    """Run all tests"""
    print(f"\n{Fore.MAGENTA}{'='*50}")
    print(f"{Fore.MAGENTA}🧪 BACKEND VERIFICATION SCRIPT")
    print(f"{Fore.MAGENTA}{'='*50}{Style.RESET_ALL}\n")
    
    print_info(f"Testing backend at: {BASE_URL}")
    print_info(f"API endpoints at: {API_URL}\n")
    
    results = {}
    
    # Run tests
    results['health'] = test_health_check()
    
    if not results['health']:
        print_error("\n❌ Backend is not running! Please start it first.")
        print_info("Run: python app/main.py")
        sys.exit(1)
    
    results['root'] = test_root_endpoint()
    results['login'] = False
    results['current_user'] = False
    results['clothing'] = False
    results['registration'] = False
    
    token = test_admin_login()
    if token:
        results['login'] = True
        results['current_user'] = test_get_current_user(token)
        results['clothing'] = test_clothing_endpoints(token)
    
    results['registration'] = test_registration()
    
    # Print summary
    print("\n" + "="*50)
    print(f"{Fore.MAGENTA}📊 TEST SUMMARY{Style.RESET_ALL}")
    print("="*50 + "\n")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        color = Fore.GREEN if result else Fore.RED
        print(f"{color}{status}{Style.RESET_ALL} - {test.replace('_', ' ').title()}")
    
    print("\n" + "="*50)
    print(f"Total: {passed}/{total} tests passed")
    print("="*50 + "\n")
    
    if passed == total:
        print(f"{Fore.GREEN}🎉 All tests passed! Your backend is ready!{Style.RESET_ALL}\n")
        print(f"{Fore.CYAN}Next steps:{Style.RESET_ALL}")
        print(f"  1. Start your React Native app: npx expo start")
        print(f"  2. Update config.js with your API URL")
        print(f"  3. Test login in the app with:")
        print(f"     Email: admin@fashionai.com")
        print(f"     Password: FashionAI@2025!Secure")
        return 0
    else:
        print(f"{Fore.RED}❌ Some tests failed. Please fix the issues above.{Style.RESET_ALL}\n")
        return 1

if __name__ == "__main__":
    try:
        exit_code = run_all_tests()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted by user{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)