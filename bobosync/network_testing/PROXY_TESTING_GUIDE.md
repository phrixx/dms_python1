# Proxy Testing Guide

## Quick Start

### 1. Run Automated Tests
```bash
cd bobosync
python test_proxy_connection.py
```

### 2. Run Interactive Tests
```bash
python test_proxy_connection.py --interactive
```

## Configuration Options

### Environment Variables
Add these to your `.env` file or set as system environment variables:

```env
# System proxy settings
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080

# With authentication
HTTP_PROXY=http://username:password@proxy.company.com:8080
HTTPS_PROXY=http://username:password@proxy.company.com:8080

# No proxy for certain hosts
NO_PROXY=localhost,127.0.0.1,.local
```

### Manual Proxy Testing
Edit the `get_manual_proxy_configs()` function in the test script to add specific proxy configurations for testing.

## Common Corporate Proxy Scenarios

### Scenario 1: Basic HTTP Proxy
```
Proxy: proxy.company.com:8080
Authentication: None
```

### Scenario 2: Authenticated Proxy
```
Proxy: proxy.company.com:8080
Username: domain\username
Password: password
```

### Scenario 3: NTLM Authentication
```
Proxy: proxy.company.com:8080
Authentication: NTLM (may require additional setup)
```

### Scenario 4: PAC File Configuration
```
Proxy: Automatic configuration script
URL: http://proxy.company.com/proxy.pac
```

## Troubleshooting

### Test Results Interpretation

✅ **Success**: Connection works properly
❌ **Failure**: Connection blocked or failed
⚠️  **Warning**: Partial success or SSL issues

### Common Issues

1. **All Direct Connections Fail**
   - Corporate firewall blocking outbound traffic
   - Need to use corporate proxy

2. **Proxy Authentication Fails**
   - Wrong username/password
   - Domain authentication required
   - NTLM/Kerberos authentication needed

3. **SSL/TLS Errors**
   - Corporate SSL inspection
   - Self-signed certificates
   - TLS version mismatch

4. **AtHoc Authentication Fails**
   - Server URL incorrect
   - Credentials invalid
   - Organization code wrong

## Customer Site Deployment

### Information to Gather
1. **Proxy Settings**
   - Proxy server address and port
   - Authentication requirements
   - PAC file URL (if used)

2. **Network Configuration**
   - Firewall rules needed
   - DNS servers
   - SSL certificate requirements

3. **Security Requirements**
   - SSL inspection policies
   - Certificate validation
   - Allowed TLS versions

### Testing at Customer Site
1. Run the automated test first
2. Try interactive mode for specific configurations
3. Work with customer IT to identify proxy settings
4. Test both SSL verification on/off
5. Document working configuration

## Usage Instructions

### For Customer Sites:

1. **Copy the test script** to the customer's system in the `bobosync` directory

2. **Run automated tests**:
   ```bash
   python test_proxy_connection.py
   ```

3. **If automated tests fail**, run interactive mode:
   ```bash
   python test_proxy_connection.py --interactive
   ```

4. **Work with customer IT** to:
   - Get proxy server details
   - Test different configurations
   - Identify firewall requirements

5. **Once working configuration is found**, update the actual `athoc_client.py` with the proxy settings

### Key Features:

- ✅ **Tests basic connectivity** without proxy
- ✅ **Tests system proxy** environment variables  
- ✅ **Tests manual proxy** configurations
- ✅ **Tests AtHoc authentication** specifically
- ✅ **Tests both SSL verification** on/off
- ✅ **Interactive mode** for real-time testing
- ✅ **Detailed error reporting** for troubleshooting
- ✅ **Safe credential handling** (masks passwords in output)

This will help you quickly identify whether the customer site needs proxy configuration and what the correct settings should be. 