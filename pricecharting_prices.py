"""
Fetches Pokemon card prices from PriceCharting API for each card in Cards_I_Care_About.txt
Get a free API token instantly at: https://www.pricecharting.com/api
"""

import requests
import os

# --- CONFIG ---
PC_TOKEN = os.environ.get("PC_TOKEN", "YOUR_TOKEN_HERE")
CARDS_FILE = "Cards_I_Care_About.txt"
API_URL = "https://www.pricecharting.com/api/products"


def load_cards(filepath: str) -> list[str]:
    cards = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                cards.append(line[2:].strip())
    return cards


def cents_to_dollars(cents) -> str:
    if cents is None or cents == 0:
        return "N/A"
    return f"${cents / 100:.2f}"


def fetch_price(card_name: str) -> dict | None:
    """Search PriceCharting and return the best matching product."""
    params = {
        "q": f"{card_name} pokemon",
        "token": PC_TOKEN,
    }
    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    products = data.get("products", [])
    if not products:
        return None

    # Return the top match
    return products[0]


def print_card_prices(card: str, product: dict | None):
    print(f"\n{'='*60}")
    print(f"  {card.upper()}")
    print(f"{'='*60}")

    if not product:
        print("  No results found on PriceCharting.")
        return

    name = product.get("product-name", "Unknown")
    console = product.get("console-name", "")
    pc_id = product.get("id", "")

    print(f"  Matched: {name} [{console}]")
    print(f"  PriceCharting: https://www.pricecharting.com/game/{pc_id}")
    print()
    print(f"  Ungraded:  {cents_to_dollars(product.get('loose-price'))}")
    print(f"  Graded:    {cents_to_dollars(product.get('graded-price'))}")
    print(f"  PSA 9:     {cents_to_dollars(product.get('psa-9-price'))}")
    print(f"  PSA 10:    {cents_to_dollars(product.get('psa-10-price'))}")


def main():
    if PC_TOKEN == "YOUR_TOKEN_HERE":
        print("ERROR: Set your PriceCharting API token.")
        print("  Option 1: export PC_TOKEN=your_token_here")
        print("  Option 2: edit PC_TOKEN in this script")
        print("  Get one free (instant) at: https://www.pricecharting.com/api")
        return

    cards = load_cards(CARDS_FILE)
    print(f"Fetching PriceCharting prices for {len(cards)} cards...")

    for card in cards:
        try:
            product = fetch_price(card)
            print_card_prices(card, product)
        except requests.RequestException as e:
            print(f"\nERROR fetching '{card}': {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
