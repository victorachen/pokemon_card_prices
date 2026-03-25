"""
deal_finder.py — Scans eBay active listings and sends a Discord alert when a card
is listed at least DEAL_THRESHOLD below its TCGPlayer market price (via pokemontcg.io).

Requires in .env:
  EBAY_APP_ID         — eBay App ID     (you have this)
  EBAY_CERT_ID        — eBay Cert ID    (same keyset on developer.ebay.com)
  DISCORD_WEBHOOK_URL — webhook URL from your Discord channel settings

Usage:
  python deal_finder.py            # scan and send Discord alerts
  python deal_finder.py --dry-run  # scan and print deals without sending alerts
"""

import os
import sys
import sqlite3
import base64
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

EBAY_APP_ID         = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID        = os.environ.get("EBAY_CERT_ID", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

CARDS_FILE     = "Cards_I_Care_About.txt"
DB_FILE        = "prices.db"
DEAL_THRESHOLD = 0.20          # alert when listed price is 20%+ below fair value
MIN_PRICE      = 2.00          # ignore listings under $2 (junk/lot remnants)

EBAY_TOKEN_URL   = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL  = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE       = "https://api.ebay.com/oauth/api_scope"
PTCG_API_URL     = "https://api.pokemontcg.io/v2/cards"
POKEMON_CATEGORY = "2536"

# Map set name keywords (from Cards_I_Care_About.txt) → pokemontcg.io set IDs
SET_ID_MAP = {
    "crystal guardians": "ex14",
    "holon phantoms":    "ex13",
    "delta species":     "ex11",
    "dragon frontiers":  "ex15",
}

DRY_RUN = "--dry-run" in sys.argv


# ── Database (just for dedup — don't re-alert same listing) ───────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts_sent (
            item_id    TEXT PRIMARY KEY,
            card_name  TEXT,
            alerted_at TEXT
        )
    """)
    conn.commit()
    return conn


def already_alerted(conn: sqlite3.Connection, item_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM alerts_sent WHERE item_id = ?", (item_id,)
    ).fetchone() is not None


def mark_alerted(conn: sqlite3.Connection, item_id: str, card_name: str):
    conn.execute(
        "INSERT OR IGNORE INTO alerts_sent (item_id, card_name, alerted_at) VALUES (?, ?, ?)",
        (item_id, card_name, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    )
    conn.commit()


# ── eBay OAuth ────────────────────────────────────────────────────────────────

_token_cache: dict = {}


def get_ebay_token() -> str:
    now = datetime.now(timezone.utc)
    if _token_cache.get("token") and _token_cache.get("expires_at", now) > now:
        return _token_cache["token"]

    creds = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    resp = requests.post(
        EBAY_TOKEN_URL,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": EBAY_SCOPE},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + timedelta(seconds=data.get("expires_in", 7200) - 60)
    return _token_cache["token"]


# ── eBay active listings ──────────────────────────────────────────────────────

JUNK_TERMS = ["-lot", "-proxy", "-custom", "-japanese", "-reprint",
              "-damaged", "-\"heavily played\"", "-\"poor condition\""]


def get_active_listings(card_name: str, token: str) -> list[dict]:
    q = f"{card_name} pokemon card " + " ".join(JUNK_TERMS)
    resp = requests.get(
        EBAY_BROWSE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        },
        params={
            "q": q,
            "category_ids": POKEMON_CATEGORY,
            "limit": "50",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("itemSummaries", [])


def parse_price(item: dict) -> float | None:
    price_info = item.get("price", {})
    if price_info.get("currency") != "USD":
        return None
    try:
        return float(price_info["value"])
    except (KeyError, ValueError):
        return None


# ── TCGPlayer fair value (via pokemontcg.io) ──────────────────────────────────

_tcg_cache: dict = {}


def parse_card_entry(raw: str) -> tuple[str, str | None, bool]:
    """
    Parses a line from Cards_I_Care_About.txt.
    Returns (card_name, set_id_or_None, is_reverse_holo).
    Example: "Charizard crystal guardians (reverse)" → ("Charizard", "ex14", True)
    """
    line = raw.strip().lower()
    is_reverse = "(reverse)" in line
    line = line.replace("(reverse)", "").strip()

    set_id = None
    card_name = line
    for keyword, sid in SET_ID_MAP.items():
        if keyword in line:
            set_id = sid
            card_name = line.replace(keyword, "").strip()
            break

    return card_name.title(), set_id, is_reverse


def get_fair_value(raw_card_entry: str) -> tuple[float | None, str | None]:
    """
    Returns (fair_value_usd, tcgplayer_url) for a card.
    Uses TCGPlayer market price from pokemontcg.io.
    """
    if raw_card_entry in _tcg_cache:
        return _tcg_cache[raw_card_entry]

    card_name, set_id, is_reverse = parse_card_entry(raw_card_entry)

    query = f'name:"{card_name}"'
    if set_id:
        query += f' set.id:{set_id}'

    resp = requests.get(
        PTCG_API_URL,
        params={"q": query, "select": "id,name,tcgplayer,set"},
        timeout=10,
    )
    resp.raise_for_status()
    cards = resp.json().get("data", [])

    if not cards:
        _tcg_cache[raw_card_entry] = (None, None)
        return None, None

    card = cards[0]
    tcgplayer = card.get("tcgplayer", {})
    prices = tcgplayer.get("prices", {})

    if is_reverse:
        price_data = prices.get("reverseHolofoil") or prices.get("reverseHolofoil", {})
    else:
        price_data = prices.get("holofoil") or prices.get("normal") or {}

    market = price_data.get("market")
    fair_value = float(market) if market else None
    url = tcgplayer.get("url")

    _tcg_cache[raw_card_entry] = (fair_value, url)
    return fair_value, url


# ── Discord alert ─────────────────────────────────────────────────────────────

def send_discord_alert(card_name: str, listing: dict, listing_price: float,
                       fair_value: float, pc_url: str | None):
    discount_pct = (fair_value - listing_price) / fair_value * 100
    title = listing.get("title", "")
    item_url = listing.get("itemWebUrl", "")
    listing_type = "AUCTION" if "AUCTION" in listing.get("buyingOptions", []) else "BIN"

    # Build Discord embed
    embed = {
        "title": f"Deal on {card_name}",
        "color": 0x2ECC71,  # green
        "fields": [
            {"name": "Listed Price", "value": f"**${listing_price:.2f}** ({listing_type})", "inline": True},
            {"name": "Fair Value (TCGPlayer)", "value": f"${fair_value:.2f}", "inline": True},
            {"name": "Discount", "value": f"**{discount_pct:.0f}% below fair value**", "inline": True},
            {"name": "Title", "value": title[:200], "inline": False},
        ],
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "footer": {"text": "Pokemon Deal Finder"},
    }

    if item_url:
        embed["url"] = item_url
        embed["fields"].append({"name": "eBay Link", "value": f"[View listing]({item_url})", "inline": True})
    if pc_url:
        embed["fields"].append({"name": "TCGPlayer", "value": f"[Fair value reference]({pc_url})", "inline": True})

    payload = {
        "content": f"🔔 **{card_name}** listed at ${listing_price:.2f} ({discount_pct:.0f}% below TCGPlayer market)",
        "embeds": [embed],
    }

    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


# ── Main ──────────────────────────────────────────────────────────────────────

def load_cards() -> list[str]:
    cards = []
    with open(CARDS_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                cards.append(line[2:].strip())
    return cards


def check_credentials() -> bool:
    missing = []
    if not EBAY_APP_ID:   missing.append("EBAY_APP_ID")
    if not EBAY_CERT_ID:  missing.append("EBAY_CERT_ID")
    if not DISCORD_WEBHOOK_URL and not DRY_RUN:
        missing.append("DISCORD_WEBHOOK_URL")
    if missing:
        print(f"ERROR: Missing in .env: {', '.join(missing)}")
        return False
    return True


def main():
    if not check_credentials():
        return

    if DRY_RUN:
        print("DRY RUN — deals will be printed but not sent to Discord\n")

    print("Getting eBay token...", end=" ", flush=True)
    try:
        token = get_ebay_token()
        print("OK")
    except requests.RequestException as e:
        print(f"FAILED: {e}")
        return

    cards = load_cards()
    conn  = get_db()
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")

    deals_found = 0
    print(f"\nScanning {len(cards)} cards for deals (threshold: {DEAL_THRESHOLD*100:.0f}% below fair value)...\n")

    for card in cards:
        # 1. Get fair value from TCGPlayer via pokemontcg.io
        try:
            fair_value, tcg_url = get_fair_value(card)
        except requests.RequestException as e:
            print(f"  {card}: pokemontcg.io error — {e}")
            continue

        if not fair_value:
            print(f"  {card}: no TCGPlayer price found, skipping")
            continue

        # 2. Get active eBay listings
        try:
            listings = get_active_listings(card, token)
        except requests.RequestException as e:
            print(f"  {card}: eBay error — {e}")
            continue

        card_deals = 0
        for item in listings:
            listing_price = parse_price(item)
            if not listing_price or listing_price < MIN_PRICE:
                continue

            discount = (fair_value - listing_price) / fair_value
            if discount < DEAL_THRESHOLD:
                continue

            item_id = item.get("itemId", "")
            if already_alerted(conn, item_id):
                continue

            # It's a deal we haven't alerted on yet
            deals_found += 1
            card_deals  += 1
            discount_pct = discount * 100
            title = item.get("title", "")

            print(f"  DEAL: {card}")
            print(f"    Listed:     ${listing_price:.2f}")
            print(f"    Fair value: ${fair_value:.2f}")
            print(f"    Discount:   {discount_pct:.0f}%")
            print(f"    Title:      {title[:70]}")
            print(f"    Link:       {item.get('itemWebUrl', 'N/A')}")
            print()

            if not DRY_RUN:
                try:
                    send_discord_alert(card, item, listing_price, fair_value, tcg_url)
                    mark_alerted(conn, item_id, card)
                    print(f"    ✓ Discord alert sent")
                except requests.RequestException as e:
                    print(f"    ✗ Discord alert failed: {e}")
            else:
                mark_alerted(conn, item_id, card)

        if card_deals == 0:
            print(f"  {card}: TCGPlayer ${fair_value:.2f} — no deals (checked {len(listings)} listings)")

    conn.close()
    print(f"\n{'─'*50}")
    print(f"  Deals found: {deals_found}")
    print(f"  Run at: {now}")
    if deals_found and DRY_RUN:
        print(f"\n  Re-run without --dry-run to send Discord alerts.")


if __name__ == "__main__":
    main()
