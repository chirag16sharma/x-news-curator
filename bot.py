import json
import os
import re
import sys
import time
import feedparser
import requests
from google import genai
from google.genai import types
from google.genai.errors import ServerError

# 1. Configure your tech RSS feeds
RSS_FEEDS = [
    "https://hnrss.org/frontpage?points=150",  # High-signal Hacker News stories
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://aws.amazon.com/blogs/aws/feed/",
]

HISTORY_FILE = "history.json"
DISCORD_CONTENT_LIMIT = 2000


def _require_env(name):
    # .strip() guards against a stray trailing newline/space when a secret
    # gets pasted into GitHub Actions — that's enough to make Discord 401.
    value = (os.environ.get(name) or "").strip()
    if not value:
        print(f"Missing required env var: {name}")
        sys.exit(1)
    return value


GEMINI_API_KEY = _require_env("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = _require_env("DISCORD_WEBHOOK_URL")

# 2. Customize your voice & rules here
SYSTEM_PROMPT = """
You write short, sharp X (Twitter) posts in my exact voice reacting to tech news.

RULES:
- Share a grounded opinion, practical takeaway, or builder advice—never a generic news summary.
- Keep it strictly under 260 characters.
- No hashtags, no emojis, and no AI hype words (e.g., game-changer, revolutionary, wild, insane, delve, buckle up).
- Never start with "Just saw", "Interesting", "Big news", or "Here's why".
- Write in lowercase or normal conversational casing, matching the examples below.
- Output ONLY the final post text, nothing else.

MY VOICE EXAMPLES:
- Most teams don't have a scaling problem, they have a caching and database indexing problem wrapped in microservices.
- Everyone is obsessed with bigger models when 80% of production apps just need lower latency and predictable JSON outputs.
- Best way to learn cloud architecture isn't watching another 10-hour course—it's breaking a live deployment and fixing the IAM permissions yourself.
"""


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    # Keep the last 300 URLs so the file stays tiny
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-300:], f, indent=2)


def _clean_summary(raw):
    # RSS summaries often carry HTML tags/entities. Strip tags, trim.
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def get_fresh_article(seen_urls):
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"Feed fetch failed ({feed_url}): {e}")
            continue

        if feed.get("bozo") and not feed.entries:
            print(f"Feed unreadable, skipping ({feed_url}): {feed.get('bozo_exception')}")
            continue

        for entry in feed.entries[:10]:
            link = entry.get("link", "").strip()
            if link and link not in seen_urls:
                title = entry.get("title", "").strip()
                summary = _clean_summary(entry.get("summary", ""))
                return {"title": title, "summary": summary, "link": link}
    return None


GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_BACKOFF_SECONDS = 20  # doubled each retry


def generate_take(article):
    client = genai.Client(api_key=GEMINI_API_KEY)
    user_prompt = (
        f"News Headline: {article['title']}\n"
        f"Context: {article['summary']}\n\n"
        "Write one sharp, human-sounding X post with my take or advice on this:"
    )

    last_err = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                ),
            )
            text = (response.text or "").strip().strip('"')
            if not text:
                raise RuntimeError("Gemini returned empty text")
            return text
        except ServerError as e:
            # 503/UNAVAILABLE = model overloaded, usually transient. Retry with backoff.
            last_err = e
            if attempt < GEMINI_MAX_RETRIES:
                wait = GEMINI_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(f"Gemini server error (attempt {attempt}/{GEMINI_MAX_RETRIES}): {e}. Retrying in {wait}s.")
                time.sleep(wait)

    raise last_err


def send_to_discord(article, post_text):
    title = article["title"]
    # Putting the draft inside a code block makes it one-tap copyable on mobile
    content = (
        f"**Source:** [{title}](<{article['link']}>)\n"
        f"**Ready to post ({len(post_text)} chars):**\n"
        f"```\n{post_text}\n```"
    )
    if len(content) > DISCORD_CONTENT_LIMIT:
        # Headline overflow shouldn't ever drop the actual post draft.
        overflow = len(content) - DISCORD_CONTENT_LIMIT
        title = title[: max(0, len(title) - overflow - 1)].rstrip() + "…"
        content = (
            f"**Source:** [{title}](<{article['link']}>)\n"
            f"**Ready to post ({len(post_text)} chars):**\n"
            f"```\n{post_text}\n```"
        )

    res = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=15)
    res.raise_for_status()


def main():
    history = load_history()
    article = get_fresh_article(set(history))

    if not article:
        print("No new articles found.")
        return

    try:
        post_text = generate_take(article)
        send_to_discord(article, post_text)
    except Exception as e:
        # Don't mark the article as seen if we never actually delivered it —
        # otherwise a flaky Gemini/Discord call permanently skips that story.
        print(f"Failed to process article ({article['link']}): {e}")
        sys.exit(1)

    history.append(article["link"])
    save_history(history)
    print(f"Sent draft for: {article['title']}")


if __name__ == "__main__":
    main()
