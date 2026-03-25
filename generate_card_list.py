"""
generate_card_list.py
=====================
Fetches every card in the four Delta-era EX sets from the pokemontcg.io API,
builds regular + reverse-holo entries for each eligible card, and outputs:

  all_set_cards.json   — machine-readable card list (used by index.html)
  cards_list.txt       — human-readable verification list

Usage:
  python generate_card_list.py
"""

import json
import time
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8")

# ── Sets to process (in display order) ────────────────────────────────────────
SETS = [
    {"name": "Holon Phantoms",    "id": "ex13"},
    {"name": "Crystal Guardians", "id": "ex14"},
    {"name": "Delta Species",     "id": "ex11"},
    {"name": "Dragon Frontiers",  "id": "ex15"},
]

API_BASE = "https://api.pokemontcg.io/v2/cards"

# Cards with these subtypes never get reverse-holo prints in the EX era
# Note: pokemontcg.io API returns lowercase "ex" for pokémon-ex subtypes
NO_REVERSE_SUBTYPES  = {"EX", "ex", "Gold Star"}
# Cards with these rarities never get reverse-holo prints
NO_REVERSE_RARITIES  = {"Secret Rare", "Rare Secret", "Rare Holo Star", "Rare Holo EX"}


def has_reverse_holo(card: dict) -> bool:
    """
    Return True if this card should have a separate reverse-holo entry.

    Rules for EX-era sets:
     - pokémon-ex (subtype "EX") → no reverse holo
     - Gold Star cards              → no reverse holo
     - Secret Rare / Rare Secret    → no reverse holo
     - Everything else              → yes, has a reverse-holo variant
    """
    subtypes = set(card.get("subtypes") or [])
    rarity   = card.get("rarity") or ""
    if subtypes & NO_REVERSE_SUBTYPES:
        return False
    if rarity in NO_REVERSE_RARITIES:
        return False
    return True


def _num_sort_key(num_str: str) -> tuple:
    """Sort card numbers like '1', '1a', '10', '100', 'T1' numerically."""
    import re
    m = re.match(r"(\d+)([a-zA-Z]*)", str(num_str))
    if m:
        return (int(m.group(1)), m.group(2))
    return (9999, num_str)


def fetch_set_cards(set_id: str) -> list[dict]:
    """Fetch all cards for one set, following pagination."""
    all_cards = []
    page = 1
    while True:
        resp = requests.get(
            API_BASE,
            params={
                "q":        f"set.id:{set_id}",
                "orderBy":  "number",
                "page":     page,
                "pageSize": 250,
                "select":   "id,name,number,rarity,subtypes,supertype,set,images",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data  = resp.json()
        batch = data.get("data", [])
        all_cards.extend(batch)
        if len(batch) < 250:
            break
        page += 1
        time.sleep(0.3)
    all_cards.sort(key=lambda c: _num_sort_key(c.get("number", "0")))
    return all_cards


def build_entry(card: dict, set_name: str, set_id: str, is_reverse: bool) -> dict:
    """Build a flat entry suitable for index.html's CARDS array."""
    name    = card.get("name", "Unknown")
    number  = card.get("number", "?")
    rarity  = card.get("rarity", "")
    subtypes = card.get("subtypes") or []
    set_info = card.get("set") or {}
    total    = str(set_info.get("printedTotal") or set_info.get("total") or "?")

    label = f"{name} (Reverse)" if is_reverse else name

    # Determine the primary variant type for display
    if "EX" in subtypes or "ex" in subtypes:
        variant = "pokémon-ex"
    elif "Gold Star" in subtypes or "Star" in subtypes:
        variant = "Gold Star"
    elif is_reverse:
        variant = "Reverse Holo"
    elif rarity in ("Rare Holo", "Rare Holo EX"):
        variant = "Holo Rare"
    else:
        variant = rarity or "Normal"

    return {
        "id":        card.get("id", f"{set_id}-{number}"),
        "label":     label,
        "number":    number,
        "total":     total,
        "set":       set_name,
        "setId":     set_id,
        "pokemon":   name.lower(),
        "rarity":    rarity,
        "subtypes":  subtypes,
        "variant":   variant,
        "isReverse": is_reverse,
    }


def main():
    all_entries        = []   # flat list: all entries for index.html
    verification_lines = []
    set_summaries      = []

    for set_info in SETS:
        set_name = set_info["name"]
        set_id   = set_info["id"]

        print(f"Fetching {set_name} ({set_id}) ...", end=" ", flush=True)
        try:
            cards = fetch_set_cards(set_id)
        except requests.RequestException as e:
            print(f"FAILED: {e}")
            continue
        print(f"{len(cards)} cards fetched")

        set_total    = len(cards)
        rev_count    = sum(1 for c in cards if has_reverse_holo(c))
        entry_count  = set_total + rev_count
        set_summaries.append((set_name, set_id, set_total, rev_count, entry_count))

        # ── Verification block ────────────────────────────────────────────────
        set_info_api = (cards[0].get("set") or {}) if cards else {}
        printed_total = set_info_api.get("printedTotal") or set_info_api.get("total", "?")
        verification_lines.append("")
        verification_lines.append("=" * 72)
        verification_lines.append(f"  {set_name.upper()}  ({set_id})  —  "
                                   f"{set_total} cards  |  {rev_count} with reverse holo  |  "
                                   f"{entry_count} total entries")
        verification_lines.append(f"  Printed set total from API: {printed_total}")
        verification_lines.append("=" * 72)
        verification_lines.append(
            f"  {'NUM':>4}  {'CARD NAME':<32}  {'RARITY':<22}  {'SUBTYPES':<20}  VARIANTS"
        )
        verification_lines.append("  " + "-" * 68)

        for card in cards:
            num      = card.get("number", "?")
            name     = card.get("name", "?")
            rarity   = card.get("rarity", "")
            subtypes = card.get("subtypes") or []
            can_rev  = has_reverse_holo(card)

            # Regular entry
            entry = build_entry(card, set_name, set_id, False)
            all_entries.append(entry)

            variants = "REG"
            if can_rev:
                rev_entry = build_entry(card, set_name, set_id, True)
                all_entries.append(rev_entry)
                variants = "REG + REV"

            stype_str = ", ".join(subtypes) if subtypes else "—"
            verification_lines.append(
                f"  {num:>4}  {name:<32}  {rarity:<22}  {stype_str:<20}  {variants}"
            )

        time.sleep(0.5)  # be polite to the API

    # ── Summary ───────────────────────────────────────────────────────────────
    verification_lines.append("")
    verification_lines.append("=" * 72)
    verification_lines.append("  SUMMARY")
    verification_lines.append("=" * 72)
    grand_cards  = sum(s[2] for s in set_summaries)
    grand_rev    = sum(s[3] for s in set_summaries)
    grand_total  = sum(s[4] for s in set_summaries)
    for (sname, sid, stot, rcount, etot) in set_summaries:
        verification_lines.append(
            f"  {sname:<22} ({sid})  {stot:>4} cards  "
            f"{rcount:>4} reverse holo  {etot:>4} total entries"
        )
    verification_lines.append("  " + "-" * 68)
    verification_lines.append(
        f"  {'GRAND TOTAL':<22}        {grand_cards:>4} cards  "
        f"{grand_rev:>4} reverse holo  {grand_total:>4} total entries"
    )

    # ── Write outputs ─────────────────────────────────────────────────────────
    with open("all_set_cards.json", "w", encoding="utf-8") as f:
        json.dump(all_entries, f, indent=2, ensure_ascii=False)

    with open("cards_list.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(verification_lines))

    print()
    print("\n".join(verification_lines))
    print()
    print(f"  Files written:")
    print(f"    all_set_cards.json  ({len(all_entries)} entries)")
    print(f"    cards_list.txt      (verification list)")


if __name__ == "__main__":
    main()
