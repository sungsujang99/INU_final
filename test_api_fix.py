#!/usr/bin/env python3
import requests
import json

# Test the activity logs API to see if the fix is working
def test_activity_logs_api():
    # Replace with your actual backend URL
    base_url = "http://localhost:5001"  # Adjust if needed
    
    # You'll need a valid token - get this from your browser's localStorage
    token = input("Enter your JWT token (from browser localStorage 'inu_token'): ").strip()
    
    if not token:
        print("No token provided. Exiting.")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Test the activity logs API
        print("Testing /api/activity-logs endpoint...")
        response = requests.get(f"{base_url}/api/activity-logs?limit=10", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Response successful")
            print(f"📊 Total entries returned: {len(data)}")
            
            # Filter for coffee pot entries
            coffee_entries = [entry for entry in data if entry.get('product_code') == '5465433']
            print(f"☕ Coffee pot entries: {len(coffee_entries)}")
            
            for i, entry in enumerate(coffee_entries):
                print(f"   {i+1}. {entry['rack']}{entry['slot']} {entry['movement_type']} - "
                      f"Start: {entry.get('start_time', 'N/A')}, End: {entry.get('end_time', 'N/A')}")
            
            if len(coffee_entries) == 2:
                print("✅ FIXED: Correct number of entries (2)")
            else:
                print(f"❌ STILL BROKEN: Expected 2 entries, got {len(coffee_entries)}")
                
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        print("Make sure your backend server is running on the correct port")

if __name__ == "__main__":
    test_activity_logs_api() 