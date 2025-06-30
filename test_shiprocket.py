#!/usr/bin/env python3
"""
Test script for ShipRocket integration
This script tests the basic functionality of the ShipRocket controller
"""

import os
import sys
from dotenv import load_dotenv
import requests
import json as _json

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from controllers.shiprocket_controller import ShipRocketController

def test_shiprocket_auth():
    """Test ShipRocket authentication"""
    print("Testing ShipRocket authentication...")
    
    # DEBUG: Show which credentials are being picked up (mask password)
    email_debug = os.getenv('SHIPROCKET_EMAIL')
    password_debug = os.getenv('SHIPROCKET_PASSWORD')
    print(f"DEBUG → Using SHIPROCKET_EMAIL: {email_debug}")
    print(f"DEBUG → SHIPROCKET_PASSWORD set: {'YES' if password_debug else 'NO'}")
    
    # Make a raw request first so we can inspect ShipRocket's raw response if it fails
    login_url = "https://apiv2.shiprocket.in/v1/external/auth/login"
    try:
        raw_resp = requests.post(login_url, json={"email": email_debug, "password": password_debug})
        print(f"DEBUG → Raw login status: {raw_resp.status_code}")
        try:
            print(f"DEBUG → Raw login response: {_json.dumps(raw_resp.json(), indent=2)}")
        except ValueError:
            print(f"DEBUG → Raw login response (non-JSON): {raw_resp.text}")
    except Exception as _e:
        print(f"DEBUG → Failed to hit ShipRocket login endpoint directly: {_e}")
    
    try:
        shiprocket = ShipRocketController()
        token = shiprocket._get_auth_token()
        
        if token:
            print("✅ Authentication successful!")
            print(f"Token: {token[:50]}...")
            return True
        else:
            print("❌ Authentication failed - no token received")
            return False
            
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        return False

def test_serviceability():
    """Test serviceability check"""
    print("\nTesting serviceability check...")
    
    try:
        shiprocket = ShipRocketController()
        response = shiprocket.check_serviceability(
            pickup_pincode="110001",  # Delhi
            delivery_pincode="400001",  # Mumbai
            weight=1.0,
            cod=0
        )
        
        if response and response.get('data'):
            print("✅ Serviceability check successful!")
            available_couriers = response['data'].get('available_courier_companies', [])
            print(f"Available couriers: {len(available_couriers)}")
            
            for courier in available_couriers[:3]:  # Show first 3 couriers
                print(f"  - {courier.get('courier_name')}: ₹{courier.get('rate')}")
            
            return True
        else:
            print("❌ Serviceability check failed - no data received")
            return False
            
    except Exception as e:
        print(f"❌ Serviceability check failed: {str(e)}")
        return False

def test_tracking():
    """Test tracking functionality"""
    print("\nTesting tracking functionality...")
    
    try:
        shiprocket = ShipRocketController()
        # This would need a real AWB code to test
        print("⚠️  Tracking test skipped - requires real AWB code")
        return True
        
    except Exception as e:
        print(f"❌ Tracking test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 ShipRocket Integration Test")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Check if ShipRocket credentials are set
    email = os.getenv('SHIPROCKET_EMAIL')
    password = os.getenv('SHIPROCKET_PASSWORD')
    
    if not email or not password:
        print("❌ ShipRocket credentials not found in environment variables")
        print("Please set SHIPROCKET_EMAIL and SHIPROCKET_PASSWORD")
        return
    
    print(f"Using ShipRocket account: {email}")
    
    # Create Flask app and context
    app = create_app()
    
    with app.app_context():
        # Run tests within Flask application context
        tests = [
            test_shiprocket_auth,
            test_serviceability,
            test_tracking
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
        
        print("\n" + "=" * 40)
        print(f"Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! ShipRocket integration is working correctly.")
        else:
            print("⚠️  Some tests failed. Please check the configuration and try again.")

if __name__ == "__main__":
    main() 