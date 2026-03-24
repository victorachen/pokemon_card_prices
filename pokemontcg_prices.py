"""
Fetches Pokemon card prices from the Pokemon TCG API (pokemontcg.io)
Free, no API key required. Returns TCGPlayer market prices.
"""

import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

CARDS_FILE = "Cards_I_Care_About.txt"
API_URL = "https://api.pokemontcg.io/v2/cards"

# Confirmed set IDs from the Pokemon TCG API
SET_ID_MAP = {
    "crystal guardians": "ex14",
    "holon phantoms": "ex13",
    "dragon frontiers": "ex15",
    "delta species": "ex11",
}


def load_cards(filepath: str) -> list[dict]:
    cards = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("- "):
                continue
            entry = line[2:].strip()
            is_reverse = "(reverse)" in entry.lower()
            clean = entry.lower().replace("(reverse)", "").strip()

            set_key = None
            pokemon_name = clean
            for key in SET_ID_MAP:
                if key in clean:
                    set_key = key
                    pokemon_name = clean.replace(key, "").strip()
                    break

            cards.append({
                "raw": entry,
                "pokemon": pokemon_name,
                "set_id": SET_ID_MAP.get(set_key, ""),
                "is_reverse": is_reverse,
            })
    return cards


def fetch_card(pokemon: str, set_id: str) -> list[dict]:
    query = f'name:"{pokemon}"'
    if set_id:
        query += f" set.id:{set_id}"

    params = {"q": query, "select": "name,set,tcgplayer,number"}
    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json().get("data", [])


def get_prices(card: dict, is_reverse: bool):
    tcg = card.get("tcgplayer", {})
    prices = tcg.get("prices", {})
    url = tcg.get("url", "")

    if is_reverse and "reverseHolofoil" in prices:
        return prices["reverseHolofoil"], "Reverse Holo", url
    if "holofoil" in prices:
        return prices["holofoil"], "Holofoil", url
    if "normal" in prices:
        return prices["normal"], "Normal", url
    if prices:
        first_key = next(iter(prices))
        return prices[first_key], first_key, url
    return None, None, url


# TCGPlayer standard condition multipliers applied to market price
CONDITION_MULTIPLIERS = {
    "NM  (Near Mint)":        1.00,
    "LP  (Lightly Played)":   0.80,
    "MP  (Moderately Played)": 0.57,
    "HP  (Heavily Played)":   0.40,
}


def fmt(val) -> str:
    return "N/A" if val is None else f"${float(val):.2f}"


def print_card(entry: dict, results: list[dict]):
    print(f"\n{'='*60}")
    print(f"  {entry['raw'].upper()}")
    print(f"{'='*60}")

    if not results:
        print("  No results found.")
        return

    card = results[0]
    name = card.get("name", "?")
    set_info = card.get("set", {})
    set_name = set_info.get("name", "?")
    number = card.get("number", "?")
    total = set_info.get("printedTotal", "?")

    prices, price_type, url = get_prices(card, entry["is_reverse"])

    print(f"  Card #:    {number}/{total}")
    print(f"  Matched:   {name} — {set_name}")
    if price_type:
        print(f"  Type:      {price_type}")
    if url:
        print(f"  TCGPlayer: {url}")
    print()

    if prices:
        market = prices.get("market")
        print(f"  {'─'*36}")
        print(f"  {'Condition':<28} {'Est. Price':>10}")
        print(f"  {'─'*36}")
        for label, mult in CONDITION_MULTIPLIERS.items():
            if market:
                est = f"${float(market) * mult:.2f}"
            else:
                est = "N/A"
            print(f"  {label:<28} {est:>10}")
        print(f"  {'─'*36}")
        print(f"  {'Market (TCGPlayer avg)':<28} {fmt(market):>10}")
        print(f"  {'Low listed':<28} {fmt(prices.get('low')):>10}")
        print(f"  {'High listed':<28} {fmt(prices.get('high')):>10}")
    else:
        print("  No pricing data available.")


def main():
    cards = load_cards(CARDS_FILE)
    print(f"Fetching TCGPlayer prices for {len(cards)} cards via pokemontcg.io...")

    for entry in cards:
        try:
            results = fetch_card(entry["pokemon"], entry["set_id"])
            print_card(entry, results)
        except requests.RequestException as e:
            print(f"\nERROR fetching '{entry['raw']}': {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
