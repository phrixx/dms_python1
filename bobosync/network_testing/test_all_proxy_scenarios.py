#!/usr/bin/env python3
"""
Comprehensive Proxy Testing Script
Tests various proxy scenarios including your own local proxies
"""

import subprocess
import time
import threading
import os
import sys
from test_proxy_connection import ProxyTester

class ProxyTestSuite:
    def __init__(self):
        self.proxy_processes = []
        self.tester = ProxyTester()
        
    def start_simple_proxy(self, port=8888):
        """Start simple proxy server"""
        print(f"🚀 Starting simple proxy on port {port}...")
        cmd = [sys.executable, "simple_proxy_server.py", str(port)]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.proxy_processes.append(('simple', process))
        time.sleep(2)  # Wait for startup
        return f"http://localhost:{port}"
    
    def start_auth_proxy(self, port=8889, username="testuser", password="testpass"):
        """Start authenticated proxy server"""
        print(f"🔐 Starting authenticated proxy on port {port}...")
        cmd = [sys.executable, "auth_proxy_server.py", str(port), username, password]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.proxy_processes.append(('auth', process))
        time.sleep(2)  # Wait for startup
        return f"http://{username}:{password}@localhost:{port}"
    
    def test_proxy_scenarios(self):
        """Test different proxy scenarios"""
        scenarios = []
        
        # Test 1: Simple proxy
        try:
            simple_proxy_url = self.start_simple_proxy(8888)
            scenarios.append({
                'name': 'Local Simple Proxy',
                'proxies': {
                    'http': simple_proxy_url,
                    'https': simple_proxy_url
                }
            })
        except Exception as e:
            print(f"❌ Failed to start simple proxy: {e}")
        
        # Test 2: Authenticated proxy
        try:
            auth_proxy_url = self.start_auth_proxy(8889, "testuser", "testpass")
            scenarios.append({
                'name': 'Local Authenticated Proxy',
                'proxies': {
                    'http': auth_proxy_url,
                    'https': auth_proxy_url
                }
            })
        except Exception as e:
            print(f"❌ Failed to start auth proxy: {e}")
        
        # Test 3: Docker proxies (if available)
        docker_scenarios = self.check_docker_proxies()
        scenarios.extend(docker_scenarios)
        
        # Run tests for each scenario
        for scenario in scenarios:
            print(f"\n{'='*60}")
            print(f"Testing: {scenario['name']}")
            print(f"{'='*60}")
            self.tester.test_proxy_connectivity(scenario)
            self.tester.test_athoc_authentication(scenario)
    
    def check_docker_proxies(self):
        """Check for running Docker proxy containers"""
        scenarios = []
        
        try:
            # Check for Squid containers
            result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}\t{{.Ports}}'], 
                                  capture_output=True, text=True, timeout=5)
            
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if '\t' in line:
                    name, ports = line.split('\t', 1)
                    
                    if 'squid-proxy' in name and '3128' in ports:
                        scenarios.append({
                            'name': 'Docker Squid Proxy (No Auth)',
                            'proxies': {
                                'http': 'http://localhost:3128',
                                'https': 'http://localhost:3128'
                            }
                        })
                    
                    if 'squid-auth-proxy' in name and '3129' in ports:
                        scenarios.append({
                            'name': 'Docker Squid Proxy (With Auth)',
                            'proxies': {
                                'http': 'http://testuser:testpass@localhost:3129',
                                'https': 'http://testuser:testpass@localhost:3129'
                            }
                        })
                        
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("ℹ️  Docker not available or no Docker proxies running")
        
        return scenarios
    
    def cleanup(self):
        """Stop all proxy processes"""
        print("\n🧹 Cleaning up proxy processes...")
        for proxy_type, process in self.proxy_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ Stopped {proxy_type} proxy")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"🔥 Force killed {proxy_type} proxy")
            except Exception as e:
                print(f"⚠️  Error stopping {proxy_type} proxy: {e}")

def main():
    suite = ProxyTestSuite()
    
    try:
        print("🧪 Starting Comprehensive Proxy Test Suite")
        print("="*60)
        
        # First test direct connection
        print("\n📡 Testing Direct Connection (No Proxy)")
        suite.tester.test_basic_connectivity()
        suite.tester.test_athoc_authentication()
        
        # Then test proxy scenarios
        suite.test_proxy_scenarios()
        
        print("\n" + "="*60)
        print("✅ All proxy tests completed!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
    finally:
        suite.cleanup()

if __name__ == "__main__":
    main() 