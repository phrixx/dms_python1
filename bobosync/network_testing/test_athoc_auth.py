#!/usr/bin/env python3
"""
Quick AtHoc Authentication Test Script
Logs all actions and responses for debugging
"""
import os
import requests
from pathlib import Path
from datetime import datetime

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
    print(f"[{datetime.now()}] Loaded .env from {env_path}")
except Exception as e:
    print(f"[{datetime.now()}] WARNING: Could not load .env: {e}")

def log(msg):
    print(f"[{datetime.now()}] {msg}")

def main():
    log("Starting AtHoc authentication test...")
    base_url = os.getenv("ATHOC_SERVER_URL")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    username = os.getenv("APIUSER")
    password = os.getenv("PASSWORD")
    org_code = os.getenv("ORG_CODE")
    scope = os.getenv("SCOPE", "athoc.iws.web.api")
    disable_ssl = os.getenv("DISABLE_SSL_VERIFY", "false").lower() == "true"

    if not all([base_url, client_id, client_secret, username, password, org_code]):
        log("ERROR: Missing one or more required environment variables.")
        return

    token_url = f"{base_url}/AuthServices/Auth/connect/token"
    data = {
        "grant_type": "password",
        "scope": scope,
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password,
        "acr_values": f"tenant:{org_code}"
    }
    log(f"POST {token_url}")
    log(f"Payload: {data}")
    log(f"SSL Verification: {'DISABLED' if disable_ssl else 'ENABLED'}")

    try:
        response = requests.post(token_url, data=data, timeout=30, verify=not disable_ssl)
        log(f"Response status: {response.status_code}")
        log(f"Response headers: {response.headers}")
        try:
            resp_json = response.json()
            log(f"Response JSON: {resp_json}")
            if 'access_token' in resp_json:
                log("✅ Authentication SUCCESSFUL!")
            else:
                log("❌ Authentication FAILED: No access_token in response.")
        except Exception as e:
            log(f"❌ Failed to parse JSON: {e}")
            log(f"Raw response: {response.text}")
    except Exception as e:
        log(f"❌ Exception during request: {e}")

if __name__ == "__main__":
    main() 