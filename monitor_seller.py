"""
monitor_seller.py — Checks eBay item listing for seller away notice.
Pings Discord every hour with current status.
Sends a special "BACK!" alert (only once) when seller returns.
"""

import os, sys, json, re
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
ITEM_ID = "157626935379"
ITEM_URL = f"https://www.ebay.com/itm/{ITEM_ID}"
FLAG_FILE = "seller_alerted.flag"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

AWAY_PHRASES = [
    "away until",
    "seller is away",
    "on vacation",
    "away on vacation",
    "seller is on vacation",
    "will ship after",
    "extended handling time",
]


def already_alerted():
    return os.path.exists(FLAG_FILE)


def mark_alerted():
    with open(FLAG_FILE, "w") as f:
        f.write(datetime.utcnow().isoformat())


def check_listing():
    print(f"Checking: {ITEM_URL}")
    try:
        r = requests.get(ITEM_URL, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"Fetch error: {e}")
        return {"status": "error", "error": str(e)}

    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text(separator=" ").lower()

    # Check for ended listing
    if r.status_code == 404 or "this listing has ended" in page_text or "item not found" in page_text:
        return {"status": "ended"}

    # Check for away / vacation notice
    for phrase in AWAY_PHRASES:
        if phrase in page_text:
            idx = page_text.find(phrase)
            snippet = page_text[max(0, idx - 10):idx + 80].strip()
            # Capitalise for display
            snippet = snippet.strip().capitalize()
            print(f"Away notice: '{snippet}'")
            return {"status": "away", "snippet": snippet}

    # No away notice — seller is back
    title_tag = soup.find("h1", {"class": re.compile(r"x-item-title", re.I)})
    if not title_tag:
        title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else f"Item {ITEM_ID}"

    return {"status": "back", "title": title}


def send_discord(msg):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL — skipping")
        return
    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": msg, "username": "eBay Seller Monitor"},
        timeout=10,
    )
    print(f"Discord: {r.status_code}")


def main():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    result = check_listing()
    print(json.dumps(result, indent=2))

    if result["status"] == "away":
        send_discord(
            f"⏰ **Seller still away** ({now})\n"
            f"> {result['snippet']}\n"
            f"{ITEM_URL}"
        )

    elif result["status"] == "back":
        if not already_alerted():
            send_discord(
                f"🟢 **SELLER IS BACK — BUY NOW!** ({now})\n"
                f"**{result['title']}**\n"
                f"{ITEM_URL}"
            )
            mark_alerted()
            print("Flag written.")
        else:
            send_discord(
                f"✅ **Seller is back** (already alerted, just confirming) ({now})\n"
                f"{ITEM_URL}"
            )

    elif result["status"] == "ended":
        send_discord(
            f"❌ **Listing ended or removed** ({now})\n"
            f"{ITEM_URL}"
        )
        mark_alerted()

    elif result["status"] == "error":
        send_discord(
            f"⚠️ **Check failed** ({now}): {result.get('error', 'unknown error')}\n"
            f"{ITEM_URL}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
