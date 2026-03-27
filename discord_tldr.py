"""
discord_tldr.py — Claude Code Stop hook.
Reads the Stop event JSON from stdin, extracts the last assistant message,
and posts a TLDR to the Discord webhook so Victor can follow along remotely.

Called automatically by Claude Code when Claude finishes a response.
Uses Claude Haiku to generate a real 1-2 sentence summary of everything done.
Falls back to naive truncation if the API call fails.
"""
import sys, json, os, re
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
FALLBACK_MAX_LEN    = 800


def extract_last_assistant(data):
    transcript = data.get("transcript", [])
    for msg in reversed(transcript):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            else:
                text = str(content)
            return text.strip()
    return None


def haiku_tldr(text):
    """Ask Claude Haiku for a 1-2 sentence plain-English summary of everything done."""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 120,
                "system": (
                    "You summarize a coding assistant's response into 1-2 plain sentences "
                    "for a remote user checking Discord. List ALL distinct things that were done "
                    "(files changed, pushed, fixed, etc.). Be specific and complete. "
                    "No markdown, no bullet points, no code blocks."
                ),
                "messages": [{"role": "user", "content": text[:6000]}],
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"].strip()
    except Exception:
        pass
    return None


def fallback_tldr(text):
    text = re.sub(r"```[\s\S]*?```", "[code]", text)
    text = re.sub(r"\n+", " ", text).strip()
    if len(text) <= FALLBACK_MAX_LEN:
        return text
    return text[:FALLBACK_MAX_LEN].rsplit(" ", 1)[0] + "..."


def main():
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}

    text = extract_last_assistant(data)
    if not text:
        return

    if ANTHROPIC_API_KEY:
        tldr = haiku_tldr(text) or fallback_tldr(text)
    else:
        tldr = fallback_tldr(text)

    try:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": f"**[Claude]** {tldr}"},
            timeout=8,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
