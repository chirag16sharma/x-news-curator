"""Merge the just-posted article URL into history.json at HEAD.

Used by the "Save posted article history" workflow step. Reads the URL from
last_posted_link.txt (written by bot.py after a successful post) and the
current history.json at HEAD, and writes the merged result back to
history.json on disk for the workflow to git-add/commit.

Kept as a standalone script (rather than an inline heredoc in the workflow
YAML) so it isn't at the mercy of the YAML block's indentation.
"""
import json
import subprocess

LINK_FILE = "last_posted_link.txt"
HISTORY_FILE = "history.json"
MAX_HISTORY = 300


def main():
    with open(LINK_FILE, encoding="utf-8") as f:
        link = f.read().strip()

    raw = subprocess.run(
        ["git", "show", f"HEAD:{HISTORY_FILE}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    history = json.loads(raw) if raw.strip() else []

    if link not in history:
        history.append(link)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-MAX_HISTORY:], f, indent=2)


if __name__ == "__main__":
    main()
