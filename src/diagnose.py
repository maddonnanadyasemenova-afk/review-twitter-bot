"""
Diagnostic script: checks each Twitter API credential individually.
Run via GitHub Actions → Diagnose workflow → Run workflow.
"""

import os
import sys
import requests
from requests_oauthlib import OAuth1

# ─── Load credentials ────────────────────────────────────────────────────────
BEARER_TOKEN          = os.environ.get("TWITTER_BEARER_TOKEN", "")
API_KEY               = os.environ.get("TWITTER_API_KEY", "")
API_SECRET            = os.environ.get("TWITTER_API_SECRET", "")
ACCESS_TOKEN          = os.environ.get("TWITTER_ACCESS_TOKEN", "")
ACCESS_TOKEN_SECRET   = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")
OPENAI_API_KEY        = os.environ.get("OPENAI_API_KEY", "")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []

def check(label, ok, detail=""):
    status = PASS if ok else FAIL
    msg = f"{status}  {label}"
    if detail:
        msg += f"\n        → {detail}"
    results.append((ok, msg))
    print(msg)


print("=" * 60)
print("Twitter API Credentials Diagnostic")
print("=" * 60)

# ─── 1. Check secrets are not empty ──────────────────────────────────────────
print("\n[1] Checking secrets are set (non-empty)...")
check("TWITTER_BEARER_TOKEN is set",      bool(BEARER_TOKEN),        f"length={len(BEARER_TOKEN)}")
check("TWITTER_API_KEY is set",           bool(API_KEY),             f"length={len(API_KEY)}")
check("TWITTER_API_SECRET is set",        bool(API_SECRET),          f"length={len(API_SECRET)}")
check("TWITTER_ACCESS_TOKEN is set",      bool(ACCESS_TOKEN),        f"length={len(ACCESS_TOKEN)}")
check("TWITTER_ACCESS_TOKEN_SECRET is set", bool(ACCESS_TOKEN_SECRET), f"length={len(ACCESS_TOKEN_SECRET)}")
check("OPENAI_API_KEY is set",            bool(OPENAI_API_KEY),      f"length={len(OPENAI_API_KEY)}")

# ─── 2. Test Bearer Token (App-only auth) ────────────────────────────────────
print("\n[2] Testing Bearer Token (App-only auth)...")
try:
    resp = requests.get(
        "https://api.twitter.com/2/tweets/search/recent",
        headers={"Authorization": f"Bearer {BEARER_TOKEN}"},
        params={"query": "hello", "max_results": 10},
        timeout=10,
    )
    if resp.status_code == 200:
        check("Bearer Token — search tweets", True, f"HTTP {resp.status_code}")
    elif resp.status_code == 401:
        check("Bearer Token — search tweets", False,
              f"HTTP 401 Unauthorized. Bearer Token is invalid or expired.")
    elif resp.status_code == 403:
        check("Bearer Token — search tweets", False,
              f"HTTP 403 Forbidden. Your Twitter App may not have 'Read' permissions or Basic/Pro API access.")
    else:
        check("Bearer Token — search tweets", False,
              f"HTTP {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    check("Bearer Token — search tweets", False, str(e))

# ─── 3. Test OAuth 1.0a (User auth — needed for posting) ─────────────────────
print("\n[3] Testing OAuth 1.0a User Auth (needed to post tweets)...")
try:
    auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    resp = requests.get(
        "https://api.twitter.com/2/users/me",
        auth=auth,
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        username = data.get("data", {}).get("username", "unknown")
        user_id  = data.get("data", {}).get("id", "unknown")
        check("OAuth 1.0a — get authenticated user", True,
              f"Logged in as @{username} (id={user_id})")
    elif resp.status_code == 401:
        check("OAuth 1.0a — get authenticated user", False,
              "HTTP 401. API_KEY/SECRET or ACCESS_TOKEN/SECRET is wrong. "
              "Try regenerating Access Token in Twitter Developer Portal.")
    elif resp.status_code == 403:
        check("OAuth 1.0a — get authenticated user", False,
              "HTTP 403. App permissions may be set to 'Read only'. "
              "Change to 'Read and Write' in Twitter Developer Portal, then regenerate Access Token.")
    else:
        check("OAuth 1.0a — get authenticated user", False,
              f"HTTP {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    check("OAuth 1.0a — get authenticated user", False, str(e))

# ─── 4. Test OpenAI key ───────────────────────────────────────────────────────
print("\n[4] Testing OpenAI API key...")
try:
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    models = client.models.list()
    check("OpenAI API key", True, f"Connected. First model: {models.data[0].id if models.data else 'n/a'}")
except openai.AuthenticationError:
    check("OpenAI API key", False, "Invalid API key. Check OPENAI_API_KEY secret.")
except Exception as e:
    check("OpenAI API key", False, str(e))

# ─── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
failed = [msg for ok, msg in results if not ok]
passed = [msg for ok, msg in results if ok]
print(f"Passed: {len(passed)} / {len(results)}")
if failed:
    print(f"\nFailed checks:")
    for msg in failed:
        print(f"  {msg}")
    sys.exit(1)
else:
    print("All checks passed!")
    sys.exit(0)
