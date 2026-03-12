"""
Configuration module for Review Twitter Bot.
All settings are loaded from environment variables (GitHub Secrets).
"""

import os

# ─── Twitter / X API Credentials ───────────────────────────────────────────
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

# ─── OpenAI API ─────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"

# ─── Bot Behaviour Limits ────────────────────────────────────────────────────
MAX_REPLIES_PER_RUN = 5          # replies per single GitHub Actions run
MAX_DAILY_REPLIES = 15           # hard cap per day
MIN_INTERVAL_BETWEEN_REPLIES = 15  # minutes between replies
TWEET_MAX_AGE_HOURS = 6          # ignore tweets older than this
MIN_AUTHOR_FOLLOWERS = 500       # minimum followers of tweet author
REPLY_COOLDOWN_HOURS = 48        # don't reply to same account within N hours

# ─── Search Keywords ────────────────────────────────────────────────────────
KEYWORDS_HIGH_PRIORITY = [
    "customer reviews",
    "customer feedback",
    "negative reviews",
    "bad reviews",
    "review management",
    "NPS score",
    "net promoter score",
    "churn rate",
    "customer churn",
    "G2 reviews",
    "Trustpilot reviews",
    "App Store reviews",
    "collecting feedback",
    "feedback tool",
    "respond to reviews",
]

KEYWORDS_MEDIUM_PRIORITY = [
    "customer retention",
    "reduce churn",
    "product feedback",
    "user feedback",
    "social proof",
    "testimonials",
    "customer satisfaction",
    "CSAT score",
    "reputation management",
    "voice of customer",
]

# Competitors to monitor (mentions of these will trigger replies)
COMPETITOR_ACCOUNTS = [
    "Trustpilot",
    "G2dotcom",
    "Birdeye",
    "Podium",
    "Yotpo",
]

# ─── Accounts to NEVER reply to ─────────────────────────────────────────────
BLOCKED_ACCOUNTS = []

# ─── Product Info (used in prompts) ─────────────────────────────────────────
PRODUCT_NAME = "Review"
PRODUCT_DESCRIPTION = (
    "an AI platform that helps SaaS companies collect, analyze, "
    "and act on customer reviews and feedback"
)
PRODUCT_URL = "https://yourproducturl.com"  # Update this

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_FILE = "data/bot_log.json"
REPLIED_IDS_FILE = "data/replied_ids.json"
DAILY_COUNTS_FILE = "data/daily_counts.json"
