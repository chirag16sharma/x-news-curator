# x-news-curator

Bot pulls fresh tech news from RSS, drafts an X (Twitter) post in your voice via Gemini, sends draft to Discord for review. Runs on schedule via GitHub Actions.

## How it works

1. `bot.py` scans feeds in `RSS_FEEDS`, grabs first article not in `history.json`.
2. Sends headline + summary to Gemini (`gemini-3.6-flash`) with your voice/rules in `SYSTEM_PROMPT`.
3. Posts draft to Discord webhook, code-blocked for easy copy on mobile.
4. Appends article URL to `history.json` (keeps last 300) so it's never redrafted.

## Setup

1. Fork/clone repo.
2. In repo Settings → Secrets and variables → Actions, add:
   - `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com/).
   - `DISCORD_WEBHOOK_URL` — Discord channel → Integrations → Webhooks → New Webhook.
3. Workflow (`.github/workflows/daily_posts.yml`) runs 3x/day (IST 9:15 AM, 2:10 PM, 7:20 PM). Edit cron lines to change schedule, or trigger manually via Actions → Daily Tech X Drafts → Run workflow.

## Local run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key
export DISCORD_WEBHOOK_URL=your_webhook
python bot.py
```

## Customize

- `RSS_FEEDS` — swap in your own sources.
- `SYSTEM_PROMPT` — your voice rules + example posts. Keep examples updated as your style shifts.
