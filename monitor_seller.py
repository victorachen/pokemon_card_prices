"""
monitor_seller.py — Checks eBay listing via Browse API (no scraping).
Pings Discord every hour with current status.
Sends a special "BACK!" alert (only once) when seller becomes purchasable.
"""

import os, sys, json, base64
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

EBAY_APP_ID         = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID        = os.environ.get("EBAY_CERT_ID", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SCOPE     = "https://api.ebay.com/oauth/api_scope"

ITEM_ID   = "157626935379"
# Browse API uses legacy item ID format: v1|<itemId>|0
ITEM_API_ID = f"v1|{ITEM_ID}|0"
ITEM_URL  = f"https://www.ebay.com/itm/{ITEM_ID}"
FLAG_FILE = "seller_alerted.flag"


# ── eBay OAuth ────────────────────────────────────────────────────────────────

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


# ── Flag helpers ──────────────────────────────────────────────────────────────

def already_alerted():
    return os.path.exists(FLAG_FILE)

def mark_alerted():
    with open(FLAG_FILE, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


# ── Check listing via Browse API ──────────────────────────────────────────────

def check_listing() -> dict:
    print(f"Checking item {ITEM_ID} via Browse API...")

    try:
        token = get_ebay_token()
    except Exception as e:
        print(f"OAuth error: {e}")
        return {"status": "error", "error": f"OAuth failed: {e}"}

    url = f"https://api.ebay.com/buy/browse/v1/item/{ITEM_API_ID}"
    try:
        r = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            timeout=15,
        )
    except Exception as e:
        print(f"API error: {e}")
        return {"status": "error", "error": str(e)}

    print(f"HTTP {r.status_code}")

    # 404 = item hidden (seller on vacation) or genuinely ended.
    # We treat this as "away" since we know the seller is on vacation.
    # Once seller returns, the listing reappears and we get a 200.
    if r.status_code == 404:
        return {"status": "away_hidden"}

    if r.status_code != 200:
        body = r.text[:300]
        print(f"Unexpected response: {body}")
        return {"status": "error", "error": f"HTTP {r.status_code}: {body[:150]}"}

    data = r.json()
    title = data.get("title", f"Item {ITEM_ID}")
    price_val = data.get("price", {}).get("value", "?")
    price_cur = data.get("price", {}).get("currency", "USD")
    seller = data.get("seller", {}).get("username", "unknown")
    condition = data.get("condition", "unknown")

    # Check if item is purchasable
    # When seller is away, the item may show as not buyable or have
    # extended ship-to times. Key fields to check:
    buying_options = data.get("buyingOptions", [])
    ship_to_locations = data.get("shipToLocations", {})
    item_end_date = data.get("itemEndDate", "")

    # The "eligibleForInlineCheckout" or presence of "FIXED_PRICE"/"AUCTION"
    # in buyingOptions indicates the item can be purchased
    enabled = data.get("enabledForGuestCheckout", None)

    # Check for availability hints
    estimated_avail = data.get("estimatedAvailabilities", [])
    avail_status = None
    for ea in estimated_avail:
        avail_status = ea.get("availabilityThreshold", ea.get("estimatedAvailabilityStatus", None))

    # Build info dict
    info = {
        "title": title,
        "price": f"{price_val} {price_cur}",
        "seller": seller,
        "condition": condition,
        "buyingOptions": buying_options,
        "guestCheckout": enabled,
        "estimatedAvail": estimated_avail,
    }
    print(json.dumps(info, indent=2))

    # If the item is active and has buying options, seller is available
    if buying_options:
        return {"status": "back", "title": title, "price": f"{price_val} {price_cur}", "info": info}
    else:
        # No buying options = likely unavailable (seller away / vacation)
        return {"status": "away", "info": info}


# ── Discord ───────────────────────────────────────────────────────────────────

def send_discord(msg):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL -- skipping")
        return
    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": msg, "username": "eBay Seller Monitor"},
        timeout=10,
    )
    print(f"Discord: {r.status_code}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Preflight
    missing = []
    if not EBAY_APP_ID:  missing.append("EBAY_APP_ID")
    if not EBAY_CERT_ID: missing.append("EBAY_CERT_ID")
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    result = check_listing()
    print(f"\nResult: {result['status']}")

    if result["status"] == "back":
        if not already_alerted():
            send_discord(
                f"\U0001f7e2 **SELLER IS BACK -- BUY NOW!** ({now})\n"
                f"**{result['title']}**\n"
                f"Price: {result.get('price', '?')}\n"
                f"{ITEM_URL}"
            )
            mark_alerted()
            print("Flag written.")
        else:
            send_discord(
                f"\u2705 **Seller active** ({now})\n"
                f"**{result.get('title', ITEM_ID)}** | {result.get('price', '?')}\n"
                f"{ITEM_URL}"
            )

    elif result["status"] in ("away", "away_hidden"):
        send_discord(
            f"\u23f0 **Seller still away** ({now})\n"
            f"Listing hidden from API (vacation mode)\n"
            f"{ITEM_URL}"
        )

    elif result["status"] == "error":
        send_discord(
            f"\u26a0\ufe0f **Check failed** ({now}): {result.get('error', 'unknown')}\n"
            f"{ITEM_URL}"
        )


if __name__ == "__main__":
    main()
