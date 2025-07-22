#!/usr/bin/env python3
"""
Proxy Connection Test Script for AtHoc Integration
Tests various connection scenarios to help diagnose network issues at customer sites
"""

import os
import sys
import requests
import urllib3
import ssl
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter
from pathlib import Path
import time
import json

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("WARNING: python-dotenv not installed. Environment variables must be set manually.")
except Exception as e:
    print(f"WARNING: Could not load .env file: {e}")

class TLS12HttpAdapter(HTTPAdapter):
    """Transport adapter that enforces TLS 1.2"""
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

class ProxyTester:
    def __init__(self):
        self.athoc_url = os.getenv("ATHOC_SERVER_URL", "https://catcloud.athocdevo.com")
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.username = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")
        self.org_code = os.getenv("ORG_CODE")
        
        # Test URLs
        self.test_urls = [
            "https://httpbin.org/ip",  # Simple connectivity test
            "https://google.com",      # Popular site test
            self.athoc_url,            # AtHoc server test
        ]
        
        self.auth_url = f"{self.athoc_url}/AuthServices/Auth/connect/token"
        
        print("="*80)
        print("AtHoc Proxy Connection Test Script")
        print("="*80)
        print(f"AtHoc Server: {self.athoc_url}")
        print(f"Auth Endpoint: {self.auth_url}")
        print()

    def test_basic_connectivity(self):
        """Test basic internet connectivity without proxy"""
        print("🌐 Testing Basic Connectivity (No Proxy)")
        print("-" * 50)
        
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        session.verify = False  # Disable SSL verification for initial test
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        for url in self.test_urls:
            try:
                start_time = time.time()
                response = session.get(url, timeout=10)
                duration = time.time() - start_time
                
                print(f"✅ {url}")
                print(f"   Status: {response.status_code}")
                print(f"   Time: {duration:.2f}s")
                
                if "httpbin.org" in url:
                    try:
                        data = response.json()
                        print(f"   Your IP: {data.get('origin', 'Unknown')}")
                    except:
                        pass
                        
            except requests.exceptions.ConnectTimeout:
                print(f"❌ {url} - Connection Timeout")
            except requests.exceptions.ConnectionError as e:
                print(f"❌ {url} - Connection Error: {e}")
            except requests.exceptions.SSLError as e:
                print(f"⚠️  {url} - SSL Error: {e}")
            except Exception as e:
                print(f"❌ {url} - Error: {e}")
        print()

    def test_proxy_connectivity(self, proxy_config):
        """Test connectivity through proxy"""
        proxy_name = proxy_config.get('name', 'Unknown Proxy')
        proxies = proxy_config.get('proxies', {})
        
        print(f"🔗 Testing Proxy Connectivity: {proxy_name}")
        print("-" * 50)
        print(f"Proxy Config: {proxies}")
        
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        session.proxies.update(proxies)
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        for url in self.test_urls:
            try:
                start_time = time.time()
                response = session.get(url, timeout=30)
                duration = time.time() - start_time
                
                print(f"✅ {url}")
                print(f"   Status: {response.status_code}")
                print(f"   Time: {duration:.2f}s")
                
                if "httpbin.org" in url:
                    try:
                        data = response.json()
                        print(f"   Your IP: {data.get('origin', 'Unknown')}")
                    except:
                        pass
                        
            except requests.exceptions.ProxyError as e:
                print(f"❌ {url} - Proxy Error: {e}")
            except requests.exceptions.ConnectTimeout:
                print(f"❌ {url} - Connection Timeout (through proxy)")
            except requests.exceptions.ConnectionError as e:
                print(f"❌ {url} - Connection Error: {e}")
            except requests.exceptions.SSLError as e:
                print(f"⚠️  {url} - SSL Error: {e}")
            except Exception as e:
                print(f"❌ {url} - Error: {e}")
        print()

    def test_athoc_authentication(self, proxy_config=None):
        """Test AtHoc authentication specifically"""
        proxy_name = proxy_config.get('name', 'Direct Connection') if proxy_config else 'Direct Connection'
        
        print(f"🔐 Testing AtHoc Authentication: {proxy_name}")
        print("-" * 50)
        
        if not all([self.client_id, self.client_secret, self.username, self.password, self.org_code]):
            print("❌ Missing AtHoc credentials in environment variables")
            print("   Required: CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, ORG_CODE")
            return
        
        session = requests.Session()
        adapter = TLS12HttpAdapter()
        session.mount('https://', adapter)
        
        if proxy_config:
            session.proxies.update(proxy_config.get('proxies', {}))
            
        # Test both with and without SSL verification
        for ssl_verify in [False, True]:
            ssl_status = "SSL Verification ON" if ssl_verify else "SSL Verification OFF"
            print(f"\n  {ssl_status}:")
            
            session.verify = ssl_verify
            if not ssl_verify:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            auth_data = {
                "grant_type": "password",
                "scope": os.getenv("SCOPE", "athoc.iws.web.api"),
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password,
                "acr_values": f"tenant:{self.org_code}"
            }
            
            try:
                start_time = time.time()
                response = session.post(self.auth_url, data=auth_data, timeout=30)
                duration = time.time() - start_time
                
                print(f"    Status: {response.status_code}")
                print(f"    Time: {duration:.2f}s")
                
                if response.status_code == 200:
                    try:
                        token_data = response.json()
                        if 'access_token' in token_data:
                            print("    ✅ Authentication Successful!")
                            print(f"    Token Type: {token_data.get('token_type', 'Unknown')}")
                            print(f"    Expires In: {token_data.get('expires_in', 'Unknown')} seconds")
                        else:
                            print("    ⚠️  Response missing access_token")
                            print(f"    Response: {response.text[:200]}...")
                    except json.JSONDecodeError:
                        print("    ⚠️  Invalid JSON response")
                        print(f"    Response: {response.text[:200]}...")
                else:
                    print(f"    ❌ Authentication Failed")
                    print(f"    Response: {response.text[:200]}...")
                    
            except requests.exceptions.ProxyError as e:
                print(f"    ❌ Proxy Error: {e}")
            except requests.exceptions.ConnectTimeout:
                print(f"    ❌ Connection Timeout")
            except requests.exceptions.ConnectionError as e:
                print(f"    ❌ Connection Error: {e}")
            except requests.exceptions.SSLError as e:
                print(f"    ❌ SSL Error: {e}")
            except Exception as e:
                print(f"    ❌ Error: {e}")
        print()

    def test_system_proxy(self):
        """Test system-configured proxy settings"""
        print("🖥️  Testing System Proxy Settings")
        print("-" * 50)
        
        # Check environment variables
        env_proxies = {}
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
            value = os.getenv(var)
            if value:
                env_proxies[var] = value
                
        if env_proxies:
            print("Environment proxy variables found:")
            for key, value in env_proxies.items():
                # Mask passwords in output
                safe_value = value
                if '@' in value:
                    parts = value.split('@')
                    if len(parts) == 2:
                        auth_part = parts[0]
                        if ':' in auth_part:
                            user, _ = auth_part.split(':', 1)
                            safe_value = f"{user}:***@{parts[1]}"
                print(f"  {key}={safe_value}")
            
            # Test with system proxy
            proxy_config = {
                'name': 'System Environment Proxy',
                'proxies': {
                    'http': os.getenv('HTTP_PROXY') or os.getenv('http_proxy'),
                    'https': os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
                }
            }
            # Remove None values
            proxy_config['proxies'] = {k: v for k, v in proxy_config['proxies'].items() if v}
            
            if proxy_config['proxies']:
                self.test_proxy_connectivity(proxy_config)
                self.test_athoc_authentication(proxy_config)
        else:
            print("No system proxy environment variables found")
            print("Checked: HTTP_PROXY, HTTPS_PROXY, http_proxy, https_proxy")
        print()

    def run_all_tests(self):
        """Run comprehensive connectivity tests"""
        
        # Test 1: Basic connectivity
        self.test_basic_connectivity()
        
        # Test 2: System proxy (if configured)
        self.test_system_proxy()
        
        # Test 3: Manual proxy configurations
        manual_proxies = self.get_manual_proxy_configs()
        for proxy_config in manual_proxies:
            self.test_proxy_connectivity(proxy_config)
            self.test_athoc_authentication(proxy_config)
        
        # Test 4: Direct AtHoc authentication
        self.test_athoc_authentication()
        
        print("="*80)
        print("Test Summary Complete")
        print("="*80)
        print("If all tests fail, check:")
        print("1. Firewall blocking outbound HTTPS traffic")
        print("2. Corporate proxy configuration required")
        print("3. DNS resolution issues")
        print("4. AtHoc server URL correctness")
        print("5. Network security appliances blocking traffic")

    def get_manual_proxy_configs(self):
        """Return list of common proxy configurations to test"""
        configs = []
        
        # Add common corporate proxy ports
        common_hosts = [
            "proxy.company.com",
            "proxy.internal",
            "proxy.local",
            "gateway.company.com"
        ]
        
        common_ports = [8080, 3128, 80, 8888, 9090]
        
        # You can add specific proxy configurations here
        # Example configurations (uncomment and modify as needed):
        
        # configs.append({
        #     'name': 'Corporate Proxy (Example)',
        #     'proxies': {
        #         'http': 'http://proxy.company.com:8080',
        #         'https': 'http://proxy.company.com:8080'
        #     }
        # })
        
        # configs.append({
        #     'name': 'Authenticated Proxy (Example)',
        #     'proxies': {
        #         'http': 'http://username:password@proxy.company.com:8080',
        #         'https': 'http://username:password@proxy.company.com:8080'
        #     }
        # })
        
        return configs

    def interactive_proxy_test(self):
        """Interactive mode for manual proxy testing"""
        print("🔧 Interactive Proxy Configuration Test")
        print("-" * 50)
        
        while True:
            print("\nOptions:")
            print("1. Test direct connection")
            print("2. Test manual proxy configuration")
            print("3. Test AtHoc authentication only")
            print("4. Run all automated tests")
            print("5. Exit")
            
            choice = input("\nEnter choice (1-5): ").strip()
            
            if choice == '1':
                self.test_basic_connectivity()
                
            elif choice == '2':
                proxy_url = input("Enter proxy URL (e.g., http://proxy.company.com:8080): ").strip()
                if proxy_url:
                    proxy_config = {
                        'name': 'Manual Proxy',
                        'proxies': {
                            'http': proxy_url,
                            'https': proxy_url
                        }
                    }
                    self.test_proxy_connectivity(proxy_config)
                    self.test_athoc_authentication(proxy_config)
                    
            elif choice == '3':
                proxy_choice = input("Use proxy? (y/n): ").strip().lower()
                if proxy_choice == 'y':
                    proxy_url = input("Enter proxy URL: ").strip()
                    proxy_config = {
                        'name': 'Manual Proxy',
                        'proxies': {
                            'http': proxy_url,
                            'https': proxy_url
                        }
                    }
                    self.test_athoc_authentication(proxy_config)
                else:
                    self.test_athoc_authentication()
                    
            elif choice == '4':
                self.run_all_tests()
                
            elif choice == '5':
                break
                
            else:
                print("Invalid choice, please try again.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        tester = ProxyTester()
        tester.interactive_proxy_test()
    else:
        tester = ProxyTester()
        tester.run_all_tests()

if __name__ == "__main__":
    main() 