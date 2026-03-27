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

LOG = os.path.expanduser("~/discord_tldr.log")

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
FALLBACK_MAX_LEN    = 800


def extract_last_assistant(data):
    log(f"  data keys: {list(data.keys())}")
    # Stop hook sends last_assistant_message directly
    msg = data.get("last_assistant_message", "")
    if msg:
        return msg.strip()
    # Fallback: walk transcript if present
    transcript = data.get("transcript", [])
    log(f"  transcript length: {len(transcript)}")
    for m in reversed(transcript):
        if m.get("role") == "assistant":
            content = m.get("content", "")
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
            return str(content).strip()
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
                    "You summarize a coding assistant's latest message into 1-2 plain sentences "
                    "for a remote user checking Discord. Focus on what was DONE or what STATUS was shared. "
                    "If the message is just a short acknowledgment, background task notification, or "
                    "'ready when you are' type message, respond with exactly: SKIP\n"
                    "Never complain, never say you can't do something, never ask for more context. "
                    "Just summarize what happened or say SKIP. No markdown, no bullets, no code blocks."
                ),
                "messages": [{"role": "user", "content": text[:6000]}],
            },
            timeout=15,
        )
        log(f"  haiku status: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"].strip()
        else:
            log(f"  haiku error body: {resp.text[:200]}")
    except Exception as e:
        log(f"  haiku exception: {e}")
    return None


def fallback_tldr(text):
    text = re.sub(r"```[\s\S]*?```", "[code]", text)
    text = re.sub(r"\n+", " ", text).strip()
    if len(text) <= FALLBACK_MAX_LEN:
        return text
    return text[:FALLBACK_MAX_LEN].rsplit(" ", 1)[0] + "..."


def main():
    log("=== discord_tldr fired ===")

    if not DISCORD_WEBHOOK_URL:
        log("  ABORT: no DISCORD_WEBHOOK_URL")
        return
    log(f"  webhook: {DISCORD_WEBHOOK_URL[:40]}...")

    raw = sys.stdin.read()
    log(f"  stdin bytes: {len(raw)}")

    try:
        data = json.loads(raw or "{}")
    except Exception as e:
        log(f"  JSON parse error: {e}")
        data = {}

    text = extract_last_assistant(data)
    if not text:
        log("  ABORT: no assistant text found")
        return
    log(f"  assistant text ({len(text)} chars): {text[:120]!r}")

    if ANTHROPIC_API_KEY:
        tldr = haiku_tldr(text) or fallback_tldr(text)
    else:
        tldr = fallback_tldr(text)
    log(f"  tldr: {tldr!r}")

    # Skip trivial messages (Haiku returns "SKIP" for acks/notifications)
    if not tldr or tldr.strip().upper() == 'SKIP':
        log("  SKIP: trivial message, not posting")
        return

    try:
        r = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": f"**[Claude]** {tldr}"},
            timeout=8,
        )
        log(f"  webhook response: {r.status_code}")
    except Exception as e:
        log(f"  webhook exception: {e}")


if __name__ == "__main__":
    main()
