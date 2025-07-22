#!/usr/bin/env python3
"""
SSL Verification Fix Guide
Provides multiple solutions for enabling SSL verification with AtHoc
"""

import os
import ssl
import requests
import tempfile
from pathlib import Path
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except:
    pass

class FixedTLS12HttpAdapter(HTTPAdapter):
    """Fixed version of TLS12HttpAdapter with proper SSL configuration"""
    def __init__(self, disable_ssl_verify=False, cert_path=None, *args, **kwargs):
        self.disable_ssl_verify = disable_ssl_verify
        self.cert_path = cert_path
        
        # Create SSL context
        self.ssl_context = create_urllib3_context(
            ssl_minimum_version=ssl.TLSVersion.TLSv1_2
        )
        
        if disable_ssl_verify:
            # Properly disable SSL verification
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        elif cert_path and os.path.exists(cert_path):
            # Use custom certificate bundle
            self.ssl_context.load_verify_locations(cafile=cert_path)
            
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)

def download_certificate_chain(hostname, port=443):
    """Download the certificate chain for a hostname"""
    print(f"📥 Downloading certificate chain for {hostname}...")
    
    try:
        import subprocess
        result = subprocess.run([
            'openssl', 's_client', 
            '-connect', f'{hostname}:{port}',
            '-servername', hostname,
            '-showcerts'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Extract certificates from output
            certs = []
            lines = result.stdout.split('\n')
            in_cert = False
            current_cert = []
            
            for line in lines:
                if '-----BEGIN CERTIFICATE-----' in line:
                    in_cert = True
                    current_cert = [line]
                elif '-----END CERTIFICATE-----' in line and in_cert:
                    current_cert.append(line)
                    certs.append('\n'.join(current_cert))
                    current_cert = []
                    in_cert = False
                elif in_cert:
                    current_cert.append(line)
            
            return certs
        else:
            print(f"❌ Failed to download certificates: {result.stderr}")
            return []
            
    except Exception as e:
        print(f"❌ Error downloading certificates: {e}")
        return []

def create_certificate_bundle(hostname, output_path):
    """Create a certificate bundle with system CAs + server certs"""
    print(f"🔧 Creating certificate bundle for {hostname}...")
    
    try:
        # Get system CA bundle
        import certifi
        system_ca_path = certifi.where()
        
        # Download server certificate chain
        server_certs = download_certificate_chain(hostname)
        
        if not server_certs:
            print("❌ Could not download server certificates")
            return False
        
        # Combine system CAs with server certificates
        with open(output_path, 'w') as f:
            # Add system CAs
            with open(system_ca_path, 'r') as ca_file:
                f.write(ca_file.read())
            
            # Add server certificate chain
            f.write('\n# Server certificate chain for {}\n'.format(hostname))
            for i, cert in enumerate(server_certs):
                f.write(f'\n# Certificate {i+1}\n')
                f.write(cert)
                f.write('\n')
        
        print(f"✅ Certificate bundle created: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating certificate bundle: {e}")
        return False

def test_ssl_solutions():
    """Test different SSL verification solutions"""
    print("🧪 Testing SSL Verification Solutions")
    print("=" * 60)
    
    athoc_url = os.getenv("ATHOC_SERVER_URL", "https://catcloud.athocdevo.com")
    hostname = athoc_url.replace('https://', '').split('/')[0]
    
    solutions = []
    
    # Solution 1: Custom certificate bundle
    print("\n1️⃣ Testing: Custom Certificate Bundle")
    cert_bundle_path = Path(__file__).parent / f"{hostname}.pem"
    
    if create_certificate_bundle(hostname, cert_bundle_path):
        try:
            session = requests.Session()
            session.mount('https://', FixedTLS12HttpAdapter(cert_path=str(cert_bundle_path)))
            response = session.get(athoc_url, timeout=10)
            
            print(f"   ✅ Custom certificate bundle works!")
            print(f"   📊 Status: {response.status_code}")
            solutions.append({
                'name': 'Custom Certificate Bundle',
                'method': f'SSL_CERT_PATH={cert_bundle_path}',
                'works': True
            })
            
        except Exception as e:
            print(f"   ❌ Custom certificate bundle failed: {e}")
            solutions.append({
                'name': 'Custom Certificate Bundle',
                'method': f'SSL_CERT_PATH={cert_bundle_path}',
                'works': False,
                'error': str(e)
            })
    
    # Solution 2: Environment variable CA bundle
    print("\n2️⃣ Testing: Environment Variable CA Bundle")
    try:
        os.environ['REQUESTS_CA_BUNDLE'] = str(cert_bundle_path)
        session = requests.Session()
        response = session.get(athoc_url, timeout=10)
        
        print(f"   ✅ Environment CA bundle works!")
        print(f"   📊 Status: {response.status_code}")
        solutions.append({
            'name': 'Environment CA Bundle',
            'method': f'export REQUESTS_CA_BUNDLE={cert_bundle_path}',
            'works': True
        })
        
    except Exception as e:
        print(f"   ❌ Environment CA bundle failed: {e}")
        solutions.append({
            'name': 'Environment CA Bundle',
            'method': f'export REQUESTS_CA_BUNDLE={cert_bundle_path}',
            'works': False,
            'error': str(e)
        })
    finally:
        if 'REQUESTS_CA_BUNDLE' in os.environ:
            del os.environ['REQUESTS_CA_BUNDLE']
    
    # Solution 3: Disabled SSL verification (current working solution)
    print("\n3️⃣ Testing: Disabled SSL Verification (Current)")
    try:
        session = requests.Session()
        session.mount('https://', FixedTLS12HttpAdapter(disable_ssl_verify=True))
        session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = session.get(athoc_url, timeout=10)
        print(f"   ✅ Disabled SSL verification works!")
        print(f"   📊 Status: {response.status_code}")
        solutions.append({
            'name': 'Disabled SSL Verification',
            'method': 'DISABLE_SSL_VERIFY=true',
            'works': True,
            'note': 'Less secure but functional'
        })
        
    except Exception as e:
        print(f"   ❌ Even disabled SSL failed: {e}")
        solutions.append({
            'name': 'Disabled SSL Verification',
            'method': 'DISABLE_SSL_VERIFY=true',
            'works': False,
            'error': str(e)
        })
    
    return solutions

def generate_implementation_guide(solutions):
    """Generate implementation guide based on test results"""
    print(f"\n📋 Implementation Guide")
    print("=" * 60)
    
    working_solutions = [s for s in solutions if s.get('works', False)]
    
    if working_solutions:
        print("✅ Working Solutions (in order of security):")
        for i, solution in enumerate(working_solutions, 1):
            print(f"\n{i}. **{solution['name']}**")
            print(f"   Method: {solution['method']}")
            if 'note' in solution:
                print(f"   Note: {solution['note']}")
    
    print(f"\n🔧 **Recommended Implementation for AtHoc Client:**")
    
    if any(s['name'] == 'Custom Certificate Bundle' and s['works'] for s in solutions):
        print("""
1. Add to .env file:
   SSL_CERT_PATH=./catcloud.athocdevo.com.pem
   DISABLE_SSL_VERIFY=false

2. Modify athoc_client.py _create_session():
   if os.getenv("SSL_CERT_PATH"):
       session.verify = os.getenv("SSL_CERT_PATH")
   elif os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true":
       session.verify = False
""")
    
    else:
        print("""
Current working solution:
   DISABLE_SSL_VERIFY=true

For production deployment:
1. Work with customer IT to get proper certificate chain
2. Or implement custom certificate bundle solution above
3. Test thoroughly in customer environment
""")

def main():
    print("🔐 SSL Verification Fix Guide")
    print("=" * 80)
    
    print("\n📊 Current SSL Configuration:")
    disable_ssl = os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"
    print(f"   DISABLE_SSL_VERIFY: {disable_ssl}")
    print(f"   SSL_CERT_PATH: {os.getenv('SSL_CERT_PATH', 'Not set')}")
    
    # Run tests
    solutions = test_ssl_solutions()
    
    # Generate guide
    generate_implementation_guide(solutions)
    
    print(f"\n" + "=" * 80)
    print("🏁 SSL Fix Guide Complete")
    print("=" * 80)

if __name__ == "__main__":
    main() 