"""
Deep diagnostic: tests each Twitter credential with raw HTTP output.
"""
import os
import sys
import json
import hmac
import hashlib
import time
import random
import string
import urllib.parse
import base64
import requests

BEARER_TOKEN        = os.environ.get("TWITTER_BEARER_TOKEN", "")
CONSUMER_KEY        = os.environ.get("TWITTER_API_KEY", "")       # mapped from TWITTER_CONSUMER_KEY
CONSUMER_SECRET     = os.environ.get("TWITTER_API_SECRET", "")    # mapped from TWITTER_CONSUMER_SECRET
ACCESS_TOKEN        = os.environ.get("TWITTER_ACCESS_TOKEN", "")
ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

print("=" * 60)
print("DEEP CREDENTIAL DIAGNOSTIC")
print("=" * 60)

# ── 1. Show key lengths (never show actual values) ────────────────────────────
print("\n[1] Key lengths (0 = empty / not set):")
print(f"  TWITTER_BEARER_TOKEN        : {len(BEARER_TOKEN)} chars")
print(f"  TWITTER_CONSUMER_KEY        : {len(CONSUMER_KEY)} chars")
print(f"  TWITTER_CONSUMER_SECRET     : {len(CONSUMER_SECRET)} chars")
print(f"  TWITTER_ACCESS_TOKEN        : {len(ACCESS_TOKEN)} chars")
print(f"  TWITTER_ACCESS_TOKEN_SECRET : {len(ACCESS_TOKEN_SECRET)} chars")

# ── 2. Bearer Token test ──────────────────────────────────────────────────────
print("\n[2] Bearer Token test (GET /2/tweets/search/recent):")
try:
    r = requests.get(
        "https://api.twitter.com/2/tweets/search/recent",
        headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
        params={"query": "hello", "max_results": 10},
        timeout=10,
    )
    print(f"  HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"  Body: {r.text[:300]}")
    else:
        print("  ✅ Bearer Token works!")
except Exception as e:
    print(f"  Exception: {e}")

# ── 3. OAuth 1.0a signature test ──────────────────────────────────────────────
print("\n[3] OAuth 1.0a test (GET /2/users/me):")

def make_oauth_header(method, url, params, ck, cs, at, ats):
    nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    ts = str(int(time.time()))
    oauth_params = {
        "oauth_consumer_key": ck,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": ts,
        "oauth_token": at,
        "oauth_version": "1.0",
    }
    all_params = {**params, **oauth_params}
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])
    signing_key = f"{urllib.parse.quote(cs, safe='')}&{urllib.parse.quote(ats, safe='')}"
    sig = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = sig
    header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return header

try:
    url = "https://api.twitter.com/2/users/me"
    auth_header = make_oauth_header(
        "GET", url, {},
        CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
    )
    r = requests.get(url, headers={"Authorization": auth_header}, timeout=10)
    print(f"  HTTP {r.status_code}")
    body = r.json()
    print(f"  Body: {json.dumps(body, indent=2)[:400]}")
    if r.status_code == 200:
        print(f"  ✅ OAuth 1.0a works! User: @{body['data']['username']}")
    elif r.status_code == 401:
        errors = body.get("errors", body.get("detail", ""))
        print(f"  ❌ 401 — {errors}")
        print("  → Consumer Key/Secret or Access Token/Secret is wrong")
    elif r.status_code == 403:
        print("  ❌ 403 — App permissions are 'Read only'")
        print("  → Set to 'Read and Write' in Developer Portal, then regenerate Access Token")
except Exception as e:
    print(f"  Exception: {e}")

# ── 4. Access Token format check ─────────────────────────────────────────────
print("\n[4] Access Token format check:")
if ACCESS_TOKEN:
    parts = ACCESS_TOKEN.split("-")
    if parts[0].isdigit():
        print(f"  ✅ Access Token starts with numeric user ID: {parts[0]}")
    else:
        print(f"  ⚠️  Access Token does NOT start with digits: '{ACCESS_TOKEN[:20]}...'")
        print("  → This might be an OAuth 2.0 token. You need OAuth 1.0a Access Token.")
else:
    print("  ❌ Access Token is empty")

print("\n" + "=" * 60)
print("Diagnostic complete.")
print("=" * 60)
