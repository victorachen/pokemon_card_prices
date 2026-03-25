"""
deal_finder.py — Scans eBay for PSA 8/9/10 listings and sends a Discord alert
when a listing is significantly below the current market median for that grade.

Market medians come from watchlist_data.json (built by fetch_watchlist_prices.py).
Run the fetch script first, then run this whenever you want to check for deals.

Usage:
    python deal_finder.py            # scan and send Discord alerts
    python deal_finder.py --dry-run  # scan and print deals without alerting
"""

import os, sys, json, sqlite3, base64
from datetime import datetime, timezone, timedelta
from statistics import median

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

EBAY_APP_ID         = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID        = os.environ.get("EBAY_CERT_ID", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

EBAY_TOKEN_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE      = "https://api.ebay.com/oauth/api_scope"

WATCHLIST_FILE  = "watchlist_data.json"
DB_FILE         = "prices.db"
DEAL_THRESHOLD  = 0.25   # alert when listing is 25%+ below market median
MIN_LISTINGS    = 2      # need at least this many stored listings to compute a reliable median
MIN_PRICE       = 5.00
DRY_RUN         = "--dry-run" in sys.argv

GRADES = [
    ("psa8",  "8"),
    ("psa9",  "9"),
    ("psa10", "10"),
]


# ── Database ───────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts_sent (
            item_id    TEXT PRIMARY KEY,
            card_name  TEXT,
            grade      TEXT,
            alerted_at TEXT
        )
    """)
    conn.commit()
    return conn

def already_alerted(conn: sqlite3.Connection, item_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM alerts_sent WHERE item_id = ?", (item_id,)
    ).fetchone() is not None

def mark_alerted(conn: sqlite3.Connection, item_id: str, card_name: str, grade: str):
    conn.execute(
        "INSERT OR IGNORE INTO alerts_sent (item_id, card_name, grade, alerted_at) VALUES (?,?,?,?)",
        (item_id, card_name, grade, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    )
    conn.commit()


# ── eBay OAuth ─────────────────────────────────────────────────────────────────

_token_cache: dict = {}

def get_ebay_token() -> str:
    now = datetime.now(timezone.utc)
    if _token_cache.get("token") and _token_cache.get("expires_at", now) > now:
        return _token_cache["token"]
    creds = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    r = requests.post(
        EBAY_TOKEN_URL,
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": EBAY_SCOPE},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + timedelta(seconds=data.get("expires_in", 7200) - 60)
    return _token_cache["token"]


# ── eBay search ────────────────────────────────────────────────────────────────

def search_ebay(token: str, query: str,
                required_in_title: list[str] | None = None, n: int = 15) -> list[dict]:
    try:
        r = requests.get(
            EBAY_BROWSE_URL,
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
            params={"q": query, "sort": "price", "limit": str(n * 3)},
            timeout=15,
        )
        r.raise_for_status()
        items = r.json().get("itemSummaries", [])
    except requests.RequestException as e:
        print(f"    eBay error: {e}")
        return []

    results = []
    for item in items:
        price_info = item.get("price", {})
        if price_info.get("currency") != "USD":
            continue
        try:
            price = float(price_info["value"])
        except (KeyError, ValueError):
            continue
        if price < MIN_PRICE:
            continue
        title = item.get("title", "")
        if required_in_title:
            tl = title.lower()
            if not all(req.lower() in tl for req in required_in_title):
                continue
        results.append({
            "item_id": item.get("itemId", ""),
            "price":   price,
            "title":   title[:120],
            "url":     item.get("itemWebUrl", ""),
            "type":    "AUCTION" if "AUCTION" in item.get("buyingOptions", []) else "BIN",
        })
        if len(results) >= n:
            break
    return results


# ── Discord alert ──────────────────────────────────────────────────────────────

def send_discord_alert(card_name: str, grade_label: str, listing: dict,
                       price: float, ref_median: float, discount_pct: float):
    embed = {
        "title":  f"Deal: {card_name} PSA {grade_label}",
        "color":  0x5B4DE8,
        "fields": [
            {"name": "Listed Price",   "value": f"**${price:.2f}** ({listing['type']})", "inline": True},
            {"name": "Market Median",  "value": f"${ref_median:.2f}",                    "inline": True},
            {"name": "Discount",       "value": f"**{discount_pct:.0f}% below median**", "inline": True},
            {"name": "Title",          "value": listing["title"][:200],                  "inline": False},
        ],
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "footer":    {"text": "Pokemon Deal Finder"},
    }
    if listing.get("url"):
        embed["url"] = listing["url"]
        embed["fields"].append(
            {"name": "eBay Link", "value": f"[View listing]({listing['url']})", "inline": True}
        )
    payload = {
        "content": (f"Deal alert: **{card_name} PSA {grade_label}** at ${price:.2f} "
                    f"({discount_pct:.0f}% below ${ref_median:.2f} market median)"),
        "embeds": [embed],
    }
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    r.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # Credential check
    missing = []
    if not EBAY_APP_ID:  missing.append("EBAY_APP_ID")
    if not EBAY_CERT_ID: missing.append("EBAY_CERT_ID")
    if not DISCORD_WEBHOOK_URL and not DRY_RUN:
        missing.append("DISCORD_WEBHOOK_URL")
    if missing:
        print(f"ERROR: Missing in .env: {', '.join(missing)}")
        return

    # Load watchlist (market reference + search queries)
    if not os.path.exists(WATCHLIST_FILE):
        print(f"ERROR: {WATCHLIST_FILE} not found.")
        print("Run: python fetch_watchlist_prices.py")
        return
    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        wl = json.load(f)

    updated = wl.get("last_updated", "unknown")
    print(f"Loaded {WATCHLIST_FILE}  (data from {updated})")

    print("Getting eBay token...", end=" ", flush=True)
    try:
        token = get_ebay_token()
        print("OK\n")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    if DRY_RUN:
        print("DRY RUN — deals will be printed but not sent to Discord\n")

    conn = get_db()
    deals_found = 0
    skipped_no_data = 0

    for card in wl["cards"]:
        card_name   = card["name"]
        graded_q    = card.get("graded_q", "")
        req         = card.get("required_in_title")
        medians     = card.get("market_medians", {})

        for grade_key, grade_num in GRADES:
            ref_median = medians.get(grade_key)

            if ref_median is None:
                skipped_no_data += 1
                continue

            stored_count = len(card.get("ebay", {}).get(grade_key, []))
            if stored_count < MIN_LISTINGS:
                # Not enough comparable data — don't generate noisy alerts
                skipped_no_data += 1
                continue

            q = f"{graded_q} PSA {grade_num}"
            print(f"  {card_name} PSA {grade_num}  (median ${ref_median:.2f}, {stored_count} stored)...",
                  end=" ", flush=True)

            listings = search_ebay(token, q, required_in_title=req)
            card_deals = 0

            for listing in listings:
                if not listing["item_id"]:
                    continue
                if already_alerted(conn, listing["item_id"]):
                    continue

                price    = listing["price"]
                discount = (ref_median - price) / ref_median

                if discount < DEAL_THRESHOLD:
                    continue

                # It's a deal
                deals_found += 1
                card_deals  += 1
                discount_pct = discount * 100

                print()  # newline after the "..." line
                print(f"    DEAL: ${price:.2f} — {discount_pct:.0f}% below median")
                print(f"    {listing['title'][:70]}")
                print(f"    {listing['url']}")

                if not DRY_RUN:
                    try:
                        send_discord_alert(card_name, grade_num, listing,
                                           price, ref_median, discount_pct)
                        mark_alerted(conn, listing["item_id"], card_name, grade_key)
                        print(f"    Discord alert sent")
                    except requests.RequestException as e:
                        print(f"    Discord failed: {e}")
                else:
                    mark_alerted(conn, listing["item_id"], card_name, grade_key)

            if card_deals == 0:
                print(f"no deals ({len(listings)} checked)")

    conn.close()
    print(f"\n{'─'*55}")
    print(f"  Deals found:  {deals_found}")
    print(f"  Skipped (no market data): {skipped_no_data}")
    print(f"  Threshold:    {DEAL_THRESHOLD*100:.0f}% below median")
    if deals_found and DRY_RUN:
        print(f"\n  Re-run without --dry-run to send Discord alerts.")


if __name__ == "__main__":
    main()
