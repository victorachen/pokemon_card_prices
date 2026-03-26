"""
pc_last_sold.py — Fetch the last 5 sold data points from PriceCharting for chase cards.

Fill in the WATCHLIST URLs below with your exact PriceCharting links, then run:
    python pc_last_sold.py

If you get 403 errors, run with --playwright flag (needs: pip install playwright && playwright install chromium):
    python pc_last_sold.py --playwright
"""

import sys
import time
import re
import requests
from bs4 import BeautifulSoup

# ─── Fill in your exact PriceCharting URLs here ───────────────────────────────
WATCHLIST = {
    "Charizard CG Rev Holo":       "https://www.pricecharting.com/game/pokemon-crystal-guardians/charizard-reverse-holo-4",
    "Charizard CG Holo":           "",   # e.g. .../charizard-4
    "Gyarados HP Rev Holo":        "",   # e.g. .../gyarados-reverse-holo-9
    "Gyarados HP Holo":            "",
    "Dragonite DS Rev Holo":       "",
    "Dragonite DS Holo":           "",
    "Feraligatr DF Rev Holo":      "",
    "Typhlosion DF Rev Holo":      "",
    "Salamence ex DF":             "",
    "Ampharos DF Rev Holo":        "",
    "Gardevoir ex DF":             "",
    "Meowth HP Rev Holo":          "",
    "Gloom HP Rev Holo":           "",
    "Vaporeon DS Rev Holo":        "",
    "Vaporeon JP #030":            "",   # japanese promo — may not be on PC
}
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

USE_PLAYWRIGHT = "--playwright" in sys.argv


def parse_sales(html: str) -> list[dict]:
    """Extract last-sold rows from a PriceCharting card page."""
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. Try the completed-auctions table (most reliable) ──────────────────
    table = (
        soup.find("table", id="completed-auctions")
        or soup.find("table", id="sold_list")
        or soup.find("table", {"class": re.compile(r"sold|completed", re.I)})
    )

    # ── 2. Fallback: any table whose header row mentions "price" ─────────────
    if not table:
        for t in soup.find_all("table"):
            header_text = t.find("tr").get_text(" ").lower() if t.find("tr") else ""
            if "price" in header_text or "sold" in header_text:
                table = t
                break

    if not table:
        return []

    # Parse header row to map column positions
    header_row = table.find("tr")
    headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

    def col(keyword):
        for i, h in enumerate(headers):
            if keyword in h:
                return i
        return None

    date_col   = col("date")
    price_col  = col("price")
    title_col  = col("title") or col("name") or col("listing")

    sales = []
    for row in table.find_all("tr")[1:6]:   # skip header, grab up to 5
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        def cell_text(idx):
            if idx is not None and idx < len(cells):
                return cells[idx].get_text(strip=True)
            return ""

        # Fallback: scan all cells for a dollar amount if col mapping fails
        price = cell_text(price_col)
        if not price:
            for c in cells:
                t = c.get_text(strip=True)
                if re.match(r"\$[\d,]+\.?\d*", t):
                    price = t
                    break

        entry = {
            "date":  cell_text(date_col),
            "price": price,
            "title": cell_text(title_col),
        }
        # Only include rows that have at least a price
        if entry["price"]:
            sales.append(entry)

    return sales


def fetch_requests(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def fetch_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        html = page.content()
        browser.close()
        return html


def main():
    active = {name: url for name, url in WATCHLIST.items() if url.strip()}
    if not active:
        print("No URLs filled in yet — add PriceCharting links to the WATCHLIST dict.")
        return

    fetcher = fetch_playwright if USE_PLAYWRIGHT else fetch_requests
    mode = "Playwright" if USE_PLAYWRIGHT else "requests"
    print(f"\n{'═'*56}")
    print(f"  PriceCharting Last Sold  [{mode} mode]")
    print(f"{'═'*56}\n")

    for name, url in active.items():
        print(f"▸ {name}")
        try:
            html  = fetcher(url)
            sales = parse_sales(html)
        except Exception as e:
            print(f"  ERROR: {e}")
            if "403" in str(e) and not USE_PLAYWRIGHT:
                print("  → Try again with: python pc_last_sold.py --playwright")
            print()
            continue

        if not sales:
            print("  No sales data parsed — the page selector may need adjustment.")
            print("  (Try running with --debug flag to dump the raw HTML for inspection)")
        else:
            print(f"  {'DATE':<16}  {'PRICE':<10}  TITLE")
            print(f"  {'-'*14}  {'-'*8}  {'-'*30}")
            for s in sales:
                print(f"  {s['date']:<16}  {s['price']:<10}  {s['title'][:50]}")
        print()
        time.sleep(0.8)   # polite crawl delay


if __name__ == "__main__":
    main()
