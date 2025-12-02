# Secure Configuration Encryption Guide

## Overview

The BOBO processor now automatically encrypts sensitive fields (`PASSWORD` and `CLIENT_SECRET`) in your `.env` file after the first run. This provides an additional layer of security for storing credentials.

### Security Architecture

**Key Separation for Enhanced Security:**
- **`.env` file**: Stored in project directory (`bobosync/.env`) with encrypted values
- **Encryption key**: Stored in user's home directory (`~/.bobo_encryption_key`) 

This separation means:
- ✅ Even if someone gains access to your `.env` file, they cannot decrypt it without the key file
- ✅ The key file is stored separately in your home directory, providing better isolation
- ✅ On multi-user systems, each user has their own key file
- ✅ The key file is never in the same directory as the encrypted data

## How It Works

### First Run
1. You create `.env` file with plaintext `PASSWORD` and `CLIENT_SECRET`
2. When the application starts, it automatically:
   - Loads the `.env` file
   - Decrypts any encrypted values (if present)
   - **Encrypts plaintext sensitive fields** and saves them back to `.env`
   - Creates a `.key` file for decryption

### Subsequent Runs
1. Application loads `.env` file
2. Detects encrypted values (prefixed with `ENCRYPTED:`)
3. Automatically decrypts them using the `.key` file
4. Uses decrypted values in memory (never stored in plaintext)

## Example

### Before First Run (.env file):
```env
PASSWORD=mysecretpassword123
CLIENT_SECRET=abc123xyz789
```

### After First Run (.env file):
```env
PASSWORD=ENCRYPTED:gAAAAABh...
CLIENT_SECRET=ENCRYPTED:gAAAAABh...
```

The values are automatically decrypted when the application runs.

## Security Notes

### Important Files

1. **`.env` file**: Contains encrypted credentials
   - Stored in the project directory (`bobosync/.env`)
   - Can be backed up (encrypted values are safe)
   - Can be version controlled if desired (though not recommended)

2. **`.bobo_encryption_key` file**: Encryption key (CRITICAL)
   - **NEVER commit this to version control**
   - **Keep secure backups** - if lost, encrypted values cannot be recovered
   - Automatically created on first run
   - **Stored in user's home directory** (`~/.bobo_encryption_key`) for better security separation
   - This separation means even if someone has access to your `.env` file, they cannot decrypt it without the key file

### Best Practices

1. **Backup the `.bobo_encryption_key` file** separately from your code repository
2. **Set restrictive permissions** on both `.env` and key files:
   - Unix/Mac: `chmod 600 ~/.bobo_encryption_key` and `chmod 600 bobosync/.env`
   - Windows: Use file properties to restrict access
3. **Never share the key file** publicly or via insecure channels
4. **Rotate credentials** if key file is compromised
5. **Key file location**: The key is stored in your home directory (`~/.bobo_encryption_key`) for better security separation from the `.env` file
6. **Multi-user systems**: Each user will have their own key file, providing additional isolation

## Troubleshooting

### "Decryption failed" Error

If you see a decryption error:
- Ensure the `.bobo_encryption_key` file exists in your home directory (`~/.bobo_encryption_key`)
- Check that the key file hasn't been corrupted or modified
- Verify you're running as the same user who created the key file
- If the key is lost, you'll need to:
  1. Delete encrypted values from `.env`
  2. Re-enter plaintext values
  3. Let the system re-encrypt them (will create a new key)

### Re-encrypting After Manual Edit

If you need to change a password or client secret:

**Method 1: Replace encrypted value with plaintext**
1. Open `.env` file
2. Find the encrypted line (e.g., `PASSWORD=ENCRYPTED:gAAAAABh...`)
3. Replace it with plaintext: `PASSWORD=yournewpassword123`
4. Save the file
5. **On next application run, it will automatically detect the plaintext value and encrypt it**

**Method 2: The system automatically detects plaintext**
- The system checks every time it starts if sensitive fields (`PASSWORD`, `CLIENT_SECRET`) are encrypted
- If a sensitive field has a value that **doesn't start with `ENCRYPTED:`**, it will automatically encrypt it
- This means you can simply replace the encrypted value with plaintext, and the next run will handle encryption

**How it works:**
- On startup, the system calls `encrypt_sensitive_fields()` with `auto_encrypt=True`
- It checks each sensitive field: if the value exists and doesn't start with `ENCRYPTED:`, it encrypts it
- You'll see a message: `✓ Encrypted X sensitive field(s) in .env`

### Cross-Platform Compatibility

- ✅ **Works on Windows, Mac, and Linux**
- ✅ **Home Directory Paths**:
  - **Windows**: `C:\Users\YourUsername\.bobo_encryption_key`
  - **Mac**: `/Users/yourusername/.bobo_encryption_key`
  - **Linux**: `/home/yourusername/.bobo_encryption_key`
- ✅ File permissions are set automatically on Unix/Mac
- ✅ Windows handles permissions differently (no chmod needed)
- ✅ `Path.home()` automatically detects the correct home directory on all platforms

## Manual Encryption (Optional)

If you want to manually encrypt values:

```python
from secure_env import SecureEnvConfig

config = SecureEnvConfig()
config.encrypt_sensitive_fields()  # Encrypts PASSWORD and CLIENT_SECRET
```

## Disabling Encryption

If you need to disable encryption temporarily:
1. Remove the `cryptography` package: `pip uninstall cryptography`
2. The system will fall back to standard `.env` loading
3. You'll see a warning message but the application will still work

## Technical Details

- **Encryption Algorithm**: Fernet (symmetric encryption)
- **Key Derivation**: Uses Fernet's built-in key generation
- **Encrypted Fields**: `PASSWORD`, `CLIENT_SECRET` (configurable in `secure_env.py`)
- **Format**: Encrypted values prefixed with `ENCRYPTED:` followed by base64-encoded ciphertext

