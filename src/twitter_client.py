"""
Twitter/X API v2 client module.
All write operations (post tweet, reply, like) use direct OAuth 1.0a HTTP requests.
Search uses Bearer Token via Tweepy (read-only, no OAuth 1.0a needed).
"""

import time
import hmac
import hashlib
import random
import string
import urllib.parse
import base64
import os
import requests
import tweepy
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import (
    TWITTER_BEARER_TOKEN,
    TWEET_MAX_AGE_HOURS,
    MIN_AUTHOR_FOLLOWERS,
    BLOCKED_ACCOUNTS,
)


# ─── OAuth 1.0a Helper ───────────────────────────────────────────────────────

def _get_oauth_keys():
    """Read Twitter OAuth 1.0a keys directly from environment at call time."""
    return {
        "api_key":            os.environ.get("TWITTER_API_KEY", "") or os.environ.get("TWITTER_CONSUMER_KEY", ""),
        "api_secret":         os.environ.get("TWITTER_API_SECRET", "") or os.environ.get("TWITTER_CONSUMER_SECRET", ""),
        "access_token":       os.environ.get("TWITTER_ACCESS_TOKEN", ""),
        "access_token_secret": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", ""),
    }


def _build_oauth_header(method: str, url: str, extra_params: dict = None) -> str:
    """Build OAuth 1.0a Authorization header for a request."""
    keys = _get_oauth_keys()
    nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    ts = str(int(time.time()))

    oauth_params = {
        "oauth_consumer_key":     keys["api_key"],
        "oauth_nonce":            nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        ts,
        "oauth_token":            keys["access_token"],
        "oauth_version":          "1.0",
    }

    # Merge extra params for signature base string (e.g. query params)
    all_params = {**oauth_params, **(extra_params or {})}
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])
    signing_key = (
        f"{urllib.parse.quote(keys['api_secret'], safe='')}"
        f"&{urllib.parse.quote(keys['access_token_secret'], safe='')}"
    )
    sig = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = sig

    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return auth_header


# ─── Tweepy client (read-only, for search) ───────────────────────────────────

def get_client() -> tweepy.Client:
    """Return Tweepy client with Bearer Token only (for search/read operations)."""
    bearer = os.environ.get("TWITTER_BEARER_TOKEN", "") or TWITTER_BEARER_TOKEN
    return tweepy.Client(
        bearer_token=bearer,
        wait_on_rate_limit=True,
    )


# ─── Search ──────────────────────────────────────────────────────────────────

def build_search_query(keywords: list[str], exclude_retweets: bool = True) -> str:
    """Build a Twitter search query from a list of keywords."""
    kw_parts = " OR ".join([f'"{kw}"' for kw in keywords[:5]])
    query = f"({kw_parts}) lang:en -is:reply"
    if exclude_retweets:
        query += " -is:retweet"
    return query


def search_tweets(
    client: tweepy.Client,
    keywords: list[str],
    max_results: int = 20,
) -> list[dict]:
    """Search recent tweets matching keywords."""
    query = build_search_query(keywords)
    print(f"[SEARCH] Query: {query}")

    try:
        response = client.search_recent_tweets(
            query=query,
            max_results=max_results,
            tweet_fields=["created_at", "author_id", "public_metrics", "lang"],
            expansions=["author_id"],
            user_fields=["username", "public_metrics", "verified"],
        )
    except tweepy.TweepyException as e:
        print(f"[ERROR] Search failed: {e}")
        return []

    if not response.data:
        print("[SEARCH] No tweets found.")
        return []

    users_by_id = {}
    if response.includes and "users" in response.includes:
        for user in response.includes["users"]:
            users_by_id[user.id] = user

    results = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=TWEET_MAX_AGE_HOURS)

    for tweet in response.data:
        author = users_by_id.get(tweet.author_id)
        if not author:
            continue
        if tweet.created_at and tweet.created_at < cutoff_time:
            continue
        followers = author.public_metrics.get("followers_count", 0) if author.public_metrics else 0
        if followers < MIN_AUTHOR_FOLLOWERS:
            continue
        if author.username in BLOCKED_ACCOUNTS:
            continue
        trigger = detect_trigger(tweet.text, keywords)
        results.append({
            "id": str(tweet.id),
            "text": tweet.text,
            "author_id": str(tweet.author_id),
            "author_username": author.username,
            "author_followers": followers,
            "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
            "trigger_keyword": trigger,
        })

    print(f"[SEARCH] Found {len(results)} qualifying tweets.")
    return results


def detect_trigger(text: str, keywords: list[str]) -> str:
    """Return the first keyword found in tweet text."""
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return kw
    return keywords[0] if keywords else "unknown"


# ─── Write Operations (direct OAuth 1.0a) ────────────────────────────────────

def post_tweet(client, tweet_text: str) -> Optional[str]:
    """Post an original tweet using direct OAuth 1.0a request."""
    url = "https://api.twitter.com/2/tweets"
    auth_header = _build_oauth_header("POST", url)
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
            json={"text": tweet_text},
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            new_id = str(data["data"]["id"])
            print(f"[TWEET] Posted original tweet → {new_id}")
            return new_id
        else:
            print(f"[ERROR] Failed to post tweet: {r.status_code} {r.reason}")
            print(f"[ERROR] Response: {r.text[:300]}")
            return None
    except Exception as e:
        print(f"[ERROR] Failed to post tweet: {e}")
        return None


def post_reply(client, reply_text: str, tweet_id: str) -> Optional[str]:
    """Post a reply to a tweet using direct OAuth 1.0a request."""
    url = "https://api.twitter.com/2/tweets"
    auth_header = _build_oauth_header("POST", url)
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
            json={
                "text": reply_text,
                "reply": {"in_reply_to_tweet_id": tweet_id},
            },
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            new_id = str(data["data"]["id"])
            print(f"[REPLY] Posted reply to tweet {tweet_id} → new tweet {new_id}")
            return new_id
        else:
            print(f"[ERROR] Failed to post reply: {r.status_code} {r.reason}")
            print(f"[ERROR] Response: {r.text[:300]}")
            return None
    except Exception as e:
        print(f"[ERROR] Failed to post reply: {e}")
        return None


def like_tweet(client, tweet_id: str, my_user_id: str) -> bool:
    """Like a tweet using direct OAuth 1.0a request."""
    url = f"https://api.twitter.com/2/users/{my_user_id}/likes"
    auth_header = _build_oauth_header("POST", url)
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
            json={"tweet_id": tweet_id},
            timeout=15,
        )
        if r.status_code in (200, 201):
            print(f"[LIKE] Liked tweet {tweet_id}")
            return True
        else:
            print(f"[WARN] Failed to like tweet: {r.status_code} {r.text[:100]}")
            return False
    except Exception as e:
        print(f"[WARN] Failed to like tweet: {e}")
        return False


# ─── Auth Check ──────────────────────────────────────────────────────────────

def get_my_user_id(client) -> Optional[str]:
    """Return the authenticated user's ID via direct OAuth 1.0a HTTP request."""
    url = "https://api.twitter.com/2/users/me"
    auth_header = _build_oauth_header("GET", url)

    keys = _get_oauth_keys()
    print(f"[DEBUG] TWITTER_API_KEY length: {len(keys['api_key'])}")
    print(f"[DEBUG] TWITTER_API_SECRET length: {len(keys['api_secret'])}")
    print(f"[DEBUG] TWITTER_ACCESS_TOKEN length: {len(keys['access_token'])}")
    print(f"[DEBUG] TWITTER_ACCESS_TOKEN_SECRET length: {len(keys['access_token_secret'])}")

    try:
        r = requests.get(url, headers={"Authorization": auth_header}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            user_id = data["data"]["id"]
            username = data["data"]["username"]
            print(f"[AUTH] Authenticated as @{username} (id={user_id})")
            return user_id
        else:
            print(f"[ERROR] Failed to get user ID: HTTP {r.status_code}")
            print(f"[ERROR] Response: {r.text[:300]}")
            return None
    except Exception as e:
        print(f"[ERROR] Failed to get user ID: {e}")
        return None
