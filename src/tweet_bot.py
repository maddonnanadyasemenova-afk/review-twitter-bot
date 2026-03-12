"""
Tweet Bot: posts original content tweets on a schedule.
Triggered by GitHub Actions at specific times each week.
"""

import sys
from datetime import datetime, timezone

from config import MAX_DAILY_REPLIES
from twitter_client import get_client, post_tweet, get_my_user_id
from generator import generate_original_tweet, sanitize_tweet
from storage import get_counter, increment_counter, log_action


# Weekly schedule: maps (weekday, hour_utc) → tweet format
# weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
# Times are in UTC (UTC+3 minus 3 hours)
WEEKLY_SCHEDULE = {
    (0, 6): "stat",           # Monday 09:00 UTC+3 → 06:00 UTC
    (1, 9): "tip",            # Tuesday 12:00 UTC+3 → 09:00 UTC
    (2, 7): "question",       # Wednesday 10:00 UTC+3 → 07:00 UTC
    (3, 11): "case",          # Thursday 14:00 UTC+3 → 11:00 UTC
    (4, 8): "hot_take",       # Friday 11:00 UTC+3 → 08:00 UTC
    (6, 15): "thread_intro",  # Sunday 18:00 UTC+3 → 15:00 UTC
}

# Daily product promo: every day at 17:00 UTC+3 (14:00 UTC)
DAILY_PROMO_HOUR_UTC = 14


def get_todays_format() -> str | None:
    """
    Determine which tweet format to post based on current UTC time.
    Returns format string or None if no tweet scheduled for this hour.
    Priority: weekly content first, then daily product promo.
    """
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    hour = now.hour

    # Check weekly content schedule first
    weekly = WEEKLY_SCHEDULE.get((weekday, hour))
    if weekly:
        return weekly

    # Daily product promo at 17:00 UTC+3 (14:00 UTC) every day
    if hour == DAILY_PROMO_HOUR_UTC:
        return "product_promo"

    return None


def run_tweet_bot(force_format: str | None = None):
    """
    Post an original tweet.
    force_format: override schedule (useful for testing).
    """
    print("=" * 60)
    print("Review Twitter Bot — Original Tweet Mode")
    print("=" * 60)

    # Determine format
    if force_format:
        tweet_format = force_format
        print(f"[MODE] Forced format: {tweet_format}")
    else:
        tweet_format = get_todays_format()
        if not tweet_format:
            now = datetime.now(timezone.utc)
            print(f"[SKIP] No tweet scheduled for {now.strftime('%A %H:%M UTC')}. Exiting.")
            return
        print(f"[SCHEDULE] Posting format '{tweet_format}' for {datetime.now(timezone.utc).strftime('%A %H:%M UTC')}")

    # Check daily tweet limit (max 2 original tweets per day)
    daily_tweets = get_counter("tweets")
    if daily_tweets >= 2:
        print(f"[LIMIT] Daily tweet limit reached ({daily_tweets}/2). Stopping.")
        return

    client = get_client()
    my_user_id = get_my_user_id(client)
    if not my_user_id:
        print("[ERROR] Could not authenticate. Check Twitter API credentials.")
        sys.exit(1)

    print(f"[AUTH] Authenticated. User ID: {my_user_id}")

    # Generate tweet
    try:
        tweet_text = generate_original_tweet(tweet_format)
        tweet_text = sanitize_tweet(tweet_text)
    except Exception as e:
        import traceback
        print(f"[ERROR] GPT generation failed: {e}")
        print(f"[ERROR] Full traceback:")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n[CONTENT] Generated tweet ({len(tweet_text)} chars):")
    print(f"  {tweet_text}")

    # Post tweet
    new_tweet_id = post_tweet(client, tweet_text)
    if not new_tweet_id:
        print("[ERROR] Failed to post tweet.")
        sys.exit(1)

    # Update state
    increment_counter("tweets")
    log_action(
        action_type="tweet",
        content=tweet_text,
        target_tweet_id=new_tweet_id,
    )

    print(f"\n[DONE] Original tweet posted successfully. ID: {new_tweet_id}")
    print(f"[DONE] Daily tweets: {get_counter('tweets')}/2")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Post an original tweet")
    parser.add_argument(
        "--format",
        choices=["stat", "tip", "question", "case", "hot_take", "thread_intro", "product_promo"],
        help="Force a specific tweet format (overrides schedule)",
        default=None,
    )
    args = parser.parse_args()
    run_tweet_bot(force_format=args.format)
