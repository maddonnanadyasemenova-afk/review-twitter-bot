"""
Generator module: uses OpenAI GPT to craft contextual replies and original tweets.
"""

import re
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, PRODUCT_NAME, PRODUCT_DESCRIPTION


def _get_openai_client() -> OpenAI:
    """Create OpenAI client lazily to avoid import-time errors."""
    import os
    api_key = os.environ.get("OPENAI_API_KEY", "") or OPENAI_API_KEY
    return OpenAI(
        api_key=api_key,
        base_url="https://api.openai.com/v1",
    )

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a Twitter growth agent for "{PRODUCT_NAME}" — {PRODUCT_DESCRIPTION}.

Your persona: You are a knowledgeable B2B SaaS expert who genuinely cares about helping founders and product teams improve their customer feedback processes. You are NOT a salesperson.

Core rules:
1. NEVER directly promote {PRODUCT_NAME} in first replies. Build trust first.
2. Always add value: share data, frameworks, or actionable advice.
3. Keep replies to 2-4 sentences. Be concise, insightful, and human.
4. End with a thoughtful follow-up question to continue the conversation naturally.
5. Write in English only.
6. NEVER use more than 2 hashtags per tweet.
7. NEVER use phrases like "try our product", "check out our website", "we have a solution".
8. Sound like a smart human practitioner, not a marketing bot.
9. Do NOT use excessive exclamation marks.
10. Keep replies under 260 characters when possible. If needed, write a short thread (max 2 tweets).

When to mention {PRODUCT_NAME} (only if user explicitly asks for a tool recommendation):
- Use: "We built {PRODUCT_NAME} specifically for this — happy to share more if useful."
- Only after 2+ exchanges or if directly asked.
"""

# ─── Reply Generation ─────────────────────────────────────────────────────────

def generate_reply(tweet_text: str, author_handle: str, trigger_keyword: str) -> str:
    """
    Generate a contextual reply to a tweet.
    Returns the reply text (string).
    """
    user_prompt = f"""Tweet from @{author_handle}:
\"{tweet_text}\"

Trigger keyword detected: "{trigger_keyword}"

Write a helpful, expert reply to this tweet. Follow all rules from your persona.
Return ONLY the reply text, nothing else."""

    client = _get_openai_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=300,
        temperature=0.85,
    )
    reply = response.choices[0].message.content.strip()
    # Safety: strip any leftover quotes
    reply = reply.strip('"').strip("'")
    return reply


# ─── Original Tweet Generation ───────────────────────────────────────────────

TWEET_FORMATS = {
    "stat": (
        "Write an insightful tweet about customer reviews or feedback for SaaS companies. "
        "Format: [Surprising statistic or fact] + [Why it matters] + [Practical takeaway]. "
        "Max 2 hashtags. Under 260 characters."
    ),
    "tip": (
        "Write a practical how-to tweet for SaaS founders about improving their customer review process. "
        "Format: numbered steps (max 4). Include a concrete result or metric. "
        "Max 2 hashtags."
    ),
    "question": (
        "Write an engaging question tweet for SaaS founders about customer feedback, NPS, or reviews. "
        "Offer 3 answer options labeled A, B, C. Make it thought-provoking. "
        "Max 1 hashtag."
    ),
    "case": (
        "Write a short story-format tweet about a SaaS company that improved their metrics by fixing "
        "their customer review/feedback process. Use realistic but fictional numbers. "
        "Format: [Situation] + [Action] + [Result]. Max 2 hashtags."
    ),
    "hot_take": (
        "Write a bold, contrarian opinion tweet about customer reviews, NPS, or feedback culture in SaaS. "
        "Make it thought-provoking and slightly controversial. End with a question. "
        "Max 1 hashtag."
    ),
    "thread_intro": (
        "Write the opening tweet of a Twitter thread about a common mistake SaaS companies make "
        "with customer reviews or feedback. Make it a compelling hook that makes people want to read more. "
        "End with '(thread)' or a numbered indicator like '1/7'. Max 1 hashtag."
    ),
    "product_promo": (
        f"Write a compelling promotional tweet about {PRODUCT_NAME} — {PRODUCT_DESCRIPTION}. "
        "Rules: sound human and genuine, NOT like an ad. Focus on the pain it solves, not features. "
        "Use one of these angles (rotate daily): "
        "1) A specific problem it solves with a concrete outcome. "
        "2) A surprising insight about why most companies lose customers due to bad review handling. "
        "3) A direct CTA tweet: 'If you're a SaaS founder struggling with X, we built Y for you.' "
        "4) Social proof angle: what customers say after using it. "
        "Keep it under 240 characters. Max 2 hashtags. End with a soft CTA or question."
    ),
}


def generate_original_tweet(format_type: str = "stat") -> str:
    """
    Generate an original tweet for the given format type.
    format_type: one of 'stat', 'tip', 'question', 'case', 'hot_take', 'thread_intro'
    """
    prompt = TWEET_FORMATS.get(format_type, TWEET_FORMATS["stat"])
    full_prompt = (
        f"{prompt}\n\n"
        "Return ONLY the tweet text. No explanations, no quotes around it."
    )

    client = _get_openai_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_prompt},
        ],
        max_tokens=400,
        temperature=0.9,
    )
    tweet = response.choices[0].message.content.strip()
    tweet = tweet.strip('"').strip("'")
    return tweet


def count_hashtags(text: str) -> int:
    return len(re.findall(r"#\w+", text))


def sanitize_tweet(text: str, max_hashtags: int = 2) -> str:
    """Remove excess hashtags if GPT generated too many."""
    hashtags = re.findall(r"#\w+", text)
    if len(hashtags) > max_hashtags:
        for tag in hashtags[max_hashtags:]:
            text = text.replace(tag, "", 1)
    return text.strip()
