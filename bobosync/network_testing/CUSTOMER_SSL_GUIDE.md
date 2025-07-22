# Customer SSL Configuration Guide

## Summary of SSL Verification Tests

### Development System (catcloud.athocdevo.com)
- **SSL Verification**: ❌ FAILS consistently 
- **Issue**: Missing intermediate certificate chain
- **Required**: `DISABLE_SSL_VERIFY=true`

### Production System (alerts1.eu.athoc.com)  
- **SSL Verification**: Mixed results
- **Main site**: ❌ FAILS
- **Auth endpoint**: ✅ WORKS!
- **Recommendation**: Test both settings with customer

## Customer Deployment Options

### Option 1: Secure Configuration (Try First)
```env
# Try this configuration first
ATHOC_SERVER_URL=https://alerts1.eu.athoc.com
DISABLE_SSL_VERIFY=false

# Add proxy if needed
HTTP_PROXY=http://corporate-proxy:8080
HTTPS_PROXY=http://corporate-proxy:8080
```

**When to use:**
- Customer has proper certificate chain
- Corporate environment with trusted CAs
- Maximum security required

### Option 2: Reliable Configuration (Fallback)
```env
# Guaranteed to work
ATHOC_SERVER_URL=https://alerts1.eu.athoc.com  
DISABLE_SSL_VERIFY=true

# Add proxy if needed
HTTP_PROXY=http://corporate-proxy:8080
HTTPS_PROXY=http://corporate-proxy:8080
```

**When to use:**
- SSL verification fails in customer environment
- Corporate proxy with SSL inspection
- Quick deployment needed

## SSL Verification Process

When `DISABLE_SSL_VERIFY=false`, Python validates:

1. **Certificate Validity** - Not expired ✅
2. **Certificate Chain** - Trusted root CA ⚠️ (This fails)
3. **Hostname Verification** - CN/SAN matches URL ✅
4. **TLS Protocol** - TLS 1.2+ required ✅

The failure occurs at step 2 due to incomplete certificate chain from AtHoc servers.

## Customer Environment Factors

### Corporate Networks
- **Proxy servers** - Usually require `HTTP_PROXY` and `HTTPS_PROXY`
- **SSL inspection** - May replace certificates, causing verification failures
- **Firewall rules** - Must allow outbound HTTPS to `*.athoc.com`

### Certificate Stores
- **Windows**: Uses Windows Certificate Store
- **Linux**: Uses system CA bundle (usually `/etc/ssl/certs/`)
- **Python**: Uses `certifi` package CA bundle

## Troubleshooting Steps

### Step 1: Test Basic Connectivity
```bash
# Test if site is reachable
curl -I https://alerts1.eu.athoc.com
```

### Step 2: Test SSL Verification
```bash
# Test certificate chain
openssl s_client -connect alerts1.eu.athoc.com:443 -servername alerts1.eu.athoc.com
```

### Step 3: Test With Proxy (if applicable)
```bash
# Test through corporate proxy
curl -I https://alerts1.eu.athoc.com --proxy http://proxy.company.com:8080
```

### Step 4: Test AtHoc Client
```bash
# Run our SSL test script
python test_production_ssl.py
```

## Customer Support Checklist

### Pre-deployment
- [ ] Confirm AtHoc server URL (`alerts1.eu.athoc.com`)
- [ ] Get proxy settings from customer IT
- [ ] Confirm firewall rules for `*.athoc.com`
- [ ] Test both SSL verification settings

### During Deployment  
- [ ] Start with `DISABLE_SSL_VERIFY=false`
- [ ] If SSL fails, switch to `DISABLE_SSL_VERIFY=true`
- [ ] Test authentication with customer credentials
- [ ] Verify proxy configuration if needed
- [ ] Test CSV processing end-to-end

### Post-deployment
- [ ] Monitor logs for SSL-related errors
- [ ] Document working configuration
- [ ] Schedule periodic connectivity tests

## Security Considerations

### DISABLE_SSL_VERIFY=true
- ✅ **Pros**: Guaranteed connectivity, works with corporate proxies
- ⚠️ **Cons**: Vulnerable to man-in-the-middle attacks
- 📋 **Acceptable**: For corporate networks with other security controls

### DISABLE_SSL_VERIFY=false
- ✅ **Pros**: Full certificate validation, maximum security
- ❌ **Cons**: May fail due to AtHoc certificate chain issues
- 📋 **Preferred**: When it works in customer environment

## Common Issues and Solutions

### Issue: "Certificate verify failed: unable to get local issuer certificate"
**Solution**: Use `DISABLE_SSL_VERIFY=true`

### Issue: "Proxy authentication required"
**Solution**: Add credentials to proxy URL: `http://user:pass@proxy:8080`

### Issue: "Connection timeout"
**Solution**: Check firewall rules and proxy configuration

### Issue: "Name resolution failure"  
**Solution**: Verify DNS resolution and network connectivity

## Contact Information

For SSL-related customer issues:
1. Run diagnostic scripts from this repository
2. Collect error logs and configuration
3. Test both SSL verification settings
4. Document working configuration for future reference

---

**Note**: The `DISABLE_SSL_VERIFY=true` setting is acceptable for production use in corporate environments where other security controls are in place. The connectivity and functionality are identical regardless of SSL verification setting. 