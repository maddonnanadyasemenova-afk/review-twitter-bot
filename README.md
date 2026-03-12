# Review Twitter Bot

An AI-powered Twitter/X bot for the **Review** product. It automatically:
- Replies to relevant tweets about customer feedback, NPS, churn, and reviews
- Posts original expert content on a weekly schedule
- Runs entirely on **GitHub Actions** — no server required

---

## How It Works

```
GitHub Actions (cron schedule)
        │
        ▼
Search Twitter for trigger keywords
        │
        ▼
Filter by: age < 6h, followers > 500, not replied recently
        │
        ▼
Generate contextual reply via OpenAI GPT
        │
        ▼
Post reply → Log action → Save state back to repo
```

---

## Project Structure

```
review-twitter-bot/
├── .github/
│   └── workflows/
│       ├── reply_bot.yml       # Runs every 3h (08:00–20:00 UTC+3)
│       └── tweet_bot.yml       # Runs on weekly schedule
├── src/
│   ├── config.py               # All settings and keywords
│   ├── storage.py              # State management (replied IDs, counters, logs)
│   ├── twitter_client.py       # Twitter API v2 wrapper (Tweepy)
│   ├── generator.py            # OpenAI GPT reply/tweet generator
│   ├── reply_bot.py            # Main reply logic
│   └── tweet_bot.py            # Main original tweet logic
├── data/
│   ├── replied_ids.json        # Tracks replied tweet IDs (auto-updated)
│   ├── daily_counts.json       # Daily action counters (auto-updated)
│   └── bot_log.json            # Full action log (auto-updated)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Setup Instructions

### Step 1: Add GitHub Secrets

Go to your repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add the following secrets:

| Secret Name | Where to get it |
|---|---|
| `TWITTER_BEARER_TOKEN` | Twitter Developer Portal → Your App → Keys and Tokens |
| `TWITTER_API_KEY` | Twitter Developer Portal → Your App → Keys and Tokens |
| `TWITTER_API_SECRET` | Twitter Developer Portal → Your App → Keys and Tokens |
| `TWITTER_ACCESS_TOKEN` | Twitter Developer Portal → Your App → Keys and Tokens |
| `TWITTER_ACCESS_TOKEN_SECRET` | Twitter Developer Portal → Your App → Keys and Tokens |
| `OPENAI_API_KEY` | platform.openai.com → API Keys |

### Step 2: Update Product URL

In `src/config.py`, update:
```python
PRODUCT_URL = "https://yourproducturl.com"  # ← replace with your actual URL
```

### Step 3: Enable GitHub Actions

Go to **Actions** tab in your repository and click **"I understand my workflows, go ahead and enable them"**.

### Step 4: Test manually

Go to **Actions** → **Reply Bot** → **Run workflow** to trigger a test run.

---

## Daily Limits (Safety)

| Action | Daily Limit |
|---|---|
| Replies | 15 |
| Original tweets | 2 |
| Likes | 30 |

The bot automatically stops when limits are reached and resets at midnight.

---

## Customization

**Add/remove keywords:** Edit `KEYWORDS_HIGH_PRIORITY` and `KEYWORDS_MEDIUM_PRIORITY` in `src/config.py`

**Change tweet schedule:** Edit cron expressions in `.github/workflows/tweet_bot.yml`

**Adjust reply frequency:** Change `MAX_REPLIES_PER_RUN` in `src/config.py`

**Change GPT model:** Update `OPENAI_MODEL` in `src/config.py` (e.g., `gpt-4o` for higher quality)

---

## Monitoring

All actions are logged in `data/bot_log.json`. Each entry contains:
- Timestamp
- Action type (reply / tweet / like)
- Target tweet ID and author
- Generated content
- Trigger keyword

---

*Built for the Review product. Powered by Twitter API v2 + OpenAI GPT + GitHub Actions.*
