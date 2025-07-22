# Network Testing Tools

This directory contains comprehensive network testing tools for diagnosing proxy and SSL connectivity issues with AtHoc systems. These tools are essential for customer site deployments where network connectivity issues are common.

## 📁 File Overview

### Core Testing Scripts

| File | Purpose | Usage |
|------|---------|--------|
| `test_proxy_connection.py` | **Main proxy testing tool** | Test various proxy configurations |
| `test_ssl_verification.py` | **SSL verification diagnostics** | Analyze SSL certificate issues |
| `test_production_ssl.py` | **Production system testing** | Test alerts1.eu.athoc.com specifically |
| `debug_proxy_config.py` | **Proxy configuration debug** | Debug current proxy settings |

### Proxy Testing Tools

| File | Purpose | Usage |
|------|---------|--------|
| `simple_proxy_server.py` | **Local proxy server** | Create test proxy for development |
| `test_all_proxy_scenarios.py` | **Comprehensive proxy tests** | Test multiple proxy scenarios |

### SSL Analysis Tools

| File | Purpose | Usage |
|------|---------|--------|
| `ssl_fix_guide.py` | **SSL troubleshooting** | Generate SSL solutions |

### Documentation

| File | Purpose | Usage |
|------|---------|--------|
| `CUSTOMER_SSL_GUIDE.md` | **Customer deployment guide** | Reference for customer support |

## 🚀 Quick Start

### 1. Test Current Configuration
```bash
cd network_testing
python debug_proxy_config.py
```

### 2. Test Production AtHoc System
```bash
python test_production_ssl.py
```

### 3. Test Proxy Connectivity
```bash
python test_proxy_connection.py
```

### 4. Start Local Proxy Server (for testing)
```bash
python simple_proxy_server.py 8889
```

## 🔧 Common Use Cases

### Customer Site Deployment
1. **Pre-deployment testing**:
   ```bash
   python test_production_ssl.py
   ```

2. **Proxy configuration**:
   ```bash
   python debug_proxy_config.py
   python test_proxy_connection.py --interactive
   ```

3. **SSL troubleshooting**:
   ```bash
   python test_ssl_verification.py
   python ssl_fix_guide.py
   ```

### Development Testing
1. **Setup local proxy**:
   ```bash
   python simple_proxy_server.py 8889
   ```

2. **Test all scenarios**:
   ```bash
   python test_all_proxy_scenarios.py
   ```

## 📋 Environment Configuration

### Required Environment Variables
Set these in your `.env` file:

```env
# AtHoc Server Configuration
ATHOC_SERVER_URL=https://alerts1.eu.athoc.com
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
USERNAME=your-username
PASSWORD=your-password
ORG_CODE=your-org-code

# Proxy Configuration (if needed)
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080

# SSL Configuration
DISABLE_SSL_VERIFY=true  # or false for secure mode
```

### Optional Settings
```env
# SSL Certificate Path (if using custom certificates)
SSL_CERT_PATH=./custom-cert-bundle.pem

# Proxy Authentication (if required)
HTTP_PROXY=http://username:password@proxy.company.com:8080
HTTPS_PROXY=http://username:password@proxy.company.com:8080
```

## 🐛 Troubleshooting Workflow

### Step 1: Basic Connectivity
```bash
python debug_proxy_config.py
```
Checks current environment and configuration.

### Step 2: SSL Verification
```bash
python test_ssl_verification.py
```
Diagnoses SSL certificate issues.

### Step 3: Production Testing
```bash
python test_production_ssl.py
```
Tests actual customer production system.

### Step 4: Proxy Testing
```bash
python test_proxy_connection.py
```
Tests proxy connectivity scenarios.

### Step 5: Comprehensive Analysis
```bash
python ssl_fix_guide.py
```
Generates specific solutions for SSL issues.

## 🌐 Customer Support

### Pre-deployment Checklist
- [ ] Run `test_production_ssl.py`
- [ ] Verify proxy requirements with customer IT
- [ ] Test both `DISABLE_SSL_VERIFY=true` and `false`
- [ ] Document working configuration

### Common Customer Issues

#### "Certificate verify failed"
**Solution**: Use `DISABLE_SSL_VERIFY=true`
**Test with**: `python test_ssl_verification.py`

#### "Connection timeout"
**Solution**: Check proxy and firewall settings
**Test with**: `python test_proxy_connection.py`

#### "Proxy authentication required"
**Solution**: Add credentials to proxy URL
**Test with**: `python debug_proxy_config.py`

## 📚 Documentation References

- **Customer Deployment**: See `CUSTOMER_SSL_GUIDE.md`
- **Main Project**: See `../README.md`
- **Process Guide**: See `../process.md`

## 🔍 Advanced Testing

### Interactive Proxy Testing
```bash
python test_proxy_connection.py --interactive
```

### Custom Certificate Testing
```bash
python ssl_fix_guide.py
```

### All Proxy Scenarios
```bash
python test_all_proxy_scenarios.py
```

---

**Note**: These tools are designed for customer site deployment scenarios where network connectivity issues are common. They provide comprehensive diagnostics and testing capabilities for both proxy and SSL configurations. 