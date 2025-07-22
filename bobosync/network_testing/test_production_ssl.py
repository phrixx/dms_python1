#!/usr/bin/env python3
"""
Production AtHoc SSL Verification Test
Tests SSL verification for https://alerts1.eu.athoc.com (customer production system)
"""

import os
import ssl
import socket
import requests
import urllib3
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except:
    pass

class ProductionTLS12HttpAdapter(HTTPAdapter):
    """TLS adapter specifically for production testing"""
    def __init__(self, disable_ssl_verify=False, *args, **kwargs):
        self.ssl_context = create_urllib3_context(
            ssl_minimum_version=ssl.TLSVersion.TLSv1_2
        )
        
        if disable_ssl_verify:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)

def test_production_ssl_verification():
    """Test SSL verification for production AtHoc system"""
    print("🔐 Production AtHoc SSL Verification Test")
    print("=" * 80)
    
    production_url = "https://alerts1.eu.athoc.com"
    hostname = "alerts1.eu.athoc.com"
    
    print(f"🎯 Target: {production_url}")
    print(f"📍 This is the PRODUCTION system customers will connect to")
    print()
    
    # Test 1: SSL Verification ENABLED (what customers need)
    print("1️⃣ Testing SSL Verification ENABLED (Production Mode)")
    print("-" * 50)
    try:
        session = requests.Session()
        adapter = ProductionTLS12HttpAdapter(disable_ssl_verify=False)
        session.mount('https://', adapter)
        session.verify = True  # Enable SSL verification
        
        response = session.get(production_url, timeout=15)
        print(f"   ✅ SSL Verification WORKS for production system!")
        print(f"   📊 Status Code: {response.status_code}")
        print(f"   🔒 SSL verification successful - customers can use DISABLE_SSL_VERIFY=false")
        ssl_works = True
        
    except requests.exceptions.SSLError as e:
        print(f"   ❌ SSL Verification FAILED: {e}")
        print(f"   💡 Customers will need DISABLE_SSL_VERIFY=true")
        ssl_works = False
        
    except Exception as e:
        print(f"   ❌ Other error: {e}")
        ssl_works = False
    
    print()
    
    # Test 2: SSL Verification DISABLED (fallback option)
    print("2️⃣ Testing SSL Verification DISABLED (Fallback Mode)")
    print("-" * 50)
    try:
        session = requests.Session()
        adapter = ProductionTLS12HttpAdapter(disable_ssl_verify=True)
        session.mount('https://', adapter)
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = session.get(production_url, timeout=15)
        print(f"   ✅ Connection successful (SSL verification bypassed)")
        print(f"   📊 Status Code: {response.status_code}")
        fallback_works = True
        
    except Exception as e:
        print(f"   ❌ Even SSL disabled failed: {e}")
        fallback_works = False
    
    print()
    
    # Test 3: Certificate Analysis
    print("3️⃣ Certificate Chain Analysis")
    print("-" * 50)
    try:
        # Use a more permissive context for analysis
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                print(f"   📋 Certificate Subject: {cert.get('subject')}")
                print(f"   📋 Certificate Issuer: {cert.get('issuer')}")
                print(f"   📅 Valid From: {cert.get('notBefore')}")
                print(f"   📅 Valid Until: {cert.get('notAfter')}")
                print(f"   🔐 SSL Version: {ssock.version()}")
                
                # Check Subject Alternative Names
                san_list = []
                for field in cert.get('subjectAltName', []):
                    if field[0] == 'DNS':
                        san_list.append(field[1])
                
                if san_list:
                    print(f"   🌐 Subject Alternative Names: {', '.join(san_list)}")
                    
                # Check if hostname matches
                matches_hostname = any(hostname in san for san in san_list) or hostname in str(cert.get('subject', ''))
                print(f"   🎯 Hostname Match: {'✅ Yes' if matches_hostname else '❌ No'}")
                
    except Exception as e:
        print(f"   ❌ Certificate analysis failed: {e}")
    
    print()
    
    # Test 4: Proxy + SSL Combination (real customer scenario)
    print("4️⃣ Testing Proxy + SSL (Customer Scenario)")
    print("-" * 50)
    
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    
    if http_proxy or https_proxy:
        print(f"   🔗 Using proxy: {https_proxy or http_proxy}")
        
        # Test with proxy + SSL enabled
        try:
            session = requests.Session()
            adapter = ProductionTLS12HttpAdapter(disable_ssl_verify=False)
            session.mount('https://', adapter)
            
            if http_proxy:
                session.proxies['http'] = http_proxy
            if https_proxy:
                session.proxies['https'] = https_proxy
                
            session.verify = True
            
            response = session.get(production_url, timeout=20)
            print(f"   ✅ Proxy + SSL verification successful!")
            print(f"   📊 Status: {response.status_code}")
            proxy_ssl_works = True
            
        except Exception as e:
            print(f"   ❌ Proxy + SSL verification failed: {e}")
            proxy_ssl_works = False
        
        # Test with proxy + SSL disabled
        try:
            session = requests.Session()
            adapter = ProductionTLS12HttpAdapter(disable_ssl_verify=True)
            session.mount('https://', adapter)
            
            if http_proxy:
                session.proxies['http'] = http_proxy
            if https_proxy:
                session.proxies['https'] = https_proxy
                
            session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = session.get(production_url, timeout=20)
            print(f"   ✅ Proxy + SSL disabled successful!")
            print(f"   📊 Status: {response.status_code}")
            proxy_fallback_works = True
            
        except Exception as e:
            print(f"   ❌ Proxy + SSL disabled failed: {e}")
            proxy_fallback_works = False
            
    else:
        print("   ℹ️  No proxy configured - skipping proxy tests")
        proxy_ssl_works = None
        proxy_fallback_works = None
    
    print()
    
    return {
        'ssl_works': ssl_works,
        'fallback_works': fallback_works,
        'proxy_ssl_works': proxy_ssl_works,
        'proxy_fallback_works': proxy_fallback_works
    }

def generate_customer_recommendations(test_results):
    """Generate recommendations for customer deployment"""
    print("📋 Customer Deployment Recommendations")
    print("=" * 80)
    
    ssl_works = test_results['ssl_works']
    fallback_works = test_results['fallback_works']
    proxy_ssl_works = test_results['proxy_ssl_works']
    proxy_fallback_works = test_results['proxy_fallback_works']
    
    print("🎯 **For Production AtHoc System (alerts1.eu.athoc.com):**")
    print()
    
    if ssl_works:
        print("✅ **GOOD NEWS: SSL Verification Works!**")
        print("   Customers can use: DISABLE_SSL_VERIFY=false")
        print("   This provides full security with certificate validation")
        print()
        
        if proxy_ssl_works:
            print("✅ **Proxy + SSL also works**")
            print("   Corporate proxy environments fully supported")
        elif proxy_ssl_works is False:
            print("⚠️  **Proxy + SSL combination has issues**")
            print("   May need DISABLE_SSL_VERIFY=true in proxy environments")
        
    else:
        print("❌ **SSL Verification Fails**")
        print("   Same certificate chain issue as development system")
        print("   Customers will need: DISABLE_SSL_VERIFY=true")
        print()
        
        if fallback_works:
            print("✅ **Fallback option works**")
            print("   DISABLE_SSL_VERIFY=true provides working connectivity")
        else:
            print("❌ **Major connectivity issues**")
            print("   Even with SSL disabled, connection fails")
    
    print()
    print("🔧 **Recommended Customer Configuration:**")
    print()
    
    if ssl_works and (proxy_ssl_works is None or proxy_ssl_works):
        # Best case scenario
        print("```env")
        print("# Secure configuration (recommended)")
        print("ATHOC_SERVER_URL=https://alerts1.eu.athoc.com")
        print("DISABLE_SSL_VERIFY=false")
        print("# Add proxy settings if needed:")
        print("# HTTP_PROXY=http://corporate-proxy:8080")
        print("# HTTPS_PROXY=http://corporate-proxy:8080")
        print("```")
        
    elif fallback_works:
        # Working but less secure
        print("```env")
        print("# Working configuration (acceptable for production)")
        print("ATHOC_SERVER_URL=https://alerts1.eu.athoc.com")
        print("DISABLE_SSL_VERIFY=true")
        print("# Add proxy settings if needed:")
        print("# HTTP_PROXY=http://corporate-proxy:8080")
        print("# HTTPS_PROXY=http://corporate-proxy:8080")
        print("```")
        
    else:
        print("❌ **CONNECTIVITY ISSUES**")
        print("   Need to investigate network/firewall issues with customer")
    
    print()
    print("📞 **Customer Support Checklist:**")
    print("1. ✅ Test basic connectivity to alerts1.eu.athoc.com")
    print("2. ✅ Configure proxy settings if required")
    print("3. ✅ Test with DISABLE_SSL_VERIFY=true first")
    print("4. ✅ If needed, work with customer IT for SSL certificate setup")
    print("5. ✅ Validate AtHoc authentication credentials")

def main():
    print("🌍 Production AtHoc SSL Testing Suite")
    print("=" * 80)
    print("Testing customer production environment connectivity")
    print()
    
    # Run comprehensive tests
    test_results = test_production_ssl_verification()
    
    # Generate customer recommendations
    generate_customer_recommendations(test_results)
    
    print()
    print("=" * 80)
    print("🏁 Production SSL Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    main() 