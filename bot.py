import json
import os
import feedparser
import requests
from google import genai
from google.genai import types

# 1. Configure your tech RSS feeds
RSS_FEEDS = [
    "https://hnrss.org/frontpage?points=150",  # High-signal Hacker News stories
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://aws.amazon.com/blogs/aws/feed/",
]

HISTORY_FILE = "history.json"
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

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


def get_fresh_article(seen_urls):
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            link = entry.get("link", "").strip()
            if link and link not in seen_urls:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")[:600].strip()
                return {"title": title, "summary": summary, "link": link}
    return None


def generate_take(article):
    client = genai.Client(api_key=GEMINI_API_KEY)
    user_prompt = (
        f"News Headline: {article['title']}\n"
        f"Context: {article['summary']}\n\n"
        "Write one sharp, human-sounding X post with my take or advice on this:"
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.8,
        ),
    )
    return response.text.strip().strip('"')


def send_to_discord(article, post_text):
    # Putting the draft inside a code block makes it one-tap copyable on mobile
    payload = {
        "content": (
            f"**Source:** [{article['title']}](<{article['link']}>)\n"
            f"**Ready to post ({len(post_text)} chars):**\n"
            f"```\n{post_text}\n```"
        )
    }
    res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    res.raise_for_status()


def main():
    history = load_history()
    article = get_fresh_article(set(history))

    if not article:
        print("No new articles found.")
        return

    post_text = generate_take(article)
    send_to_discord(article, post_text)

    history.append(article["link"])
    save_history(history)
    print(f"Sent draft for: {article['title']}")


if __name__ == "__main__":
    main()
