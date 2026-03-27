"""
monitor_seller.py — Checks eBay item listing for seller away notice.
Sends a Discord ping when the seller is back and accepting orders.

State is tracked via seller_alerted.flag so you only get pinged once.
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
        r.raise_for_status()
    except Exception as e:
        print(f"Fetch error: {e}")
        return {"status": "error", "error": str(e)}

    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text(separator=" ").lower()

    # Check for "item not found / ended" — listing may have been pulled
    if r.status_code == 404 or "this listing has ended" in page_text or "item not found" in page_text:
        return {"status": "ended", "note": "Listing is no longer available"}

    # Check for away / vacation notice anywhere on the page
    for phrase in AWAY_PHRASES:
        if phrase in page_text:
            # Try to extract the context around the phrase for logging
            idx = page_text.find(phrase)
            snippet = page_text[max(0, idx-20):idx+80].strip()
            print(f"Away notice found: '...{snippet}...'")
            return {"status": "away", "phrase": phrase, "snippet": snippet}

    # No away notice found — seller is back
    # Try to grab the item title for the Discord message
    title_tag = soup.find("h1", {"class": re.compile(r"x-item-title", re.I)})
    if not title_tag:
        title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else f"Item {ITEM_ID}"

    return {"status": "back", "title": title}


def send_discord_alert(title):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set — skipping Discord ping")
        return

    msg = (
        f"**Seller is BACK!** Time to buy!\n\n"
        f"**{title}**\n"
        f"{ITEM_URL}\n\n"
        f"_(This monitor will now stop sending alerts)_"
    )
    payload = {"content": msg, "username": "eBay Seller Monitor"}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    if r.status_code in (200, 204):
        print("Discord ping sent!")
    else:
        print(f"Discord error: {r.status_code} {r.text}")


def main():
    if already_alerted():
        print("Already alerted — seller was back as of last check. Remove seller_alerted.flag to re-enable.")
        return

    result = check_listing()
    print(f"Result: {json.dumps(result, indent=2)}")

    if result["status"] == "back":
        send_discord_alert(result.get("title", f"Item {ITEM_ID}"))
        mark_alerted()
        print("Flag written — won't ping again unless flag is deleted.")
    elif result["status"] == "ended":
        print("Listing ended or removed — sending one-time alert.")
        send_discord_alert(f"Item {ITEM_ID} listing has ENDED (may have sold or been removed)")
        mark_alerted()
    elif result["status"] == "away":
        print("Seller still away — no ping.")
    else:
        print(f"Check failed: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
