"""
fetch_watchlist_prices.py — Fetches current eBay listings and TCGPlayer prices
for all watchlist cards. Saves results to watchlist_data.json.

The site reads watchlist_data.json statically — no API credentials in the browser.
Run this locally whenever you want fresh data, then commit + push to update the site.

Usage:
    python fetch_watchlist_prices.py
"""

import os, json, base64, time, requests
from datetime import datetime, timezone, timedelta
from statistics import median as _median
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

EBAY_APP_ID  = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "")

EBAY_TOKEN_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE      = "https://api.ebay.com/oauth/api_scope"
PTCG_API_URL    = "https://api.pokemontcg.io/v2/cards"

RESULTS_PER_GRADE = 8   # listings to store per grade (median of these used for deal detection)

# ── Watchlist definition ───────────────────────────────────────────────────────
# raw_q    : eBay query for ungraded copies (excludes grading company keywords)
# graded_q : base eBay query for graded copies (PSA grade number appended at runtime)
# tcg_name : card name for pokemontcg.io search
# tcg_set  : pokemontcg.io set ID
# tcg_rev  : True if this is the reverse holo variant

WATCHLIST = [
    {
        "label":    "Charizard Crystal Guardians (Rev)",
        "language": "English",
        "raw_q":    "Charizard Crystal Guardians reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Charizard Crystal Guardians reverse -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["charizard", "crystal"],
        "tcg_name": "Charizard", "tcg_set": "ex14", "tcg_rev": True,
    },
    {
        "label":    "Gyarados Holon Phantoms (Rev)",
        "language": "English",
        "raw_q":    "Gyarados Holon Phantoms reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Gyarados Holon Phantoms -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["gyarados", "holon"],
        "tcg_name": "Gyarados", "tcg_set": "ex13", "tcg_rev": True,
    },
    {
        "label":    "Meowth Holon Phantoms (Rev)",
        "language": "English",
        "raw_q":    "Meowth Holon Phantoms reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Meowth Holon Phantoms -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["meowth", "holon"],
        "tcg_name": "Meowth", "tcg_set": "ex13", "tcg_rev": True,
    },
    {
        "label":    "Gloom Holon Phantoms (Rev)",
        "language": "English",
        "raw_q":    "Gloom Holon Phantoms reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Gloom Holon Phantoms -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["gloom", "holon"],
        "tcg_name": "Gloom", "tcg_set": "ex13", "tcg_rev": True,
    },
    {
        "label":    "Salamence ex Dragon Frontiers",
        "language": "English",
        "raw_q":    "Salamence ex Dragon Frontiers -reverse -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Salamence ex Dragon Frontiers -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["salamence", "frontier"],
        "tcg_name": "Salamence", "tcg_set": "ex15", "tcg_rev": False,
    },
    {
        "label":    "Feraligatr Dragon Frontiers (Rev)",
        "language": "English",
        "raw_q":    "Feraligatr Dragon Frontiers reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Feraligatr Dragon Frontiers reverse -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["feraligatr", "frontier"],
        "tcg_name": "Feraligatr", "tcg_set": "ex15", "tcg_rev": True,
    },
    {
        "label":    "Typhlosion Dragon Frontiers (Rev)",
        "language": "English",
        "raw_q":    "Typhlosion Dragon Frontiers reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Typhlosion Dragon Frontiers reverse -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["typhlosion", "frontier"],
        "tcg_name": "Typhlosion", "tcg_set": "ex15", "tcg_rev": True,
    },
    {
        "label":    "Dragonite Delta Species (Rev)",
        "language": "English",
        "raw_q":    "Dragonite Delta Species reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Dragonite Delta Species reverse -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["dragonite", "delta"],
        "tcg_name": "Dragonite", "tcg_set": "ex11", "tcg_rev": True,
    },
    {
        "label":    "Ampharos Dragon Frontiers (Rev)",
        "language": "English",
        "raw_q":    "Ampharos Dragon Frontiers reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Ampharos Dragon Frontiers reverse -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["ampharos", "frontier"],
        "tcg_name": "Ampharos", "tcg_set": "ex15", "tcg_rev": True,
    },
    {
        "label":    "Gardevoir ex Dragon Frontiers",
        "language": "English",
        "raw_q":    "Gardevoir ex Dragon Frontiers -reverse -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin -celebrations",
        "graded_q": "Gardevoir ex Dragon Frontiers -japanese -keychain -pin -lot -proxy -celebrations",
        "required_in_title": ["gardevoir", "frontier"],
        "tcg_name": "Gardevoir", "tcg_set": "ex15", "tcg_rev": False,
    },
    {
        "label":    "Vaporeon Delta Species (Rev)",
        "language": "English",
        "raw_q":    "Vaporeon Delta Species reverse holo -PSA -BGS -SGC -CGC -lot -proxy -japanese -keychain -pin",
        "graded_q": "Vaporeon Delta Species reverse -japanese -keychain -pin -lot -proxy",
        "required_in_title": ["vaporeon", "delta"],
        "tcg_name": "Vaporeon", "tcg_set": "ex11", "tcg_rev": True,
    },
    {
        "label":    "Vaporeon Holon Research Tower (JP)",
        "language": "Japanese",
        "raw_q":    "Vaporeon Holon Research Tower -PSA -BGS -SGC -CGC -lot -proxy -keychain -pin",
        "graded_q": "Vaporeon Holon Research Tower -keychain -pin -lot -proxy",
        "required_in_title": ["vaporeon"],
        "skip_tcg": True,   # Japanese exclusive set, not in pokemontcg.io
        "tcg_name": None, "tcg_set": None, "tcg_rev": False,
    },
]


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

def search_ebay(token: str, query: str, n: int = RESULTS_PER_GRADE,
                required_in_title: list[str] | None = None) -> list[dict]:
    """Returns up to n cheapest active eBay listings for the given query.

    required_in_title: all strings must appear (case-insensitive) in the listing
    title, or the result is discarded. Catches junk like wrong-card lots,
    keychains, and other false positives the query alone can't filter.
    """
    try:
        r = requests.get(
            EBAY_BROWSE_URL,
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
            params={"q": query, "sort": "price", "limit": str(n * 4)},
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
        if price < 1.00:
            continue
        title = item.get("title", "")
        if required_in_title:
            title_lower = title.lower()
            if not all(req.lower() in title_lower for req in required_in_title):
                continue
        options = item.get("buyingOptions", [])
        results.append({
            "price":      price,
            "type":       "AUCTION" if "AUCTION" in options else "FIXED_PRICE",
            "best_offer": "BEST_OFFER" in options,
            "title":      title[:120],
            "url":        item.get("itemWebUrl", ""),
        })
        if len(results) >= n:
            break
    return results


# ── TCGPlayer price via pokemontcg.io ─────────────────────────────────────────

def get_tcgplayer_price(name: str, set_id: str, is_rev: bool) -> tuple[float | None, float | None, str | None]:
    """Returns (market_price_usd, low_price_usd, tcgplayer_url) for a card."""
    try:
        r = requests.get(
            PTCG_API_URL,
            params={"q": f'name:"{name}" set.id:{set_id}', "select": "id,name,tcgplayer"},
            timeout=20,
        )
        r.raise_for_status()
        cards = r.json().get("data", [])
    except requests.RequestException as e:
        print(f"    pokemontcg.io error: {e}")
        return None, None, None

    if not cards:
        return None, None, None

    tcg    = cards[0].get("tcgplayer", {})
    prices = tcg.get("prices", {})
    if is_rev:
        p = prices.get("reverseHolofoil", {})
    else:
        p = prices.get("holofoil") or prices.get("normal") or {}

    market = p.get("market")
    low    = p.get("low")
    return (float(market) if market else None), (float(low) if low else None), tcg.get("url")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        print("ERROR: Missing EBAY_APP_ID or EBAY_CERT_ID in .env")
        return

    print("Getting eBay token...", end=" ", flush=True)
    try:
        token = get_ebay_token()
        print("OK\n")
    except Exception as e:
        print(f"FAILED: {e}")
        return

    results = []

    for i, card in enumerate(WATCHLIST, 1):
        print(f"[{i}/{len(WATCHLIST)}] {card['label']}")

        # TCGPlayer reference price
        if card.get("skip_tcg"):
            print(f"  TCGPlayer... skipped (Japanese exclusive set)")
            tcg_market, tcg_low, tcg_url = None, None, None
        else:
            print(f"  TCGPlayer (pokemontcg.io)...", end=" ", flush=True)
            tcg_market, tcg_low, tcg_url = get_tcgplayer_price(card["tcg_name"], card["tcg_set"], card["tcg_rev"])
            print(f"${tcg_market:.2f}" if tcg_market else "no data")

        req = card.get("required_in_title")

        # eBay: graded
        ebay_data: dict[str, list] = {}
        for grade_key, grade_num in [("psa9", "9"), ("psa10", "10"), ("psa8", "8")]:
            q = f"{card['graded_q']} PSA {grade_num}"
            print(f"  PSA {grade_num}...", end=" ", flush=True)
            listings = search_ebay(token, q, required_in_title=req)
            n = len(listings)
            low = f" · from ${listings[0]['price']:.2f}" if listings else ""
            print(f"{n} found{low}")
            ebay_data[grade_key] = listings
            time.sleep(0.3)

        # eBay: raw (any condition)
        print(f"  Raw eBay (any)...", end=" ", flush=True)
        raw = search_ebay(token, card["raw_q"], required_in_title=req)
        n   = len(raw)
        low_str = f" · from ${raw[0]['price']:.2f}" if raw else ""
        print(f"{n} found{low_str}")
        ebay_data["raw"] = raw
        time.sleep(0.3)

        # eBay: raw NM/LP only
        nm_q = card["raw_q"].replace("-PSA", "NM -PSA", 1) + " -damaged -HP -MP"
        print(f"  Raw NM/LP...", end=" ", flush=True)
        raw_nm = search_ebay(token, nm_q, required_in_title=req)
        n      = len(raw_nm)
        low_str = f" · from ${raw_nm[0]['price']:.2f}" if raw_nm else ""
        print(f"{n} found{low_str}")
        ebay_data["raw_nm"] = raw_nm
        time.sleep(0.3)

        # PSA 9 vs NM raw delta
        psa9_prices   = [l["price"] for l in ebay_data.get("psa9", [])]
        raw_nm_prices = [l["price"] for l in raw_nm]
        if len(psa9_prices) >= 1 and len(raw_nm_prices) >= 1:
            psa9_med   = _median(psa9_prices)
            raw_nm_med = _median(raw_nm_prices)
            delta_usd  = round(psa9_med - raw_nm_med, 2)
            delta_pct  = round((delta_usd / raw_nm_med) * 100, 1) if raw_nm_med else None
        else:
            delta_usd = delta_pct = None

        # Compute market medians per grade (used by deal_finder.py)
        market_medians = {}
        for g in ["psa8", "psa9", "psa10"]:
            prices = [l["price"] for l in ebay_data.get(g, [])]
            market_medians[g] = round(_median(prices), 2) if prices else None

        results.append({
            "name":              card["label"],
            "language":          card.get("language", "English"),
            "graded_q":          card["graded_q"],
            "required_in_title": card.get("required_in_title"),
            "tcgplayer_market":  tcg_market,
            "tcgplayer_low":     tcg_low,
            "tcgplayer_url":     tcg_url,
            "delta_usd":         delta_usd,
            "delta_pct":         delta_pct,
            "market_medians":    market_medians,
            "ebay":              ebay_data,
        })
        print()

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "cards":        results,
    }

    with open("watchlist_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_listings = sum(len(c['ebay'].get(g, [])) for c in results for g in ['psa8','psa9','psa10','raw'])
    print(f"Saved watchlist_data.json  ({len(results)} cards, {total_listings} total listings)")
    print("\nNext: git add watchlist_data.json && git push   (GitHub Pages auto-deploys)")


if __name__ == "__main__":
    main()
