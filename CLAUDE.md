# Pokemon Delta Species — Project Notes

## Current Status (2026-03-25 — updated)

### Done today
- Set up eBay Developer account (username: manu2020)
- Created Production keyset `delta_species` — App ID: `VictorCh-deltaspe-PRD-7f6069bf2-543b0316`
- Fixed disabled keyset by applying exemption ("I do not persist eBay data") via the Notifications page
- Created `.env` file with Production App ID (already in `.gitignore`)
- Installed `python-dotenv` and wired it into `ebay_prices.py`

### Blocked / Waiting
- **eBay rate limits not provisioned yet** — `findCompletedItems` returning error 10001 ("exceeded call limit") because the Production keyset was just activated today. This is normal for new accounts. Try again in a few hours or tomorrow — no code changes needed, just rerun `python ebay_prices.py`.

---

## eBay API Status

- `ebay_prices.py` is **dead** — the eBay Finding API (`findCompletedItems`) was retired June 2023. Getting 500 errors, not a fixable problem.
- **Solution**: `ebay_tracker.py` — uses the Browse API (active listings) + SQLite to build our own forward-looking sold database.

### How ebay_tracker.py works
1. Scans active eBay listings for all 11 cards daily via Browse API (OAuth client credentials)
2. Stores every listing in `prices.db`
3. On each scan, listings that disappeared are recorded as likely sales with a confidence score:
   - **HIGH**: auction that disappeared on/after its end date
   - **MEDIUM**: fixed-price listing seen across multiple scans then gone
   - **LOW**: fixed-price listing only seen once (might be relisted — not recorded)
4. Computes fair value (90d median), market price (7d median), momentum % per card

### To make ebay_tracker.py work, you need your Cert ID
Add to `.env`:
```
EBAY_CERT_ID=your_cert_id_here
```
Get it from developer.ebay.com → Hello Victor Chen → Application Keysets → `delta_species` → the "Cert ID" value (next to App ID).

## Architecture (decided 2026-03-25)

Two tools with distinct jobs:
- **PriceCharting** = fair value baseline (what a card is *worth*, based on real sold data)
- **eBay active listings** = deal detector (what people are *asking right now*)
- **Gap between them** = buy alert (listing is underpriced vs fair value)

`ebay_tracker.py` was reconsidered — using listing price as sold price is unreliable (auctions show starting bid, BIN may have accepted Best Offers). Repurposed as an inventory/liquidity monitor.

`deal_finder.py` is the main tool: fetches PC fair value + eBay active listings → Discord alert when a listing is 20%+ below fair value. Deduplicates alerts via `prices.db` so you don't get pinged twice for the same listing.

## Full Set Card Database (added 2026-03-25)

All 4 sets are now fully catalogued in the site. `index.html` now tracks ALL cards across:
- Holon Phantoms (ex13): 111 cards, 104 with reverse holo → 215 entries
- Crystal Guardians (ex14): 100 cards, 88 with reverse holo → 188 entries
- Delta Species (ex11): 114 cards, 107 with reverse holo → 221 entries
- Dragon Frontiers (ex15): 101 cards, 89 with reverse holo → 190 entries
- **Total: 426 unique cards, 814 tracked entries (regular + reverse holo)**

**Reverse holo rules enforced:**
- pokémon-ex cards (subtype `"ex"`) → regular only, no reverse holo
- Gold Star cards (subtype `"Star"`, rarity `"Rare Holo Star"`) → regular only
- Secret Rares → regular only
- All other cards → regular + reverse holo entries

**Site UI** (index.html):
- Compact table view (no images by default): # | Name | Variant badge | Rarity | Market price
- Click any row to expand inline → card image + condition estimates + TCGPlayer data
- Lazy price loading per page (fetches by card ID from pokemontcg.io API)
- Set navigation in sidebar, search bar, All/Regular/Reverse Holo filter tabs
- 25 entries per page with pagination

**New/changed files:**
- `index.html` — fully rebuilt with all 814 entries embedded, new compact UI
- `generate_card_list.py` — fetches all cards from pokemontcg.io API for all 4 sets
- `all_set_cards.json` — machine-readable card database (426 cards × fields)
- `cards_list.txt` — human-readable verification list of every card + variant
- `build_site.py` — generator that embeds the JSON data into index.html

**eBay deal finder stays focused on the 11-card watchlist** — expanding to 800+ eBay searches would blow rate limits. The full card database is display-only (TCGPlayer prices via pokemontcg.io).

---

## Current State (end of session 2026-03-25)

Everything is live and working on GitHub Pages.

### What's done
- [x] All credentials in `.env` — EBAY_APP_ID, EBAY_CERT_ID, DISCORD_WEBHOOK_URL
- [x] `fetch_watchlist_prices.py` — fetches 12 cards, saves `watchlist_data.json` (160 listings)
- [x] `deal_finder.py` — pings Discord when PSA 8/9/10 listing is 25%+ below median; deduplicates via `prices.db` (never double-pings same listing)
- [x] Site watchlist tab: PSA 8/9/10/NM-LP/Raw/TCGPlayer tabs, delta badge, language badges
- [x] Gardevoir Celebrations reprint junk filtered (`-celebrations` in query)
- [x] `PC_TOKEN` / PriceCharting dropped — site requires paid sub now; using pokemontcg.io instead

### Next session TODO (in order)

**#1 — Schedule deal_finder.py (one command, do this first)**
```
schtasks /create /tn "PokemonDealFinder" /tr "python C:\Users\vchen\OneDrive\Documents\pycharmprojects\pokemon_delta_species\deal_finder.py" /sc hourly /mo 4
```
Runs every 4 hours automatically. Check it: Task Scheduler app → Task Scheduler Library → PokemonDealFinder.

**#2 — PSA population data (optional)**
- Endpoint `api.psacard.com/publicapi/pop/GetPSASetItems/{setId}` works without auth (got 429 = rate limited, not blocked)
- Need to find PSA set IDs for Crystal Guardians, Holon Phantoms, Delta Species, Dragon Frontiers
- Would show PSA 8/9/10 pop counts in each card's tab on the site

**#3 — Refresh prices any time**
```bash
python fetch_watchlist_prices.py   # re-fetch all 12 cards
# then commit + push watchlist_data.json
```

---

## Key Files
- `index.html` — live site: 814 cards across 4 sets + watchlist tab for 12 cards
- `watchlist_data.json` — fetched locally, committed to repo, read by site JS at runtime
- `fetch_watchlist_prices.py` — run this to refresh prices → commit watchlist_data.json
- `deal_finder.py` — Discord deal alerts (25% below median); run manually or via Task Scheduler
- `prices.db` — SQLite: `alerts_sent` table deduplicates Discord pings by eBay item_id
- `Cards_I_Care_About.txt` — 12-card personal watchlist
- `all_set_cards.json` — full card database (426 cards) from pokemontcg.io API
- `generate_card_list.py` — re-fetches all set cards from API → updates all_set_cards.json
- `build_site.py` — re-generates index.html from all_set_cards.json
- `next_time.txt` — session handoff notes
- `.env` — credentials (not committed): EBAY_APP_ID, EBAY_CERT_ID, DISCORD_WEBHOOK_URL
- `ebay_prices.py` — OLD/DEAD: used retired Finding API, ignore
- `ebay_tracker.py` — OLD/SUPERSEDED by deal_finder.py
