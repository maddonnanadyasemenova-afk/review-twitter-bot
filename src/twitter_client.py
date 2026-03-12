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
    """Return the authenticated user's ID."""
    try:
        me = client.get_me()
        return str(me.data.id)
    except tweepy.errors.Unauthorized as e:
        print(f"[ERROR] 401 Unauthorized — details: {e}")
        print("[HINT] Common causes:")
        print("  1. Access Token was created BEFORE setting Read+Write permissions")
        print("     → Go to Twitter Developer Portal → App → Settings → User authentication settings")
        print("     → Set permissions to 'Read and Write'")
        print("     → Then regenerate Access Token & Secret")
        print("  2. Wrong Access Token type — make sure you use OAuth 1.0a tokens, not OAuth 2.0")
        print("  3. App is not attached to a Twitter account (needs Elevated access or Basic)")
        return None
    except tweepy.TweepyException as e:
        print(f"[ERROR] Failed to get user ID: {e}")
        return None
