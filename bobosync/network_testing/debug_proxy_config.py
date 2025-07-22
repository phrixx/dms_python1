#!/usr/bin/env python3
"""
Debug Proxy Configuration
Shows exactly what proxy settings are being used and tests them
"""

import os
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from: {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed")
except Exception as e:
    print(f"❌ Error loading .env: {e}")

def debug_proxy_settings():
    """Debug current proxy configuration"""
    print("\n🔍 Debugging Proxy Configuration")
    print("=" * 50)
    
    # Check environment variables
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    
    print(f"HTTP_PROXY: {http_proxy}")
    print(f"HTTPS_PROXY: {https_proxy}")
    
    # Check what AtHoc client will use
    athoc_url = os.getenv("ATHOC_SERVER_URL")
    print(f"AtHoc Server: {athoc_url}")
    
    if athoc_url and athoc_url.startswith('https://'):
        print("🔒 AtHoc uses HTTPS - requires HTTPS_PROXY setting")
        if not https_proxy:
            print("❌ HTTPS_PROXY not set! This is why your proxy isn't being used.")
            print("💡 Solution: Set HTTPS_PROXY in your .env file")
    elif athoc_url and athoc_url.startswith('http://'):
        print("🔓 AtHoc uses HTTP - requires HTTP_PROXY setting")
        if not http_proxy:
            print("❌ HTTP_PROXY not set!")
    
    return http_proxy, https_proxy

def test_proxy_session():
    """Test creating a session like AtHoc client does"""
    print("\n🧪 Testing Session Creation (like AtHoc client)")
    print("=" * 50)
    
    session = requests.Session()
    
    # Add proxy support (same as athoc_client.py)
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    
    if http_proxy or https_proxy:
        proxies = {}
        if http_proxy:
            proxies['http'] = http_proxy
        if https_proxy:
            proxies['https'] = https_proxy
        session.proxies.update(proxies)
        print(f"✅ Using proxy configuration: {proxies}")
    else:
        print("❌ No proxy configuration found")
    
    return session

def test_actual_request():
    """Test an actual request to see if proxy is used"""
    print("\n📡 Testing Actual Request")
    print("=" * 50)
    
    session = test_proxy_session()
    test_url = "https://httpbin.org/ip"
    
    try:
        print(f"Making request to: {test_url}")
        response = session.get(test_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Request successful!")
            print(f"Your IP as seen by server: {data.get('origin')}")
            
            # If using proxy, the IP should be different from your real IP
            print("\n💡 If you're using a proxy, the IP above should be the proxy's IP")
        else:
            print(f"❌ Request failed with status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

def fix_proxy_config():
    """Show how to fix the proxy configuration"""
    print("\n🔧 How to Fix Proxy Configuration")
    print("=" * 50)
    
    athoc_url = os.getenv("ATHOC_SERVER_URL")
    proxy_url = os.getenv("HTTP_PROXY", "http://localhost:8889")
    
    if athoc_url and athoc_url.startswith('https://'):
        print("For HTTPS AtHoc server, add this line to your .env file:")
        print(f"HTTPS_PROXY={proxy_url}")
        print()
        print("Your .env file should have both:")
        print(f"HTTP_PROXY={proxy_url}")
        print(f"HTTPS_PROXY={proxy_url}")
        
        # Show the fix
        env_file = Path(__file__).parent / '.env'
        print(f"\n📝 Edit {env_file} and change:")
        print("FROM: #HTTPS_PROXY=https://proxy.example.com:8080")
        print(f"TO:   HTTPS_PROXY={proxy_url}")

def main():
    print("🐛 AtHoc Proxy Configuration Debugger")
    print("=" * 60)
    
    # Step 1: Debug current settings
    debug_proxy_settings()
    
    # Step 2: Test session creation
    test_proxy_session()
    
    # Step 3: Test actual request
    test_actual_request()
    
    # Step 4: Show how to fix
    fix_proxy_config()
    
    print("\n" + "=" * 60)
    print("🏁 Debug Complete")

if __name__ == "__main__":
    main() 