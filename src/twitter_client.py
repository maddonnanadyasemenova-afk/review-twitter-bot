"""
Twitter/X API v2 client module.
Handles search, reply, and tweet posting using Tweepy.
"""

import time
import tweepy
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import (
    TWITTER_BEARER_TOKEN,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
    TWEET_MAX_AGE_HOURS,
    MIN_AUTHOR_FOLLOWERS,
    KEYWORDS_HIGH_PRIORITY,
    KEYWORDS_MEDIUM_PRIORITY,
    COMPETITOR_ACCOUNTS,
    BLOCKED_ACCOUNTS,
)


def get_client() -> tweepy.Client:
    """Return authenticated Tweepy v2 Client."""
    return tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


def build_search_query(keywords: list[str], exclude_retweets: bool = True) -> str:
    """Build a Twitter search query from a list of keywords."""
    kw_parts = " OR ".join([f'"{kw}"' for kw in keywords[:5]])  # max 5 per query
    query = f"({kw_parts}) lang:en -is:reply"
    if exclude_retweets:
        query += " -is:retweet"
    return query


def search_tweets(
    client: tweepy.Client,
    keywords: list[str],
    max_results: int = 20,
) -> list[dict]:
    """
    Search recent tweets matching keywords.
    Returns list of tweet dicts with id, text, author_id, created_at.
    """
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

    # Build author lookup
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

        # Age filter
        if tweet.created_at and tweet.created_at < cutoff_time:
            continue

        # Follower filter
        followers = author.public_metrics.get("followers_count", 0) if author.public_metrics else 0
        if followers < MIN_AUTHOR_FOLLOWERS:
            continue

        # Blocked accounts filter
        if author.username in BLOCKED_ACCOUNTS:
            continue

        # Detect which keyword triggered this
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


def post_reply(client: tweepy.Client, reply_text: str, tweet_id: str) -> Optional[str]:
    """
    Post a reply to a tweet.
    Returns the new tweet ID on success, None on failure.
    """
    try:
        response = client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet_id,
        )
        new_id = str(response.data["id"])
        print(f"[REPLY] Posted reply to tweet {tweet_id} → new tweet {new_id}")
        return new_id
    except tweepy.TweepyException as e:
        print(f"[ERROR] Failed to post reply: {e}")
        return None


def post_tweet(client: tweepy.Client, tweet_text: str) -> Optional[str]:
    """
    Post an original tweet.
    Returns the new tweet ID on success, None on failure.
    """
    try:
        response = client.create_tweet(text=tweet_text)
        new_id = str(response.data["id"])
        print(f"[TWEET] Posted original tweet → {new_id}")
        return new_id
    except tweepy.TweepyException as e:
        print(f"[ERROR] Failed to post tweet: {e}")
        return None


def like_tweet(client: tweepy.Client, tweet_id: str, my_user_id: str) -> bool:
    """Like a tweet. Returns True on success."""
    try:
        client.like(my_user_id, tweet_id)
        print(f"[LIKE] Liked tweet {tweet_id}")
        return True
    except tweepy.TweepyException as e:
        print(f"[ERROR] Failed to like tweet: {e}")
        return False


def get_my_user_id(client: tweepy.Client) -> Optional[str]:
    """
    Return the authenticated user's ID via direct OAuth 1.0a HTTP request.
    Uses raw requests + OAuth1 to avoid tweepy.get_me() 401 issues.
    """
    import hmac
    import hashlib
    import random
    import string
    import urllib.parse
    import base64
    import requests as req

    # Read directly from env to avoid config.py caching empty values
    TWITTER_API_KEY           = os.environ.get("TWITTER_API_KEY", "") or os.environ.get("TWITTER_CONSUMER_KEY", "")
    TWITTER_API_SECRET        = os.environ.get("TWITTER_API_SECRET", "") or os.environ.get("TWITTER_CONSUMER_SECRET", "")
    TWITTER_ACCESS_TOKEN      = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

    url = "https://api.twitter.com/2/users/me"
    method = "GET"
    nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    ts = str(int(time.time()))

    oauth_params = {
        "oauth_consumer_key": TWITTER_API_KEY,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": ts,
        "oauth_token": TWITTER_ACCESS_TOKEN,
        "oauth_version": "1.0",
    }
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])
    signing_key = f"{urllib.parse.quote(TWITTER_API_SECRET, safe='')}&{urllib.parse.quote(TWITTER_ACCESS_TOKEN_SECRET, safe='')}"
    sig = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()  # noqa
    ).decode()
    oauth_params["oauth_signature"] = sig
    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )

    # Debug: print key lengths to verify secrets are loaded
    print(f"[DEBUG] TWITTER_API_KEY length: {len(TWITTER_API_KEY)}")
    print(f"[DEBUG] TWITTER_API_SECRET length: {len(TWITTER_API_SECRET)}")
    print(f"[DEBUG] TWITTER_ACCESS_TOKEN length: {len(TWITTER_ACCESS_TOKEN)}")
    print(f"[DEBUG] TWITTER_ACCESS_TOKEN_SECRET length: {len(TWITTER_ACCESS_TOKEN_SECRET)}")

    try:
        r = req.get(url, headers={"Authorization": auth_header}, timeout=10)
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
