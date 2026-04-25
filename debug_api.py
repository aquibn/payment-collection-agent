#!/usr/bin/env python3
"""
debug_api.py — Run this FIRST to diagnose the external API issue.

Usage:
    python debug_api.py

It tries every plausible URL combination and tells you exactly which one works.
"""

import requests
import json

HOST = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com"

CANDIDATES = [
    f"{HOST}/api/lookup-account",            # Most likely correct
    f"{HOST}/openapi/api/lookup-account",    # What we were using (probably wrong)
    f"{HOST}/openapi/lookup-account",        # openapi as base, no /api/
    f"{HOST}/v1/api/lookup-account",         # versioned
    f"{HOST}/lookup-account",               # flat
]

PAYLOAD = {"account_id": "ACC1001"}
HEADERS = {"Content-Type": "application/json"}

print("=" * 60)
print("  PayAgent — External API Diagnostics")
print("=" * 60)
print(f"\nHost: {HOST}")
print(f"Payload: {PAYLOAD}\n")

working = None
for url in CANDIDATES:
    try:
        resp = requests.post(url, json=PAYLOAD, headers=HEADERS, timeout=8)
        status = resp.status_code
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:100]

        marker = "✅ WORKS" if status == 200 else f"❌ HTTP {status}"
        print(f"{marker}  →  {url}")
        if status not in (404, 405):
            print(f"   Response: {json.dumps(body)[:120]}")
        if status == 200 and working is None:
            working = url
    except requests.exceptions.ConnectionError:
        print(f"⚠️  CONN ERR  →  {url}")
    except requests.exceptions.Timeout:
        print(f"⏱  TIMEOUT   →  {url}")
    except Exception as e:
        print(f"💥  ERROR     →  {url}  ({e})")

print()
if working:
    # Extract the base URL (strip /lookup-account)
    base = working.replace("/lookup-account", "")
    print(f"✅ CORRECT BASE_URL = \"{base}\"")
    print(f"\nAction: Update api_client.py line 12:")
    print(f'  BASE_URL = "{base}"')
else:
    print("❌ No working endpoint found.")
    print("\nPossible causes:")
    print("  1. External API is down — run with MOCK_API=1:")
    print("     MOCK_API=1 python app.py")
    print("  2. VPN/firewall blocking access from your network")
    print("  3. The API requires authentication headers (check the spec)")
print()
