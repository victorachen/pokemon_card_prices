"""
Fetches last 10 eBay sold prices for each card in Cards_I_Care_About.txt
Uses eBay Finding API (free, just needs an App ID from developer.ebay.com)
"""

import requests
import json
import os
from datetime import datetime

# --- CONFIG ---
EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "YOUR_APP_ID_HERE")
CARDS_FILE = "Cards_I_Care_About.txt"
FINDING_API_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
POKEMON_CATEGORY_ID = "2536"  # Pokemon Individual Cards
RESULTS_PER_CARD = 10


def load_cards(filepath: str) -> list[str]:
    cards = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                cards.append(line[2:].strip())
    return cards


def fetch_sold_prices(card_name: str) -> list[dict]:
    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": EBAY_APP_ID,
        "RESPONSE-DATA-FORMAT": "JSON",
        "keywords": f"{card_name} pokemon card",
        "categoryId": POKEMON_CATEGORY_ID,
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "sortOrder": "EndTimeSoonest",
        "paginationInput.entriesPerPage": str(RESULTS_PER_CARD),
        "outputSelector": "SellerInfo",
    }

    response = requests.get(FINDING_API_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    search_result = data.get("findCompletedItemsResponse", [{}])[0]
    items = (
        search_result.get("searchResult", [{}])[0]
        .get("item", [])
    )

    results = []
    for item in items:
        price_info = item.get("sellingStatus", [{}])[0]
        sold_price = price_info.get("currentPrice", [{}])[0].get("__value__", "N/A")
        currency = price_info.get("currentPrice", [{}])[0].get("@currencyId", "USD")
        end_time = item.get("listingInfo", [{}])[0].get("endTime", ["N/A"])[0]
        title = item.get("title", ["N/A"])[0]
        item_url = item.get("viewItemURL", ["N/A"])[0]

        # Parse and reformat the date
        try:
            dt = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%fZ")
            end_time = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        results.append({
            "title": title,
            "price": f"{currency} {float(sold_price):.2f}",
            "sold_date": end_time,
            "url": item_url,
        })

    return results


def print_results(card: str, sales: list[dict]):
    print(f"\n{'='*60}")
    print(f"  {card.upper()}")
    print(f"{'='*60}")
    if not sales:
        print("  No recent sold listings found.")
        return
    for i, sale in enumerate(sales, 1):
        print(f"  {i:>2}. {sale['price']}  ({sale['sold_date']})")
        print(f"      {sale['title'][:70]}")
        print(f"      {sale['url']}")

    prices = [float(s["price"].split()[-1]) for s in sales]
    avg = sum(prices) / len(prices)
    print(f"\n  Avg of last {len(prices)}: ${avg:.2f} | "
          f"Low: ${min(prices):.2f} | High: ${max(prices):.2f}")


def main():
    if EBAY_APP_ID == "YOUR_APP_ID_HERE":
        print("ERROR: Set your eBay App ID.")
        print("  Option 1: export EBAY_APP_ID=your_id_here")
        print("  Option 2: edit the EBAY_APP_ID variable in this script")
        print("  Get one free at: https://developer.ebay.com")
        return

    cards = load_cards(CARDS_FILE)
    print(f"Fetching eBay sold prices for {len(cards)} cards...\n")

    for card in cards:
        try:
            sales = fetch_sold_prices(card)
            print_results(card, sales)
        except requests.RequestException as e:
            print(f"\nERROR fetching {card}: {e}")


if __name__ == "__main__":
    main()
