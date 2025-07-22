#!/usr/bin/env python3
"""
SSL Verification Test Script
Tests SSL certificate validation and shows what's failing when DISABLE_SSL_VERIFY=false
"""

import os
import ssl
import socket
import requests
import urllib3
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter
from pathlib import Path
import subprocess
import sys

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from: {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed")
except Exception as e:
    print(f"❌ Error loading .env: {e}")

class TLS12HttpAdapter(HTTPAdapter):
    """Same adapter as used in athoc_client.py"""
    def __init__(self, *args, **kwargs):
        self.ssl_context = create_urllib3_context(
            ssl_minimum_version=ssl.TLSVersion.TLSv1_2
        )
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)

def get_certificate_info(hostname, port=443):
    """Get certificate information from a server"""
    print(f"\n🔍 Certificate Analysis for {hostname}:{port}")
    print("=" * 60)
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        
        # Connect and get certificate
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                print(f"✅ SSL Connection successful")
                print(f"📋 Certificate Subject: {cert.get('subject')}")
                print(f"📋 Certificate Issuer: {cert.get('issuer')}")
                print(f"📅 Valid From: {cert.get('notBefore')}")
                print(f"📅 Valid Until: {cert.get('notAfter')}")
                print(f"🔐 SSL Version: {ssock.version()}")
                
                # Check Subject Alternative Names
                san_list = []
                for field in cert.get('subjectAltName', []):
                    if field[0] == 'DNS':
                        san_list.append(field[1])
                
                if san_list:
                    print(f"🌐 Subject Alternative Names: {', '.join(san_list)}")
                else:
                    print("⚠️  No Subject Alternative Names found")
                
                return cert
                
    except ssl.SSLError as e:
        print(f"❌ SSL Error: {e}")
        return None
    except socket.timeout:
        print(f"❌ Connection timeout")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_ssl_verification_modes(url):
    """Test different SSL verification modes"""
    print(f"\n🧪 Testing SSL Verification Modes for {url}")
    print("=" * 60)
    
    hostname = url.replace('https://', '').replace('http://', '').split('/')[0]
    
    # Test 1: With SSL verification (default)
    print("\n1️⃣ Testing with SSL Verification ENABLED (normal mode)")
    try:
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        session.verify = True  # Enable SSL verification
        
        response = session.get(url, timeout=10)
        print(f"   ✅ SSL Verification PASSED")
        print(f"   📊 Status Code: {response.status_code}")
        
    except requests.exceptions.SSLError as e:
        print(f"   ❌ SSL Verification FAILED: {e}")
        print(f"   🔍 This is why DISABLE_SSL_VERIFY=true is needed")
        
    except Exception as e:
        print(f"   ❌ Other error: {e}")
    
    # Test 2: With SSL verification disabled
    print("\n2️⃣ Testing with SSL Verification DISABLED")
    try:
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        session.verify = False  # Disable SSL verification
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = session.get(url, timeout=10)
        print(f"   ✅ Connection successful (SSL verification bypassed)")
        print(f"   📊 Status Code: {response.status_code}")
        
    except Exception as e:
        print(f"   ❌ Error even with SSL disabled: {e}")
    
    # Test 3: Manual SSL context (like the adapter uses)
    print("\n3️⃣ Testing with Custom SSL Context (TLS 1.2+)")
    try:
        session = requests.Session()
        
        # Create the same SSL context as TLS12HttpAdapter
        ssl_context = create_urllib3_context(
            ssl_minimum_version=ssl.TLSVersion.TLSv1_2
        )
        
        class TestAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs['ssl_context'] = ssl_context
                return super().init_poolmanager(*args, **kwargs)
        
        session.mount('https://', TestAdapter())
        session.verify = True
        
        response = session.get(url, timeout=10)
        print(f"   ✅ Custom SSL context successful")
        print(f"   📊 Status Code: {response.status_code}")
        
    except Exception as e:
        print(f"   ❌ Custom SSL context failed: {e}")

def check_system_ca_bundle():
    """Check system CA certificate bundle"""
    print(f"\n🔐 System Certificate Store Analysis")
    print("=" * 60)
    
    # Check where requests looks for CA certificates
    try:
        import certifi
        ca_bundle_path = certifi.where()
        print(f"📂 CA Bundle Location: {ca_bundle_path}")
        
        # Check if file exists and get size
        if os.path.exists(ca_bundle_path):
            size = os.path.getsize(ca_bundle_path)
            print(f"📊 CA Bundle Size: {size:,} bytes")
            
            # Count certificates in bundle
            with open(ca_bundle_path, 'r') as f:
                content = f.read()
                cert_count = content.count('-----BEGIN CERTIFICATE-----')
                print(f"🔢 Certificates in bundle: {cert_count}")
        else:
            print(f"❌ CA Bundle file not found!")
            
    except ImportError:
        print("⚠️  certifi package not available")
        
    # Check system SSL paths
    print(f"\n🗂️ System SSL Paths:")
    for path_name, path_value in [
        ("Default CA file", ssl.get_default_verify_paths().cafile),
        ("Default CA path", ssl.get_default_verify_paths().capath),
        ("OpenSSL CA file", ssl.get_default_verify_paths().openssl_cafile),
        ("OpenSSL CA path", ssl.get_default_verify_paths().openssl_capath),
    ]:
        print(f"   {path_name}: {path_value}")

def suggest_fixes(hostname):
    """Suggest ways to fix SSL verification"""
    print(f"\n🔧 How to Fix SSL Verification for {hostname}")
    print("=" * 60)
    
    print("1️⃣ **Corporate Environment Fixes:**")
    print("   • Install corporate root CA certificates")
    print("   • Configure SSL_CERT_PATH in .env file")
    print("   • Use corporate certificate bundle")
    print("")
    
    print("2️⃣ **Manual Certificate Verification:**")
    print(f"   # Check certificate manually:")
    print(f"   openssl s_client -connect {hostname}:443 -servername {hostname}")
    print("")
    
    print("3️⃣ **Python Certificate Path:**")
    print("   # Set custom CA bundle:")
    print("   export SSL_CERT_FILE=/path/to/corporate-ca-bundle.pem")
    print("   export REQUESTS_CA_BUNDLE=/path/to/corporate-ca-bundle.pem")
    print("")
    
    print("4️⃣ **AtHoc Client Configuration:**")
    print("   # Add to .env file:")
    print("   SSL_CERT_PATH=/path/to/certificate.pem")
    print("")
    
    print("5️⃣ **Development/Testing (NOT for production):**")
    print("   # Keep current setting:")
    print("   DISABLE_SSL_VERIFY=true")

def test_proxy_ssl_interaction():
    """Test how proxy affects SSL verification"""
    print(f"\n🔗 Proxy + SSL Interaction Test")
    print("=" * 60)
    
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    
    if not (http_proxy or https_proxy):
        print("ℹ️  No proxy configured - skipping proxy SSL tests")
        return
    
    print(f"🔍 Testing with proxy: {https_proxy or http_proxy}")
    
    athoc_url = os.getenv("ATHOC_SERVER_URL", "https://catcloud.athocdevo.com")
    
    # Test with proxy + SSL verification
    print("\n📡 Testing: Proxy + SSL Verification ON")
    try:
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        
        if http_proxy:
            session.proxies['http'] = http_proxy
        if https_proxy:
            session.proxies['https'] = https_proxy
            
        session.verify = True  # SSL verification ON
        
        response = session.get(athoc_url, timeout=15)
        print(f"   ✅ Proxy + SSL verification successful")
        print(f"   📊 Status: {response.status_code}")
        
    except Exception as e:
        print(f"   ❌ Proxy + SSL verification failed: {e}")
        print(f"   💡 This combination may require special certificate handling")

def main():
    print("🔐 SSL Verification Diagnostic Tool")
    print("=" * 80)
    
    athoc_url = os.getenv("ATHOC_SERVER_URL", "https://catcloud.athocdevo.com")
    hostname = athoc_url.replace('https://', '').replace('http://', '').split('/')[0]
    
    # Step 1: Get certificate info
    cert_info = get_certificate_info(hostname)
    
    # Step 2: Test different SSL verification modes
    test_ssl_verification_modes(athoc_url)
    
    # Step 3: Check system CA bundle
    check_system_ca_bundle()
    
    # Step 4: Test proxy + SSL interaction
    test_proxy_ssl_interaction()
    
    # Step 5: Suggest fixes
    suggest_fixes(hostname)
    
    print(f"\n" + "=" * 80)
    print("🏁 SSL Verification Analysis Complete")
    print("=" * 80)
    
    # Final recommendation
    print("\n💡 **Recommendation:**")
    disable_ssl = os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"
    if disable_ssl:
        print("   Currently using DISABLE_SSL_VERIFY=true")
        print("   ✅ This is acceptable for development/testing")
        print("   ⚠️  For production, consider proper certificate setup")
    else:
        print("   Currently using SSL verification (DISABLE_SSL_VERIFY=false)")
        print("   🔍 Check the SSL verification test results above")
        print("   💡 If failing, either fix certificates or use DISABLE_SSL_VERIFY=true")

if __name__ == "__main__":
    main() 