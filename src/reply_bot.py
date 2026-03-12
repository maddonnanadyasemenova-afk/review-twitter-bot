"""
Reply Bot: searches for relevant tweets and posts contextual replies.
Triggered by GitHub Actions on a schedule.
"""

import time
import random
import sys

from config import (
    KEYWORDS_HIGH_PRIORITY,
    KEYWORDS_MEDIUM_PRIORITY,
    COMPETITOR_ACCOUNTS,
    MAX_REPLIES_PER_RUN,
    MAX_DAILY_REPLIES,
    REPLY_COOLDOWN_HOURS,
    MIN_INTERVAL_BETWEEN_REPLIES,
)
from twitter_client import get_client, search_tweets, post_reply, like_tweet, get_my_user_id
from generator import generate_reply, sanitize_tweet
from storage import (
    already_replied,
    mark_as_replied,
    replied_to_author_recently,
    get_counter,
    increment_counter,
    log_action,
)


def run_reply_bot():
    print("=" * 60)
    print("Review Twitter Bot — Reply Mode")
    print("=" * 60)

    # Check daily limit
    daily_count = get_counter("replies")
    if daily_count >= MAX_DAILY_REPLIES:
        print(f"[LIMIT] Daily reply limit reached ({daily_count}/{MAX_DAILY_REPLIES}). Stopping.")
        return

    client = get_client()
    my_user_id = get_my_user_id(client)
    if not my_user_id:
        print("[ERROR] Could not authenticate. Check Twitter API credentials.")
        sys.exit(1)

    print(f"[AUTH] Authenticated. User ID: {my_user_id}")

    replies_this_run = 0

    # ─── Search high-priority keywords ───────────────────────────────────────
    all_tweets = []

    # High priority batch
    high_tweets = search_tweets(client, KEYWORDS_HIGH_PRIORITY[:5], max_results=20)
    for t in high_tweets:
        t["priority"] = "high"
    all_tweets.extend(high_tweets)

    # Medium priority batch
    medium_tweets = search_tweets(client, KEYWORDS_MEDIUM_PRIORITY[:5], max_results=10)
    for t in medium_tweets:
        t["priority"] = "medium"
    all_tweets.extend(medium_tweets)

    # Competitor mention batch
    competitor_keywords = [f"@{acc}" for acc in COMPETITOR_ACCOUNTS[:3]]
    comp_tweets = search_tweets(client, competitor_keywords, max_results=10)
    for t in comp_tweets:
        t["priority"] = "competitor"
    all_tweets.extend(comp_tweets)

    # Sort: high priority first, then by follower count descending
    priority_order = {"high": 0, "competitor": 1, "medium": 2}
    all_tweets.sort(
        key=lambda x: (priority_order.get(x["priority"], 3), -x.get("author_followers", 0))
    )

    print(f"[QUEUE] Total qualifying tweets to process: {len(all_tweets)}")

    # ─── Process tweets ───────────────────────────────────────────────────────
    for tweet in all_tweets:
        if replies_this_run >= MAX_REPLIES_PER_RUN:
            print(f"[LIMIT] Per-run limit reached ({MAX_REPLIES_PER_RUN}). Stopping.")
            break

        daily_count = get_counter("replies")
        if daily_count >= MAX_DAILY_REPLIES:
            print(f"[LIMIT] Daily limit reached ({MAX_DAILY_REPLIES}). Stopping.")
            break

        tweet_id = tweet["id"]
        author = tweet["author_username"]
        tweet_text = tweet["text"]
        trigger = tweet["trigger_keyword"]

        # ── Deduplication checks ──────────────────────────────────────────────
        if already_replied(tweet_id):
            print(f"[SKIP] Already replied to tweet {tweet_id}")
            continue

        if replied_to_author_recently(author, REPLY_COOLDOWN_HOURS):
            print(f"[SKIP] Replied to @{author} recently (cooldown {REPLY_COOLDOWN_HOURS}h)")
            continue

        # ── Generate reply ────────────────────────────────────────────────────
        print(f"\n[PROCESS] Tweet by @{author} ({tweet['author_followers']} followers)")
        print(f"  Text: {tweet_text[:100]}...")
        print(f"  Trigger: {trigger} | Priority: {tweet['priority']}")

        try:
            reply_text = generate_reply(tweet_text, author, trigger)
            reply_text = sanitize_tweet(reply_text)
        except Exception as e:
            print(f"[ERROR] GPT generation failed: {e}")
            continue

        print(f"  Reply: {reply_text}")

        # ── Post reply ────────────────────────────────────────────────────────
        new_tweet_id = post_reply(client, reply_text, tweet_id)
        if not new_tweet_id:
            print(f"[ERROR] Failed to post reply to {tweet_id}")
            continue

        # ── Update state ──────────────────────────────────────────────────────
        mark_as_replied(tweet_id, author)
        increment_counter("replies")
        replies_this_run += 1

        log_action(
            action_type="reply",
            content=reply_text,
            target_tweet_id=tweet_id,
            target_author=author,
            trigger_keyword=trigger,
        )

        # ── Optional: like the original tweet ────────────────────────────────
        like_tweet(client, tweet_id, my_user_id)
        increment_counter("likes")

        # ── Human-like delay ──────────────────────────────────────────────────
        delay = random.randint(
            MIN_INTERVAL_BETWEEN_REPLIES * 60,
            MIN_INTERVAL_BETWEEN_REPLIES * 60 + 300,
        )
        print(f"[WAIT] Sleeping {delay // 60}m {delay % 60}s before next reply...")
        time.sleep(delay)

    print(f"\n[DONE] Reply run complete. Replies this run: {replies_this_run}")
    print(f"[DONE] Daily total: {get_counter('replies')}/{MAX_DAILY_REPLIES}")


if __name__ == "__main__":
    run_reply_bot()
