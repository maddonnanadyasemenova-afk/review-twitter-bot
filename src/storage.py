"""
Storage module: manages replied tweet IDs, daily counters, and action logs.
Uses JSON files committed back to the repo via GitHub Actions.
"""

import json
import os
from datetime import datetime, date, timezone
from typing import Optional

from config import LOG_FILE, REPLIED_IDS_FILE, DAILY_COUNTS_FILE


def _load_json(path: str, default) -> dict | list:
    """Load JSON file or return default if missing/corrupt."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_json(path: str, data) -> None:
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Replied IDs ─────────────────────────────────────────────────────────────

def load_replied_ids() -> dict:
    """
    Returns dict: {tweet_id: {"author": str, "replied_at": ISO timestamp}}
    """
    return _load_json(REPLIED_IDS_FILE, {})


def save_replied_ids(data: dict) -> None:
    _save_json(REPLIED_IDS_FILE, data)


def mark_as_replied(tweet_id: str, author: str) -> None:
    data = load_replied_ids()
    data[tweet_id] = {
        "author": author,
        "replied_at": datetime.now(timezone.utc).isoformat(),
    }
    save_replied_ids(data)


def already_replied(tweet_id: str) -> bool:
    data = load_replied_ids()
    return tweet_id in data


def replied_to_author_recently(author: str, cooldown_hours: int = 48) -> bool:
    """Check if we replied to this author within cooldown_hours."""
    from datetime import timedelta
    data = load_replied_ids()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
    for entry in data.values():
        if entry.get("author") == author:
            replied_at = datetime.fromisoformat(entry["replied_at"])
            if replied_at > cutoff:
                return True
    return False


# ─── Daily Counters ───────────────────────────────────────────────────────────

def load_daily_counts() -> dict:
    data = _load_json(DAILY_COUNTS_FILE, {})
    today = str(date.today())
    if data.get("date") != today:
        # Reset counters for new day
        data = {"date": today, "replies": 0, "tweets": 0, "likes": 0}
        save_daily_counts(data)
    return data


def save_daily_counts(data: dict) -> None:
    _save_json(DAILY_COUNTS_FILE, data)


def increment_counter(action: str) -> int:
    """Increment counter for action ('replies', 'tweets', 'likes'). Returns new value."""
    data = load_daily_counts()
    data[action] = data.get(action, 0) + 1
    save_daily_counts(data)
    return data[action]


def get_counter(action: str) -> int:
    data = load_daily_counts()
    return data.get(action, 0)


# ─── Action Log ───────────────────────────────────────────────────────────────

def log_action(
    action_type: str,
    content: str,
    target_tweet_id: Optional[str] = None,
    target_author: Optional[str] = None,
    trigger_keyword: Optional[str] = None,
) -> None:
    """Append an action entry to the log file."""
    logs = _load_json(LOG_FILE, [])
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "target_tweet_id": target_tweet_id,
        "target_author": target_author,
        "trigger_keyword": trigger_keyword,
        "content": content,
    }
    logs.append(entry)
    # Keep only last 500 entries to avoid bloat
    if len(logs) > 500:
        logs = logs[-500:]
    _save_json(LOG_FILE, logs)
    print(f"[LOG] {action_type.upper()} | @{target_author} | {content[:80]}...")
