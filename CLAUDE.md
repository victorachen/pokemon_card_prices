# Pokemon Delta Species — Project Notes

## Seller Away Monitor (added 2026-03-27)

- **Item**: https://www.ebay.com/itm/157626935379 — seller away until ~Mar 29
- **Script**: `monitor_seller.py` — scrapes listing page for away/vacation text
- **Workflow**: `.github/workflows/seller_monitor.yml` — runs hourly via GH Actions cron
- **Discord pings**: every hour with status snippet; one-time `🟢 BACK` alert when seller returns
- **Dedup**: `seller_alerted.flag` (cached in GH Actions) prevents repeat "back" pings
- **After buying**: disable the workflow in GitHub Actions → Settings → Actions

---

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

## Current State (end of session 2026-03-27)

Everything is live and working on GitHub Pages. deal_finder.py runs automatically every 4 hours via GitHub Actions — no PC required.

### What's done
- [x] All credentials in `.env` — EBAY_APP_ID, EBAY_CERT_ID, DISCORD_WEBHOOK_URL, DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY
- [x] `fetch_watchlist_prices.py` — fetches **15 cards** (was 12), saves `watchlist_data.json`
- [x] `deal_finder.py` — pings Discord when PSA 8/9/10 listing is 25%+ below median; deduplicates via `prices.db`
- [x] GitHub Actions workflow — `deal_finder.py` runs every 4 hours, secrets stored in repo, `prices.db` persisted via Actions cache
- [x] Watchlist expanded: Gyarados, Dragonite, Charizard each split into Rev + Holo entries (15 total)
- [x] Rev graded queries fixed to include "reverse" so PSA searches filter correctly
- [x] Unicode crash fixed in `deal_finder.py` (δ symbol on Windows)
- [x] `ebay_auction_searches.html` — browser page with all 15 cards × PSA 8/9/10 auction links (covers eBay Live which Browse API can't see)
- [x] Site watchlist tab: PSA 8/9/10/NM-LP/Raw/TCGPlayer tabs, delta badge, language badges
- [x] **Card Search tab** — searches entire Pokémon TCG via pokemontcg.io API; thumbnails + live TCGPlayer prices + eBay Active/Sold links for PSA 8/9/10/NM/Raw; Regular/Rev Holo toggle
- [x] **PriceCharting Last Sold tab** — paste any PriceCharting URL → fetches last 5 sold prices via CORS proxy; lookups saved in browser localStorage; multi-proxy fallback (corsproxy.io → allorigins.win → codetabs.com); visible debug log in card UI; `pc_last_sold.py` also exists as CLI fallback
- [x] **Discord bot** (`discord_bot.py`) — live and working! Uses Claude Haiku via Anthropic API. Run `python discord_bot.py` to start. Bot name: "Delta Species Bot" on server "delta_species".

### Discord Bot Details
- `discord_bot.py` — Claude Haiku bot, responds to `!claude <msg>` or @mention
- Commands: `!claude`, `!status` (watchlist summary), `!clear` (reset history), `!help`
- Uses model `claude-haiku-4-5-20251001` (~$0.001/msg)
- Bot runs **locally** — must have `python discord_bot.py` running on PC
- **Next step**: deploy to Railway so it runs 24/7 without PC (see remote_instructions.txt)
- Anthropic API: console.anthropic.com — $10 credits loaded, spend limit set to $10
- Discord Developer Portal: discord.com/developers → "Delta Species Bot" app
- `remote_instructions.txt` — full setup guide for replicating this bot in any future project

### eBay Live blind spot
The Browse API does NOT index eBay Live auctions — they're a separate platform. Use `ebay_auction_searches.html` to manually check for live auction deals.

### PC Last Sold tab — proxy status (end of 2026-03-27 session)
Built and pushed but **NOT yet confirmed working** — got "Failed to fetch" with allorigins.win (single proxy). Fixed by adding 3-proxy fallback (corsproxy.io → allorigins.win → codetabs.com) with visible debug log in each card. User went to sleep before re-testing. **Next session: open the site, click PC Last Sold, paste a URL and see what the debug log says.** If all 3 still fail, we may need a small serverless function (Netlify/Vercel) as proxy instead.

---

## Discord ↔ Terminal Mirroring (added 2026-03-27)

### What's working
- **Discord → Claude context**: `UserPromptSubmit` hook (`discord_mirror_hook.py`) reads `~/discord_mirror.log` since last check and injects new Discord messages as `additionalContext` — Claude sees them every turn
- **Claude Code → Discord TLDR**: Stop hook fires `discord_tldr.py` on every response; uses Haiku to summarize everything done and POSTs to Discord webhook as "Spidy Bot [Claude]..."
- **Discord bot terminal mirroring**: `discord_bot.py` writes all Victor messages + bot replies to `~/discord_mirror.log`

### What didn't work / lessons learned
- **`systemMessage` from hooks** — appears as a subtle UI banner in Claude Code, not prominent terminal text. Victor couldn't see it.
- **Background process stdout** — bot runs via `run_in_background: true`; its `print()` statements go to a temp task output file, NOT the visible terminal. Cannot use stdout for real-time terminal display.
- **`CONOUT$` on Windows** — attempted to open Windows console device directly from bot subprocess to write to parent terminal. Did NOT work — background bash subprocess doesn't inherit the same console handle.
- **Real-time bidirectional mirror is not achievable** with the current architecture (bot as background process + Claude Code as foreground). The hook approach is the closest working solution.

### Current best solution
1. Victor sends Discord message → bot logs it to `~/discord_mirror.log`
2. Next time Victor types anything in Claude Code → hook reads log → Claude sees Discord messages in context and can reference them explicitly
3. Claude finishes responding → Stop hook posts Haiku TLDR to Discord

### If real-time terminal display is needed in future
- Run bot in a **separate terminal window** (not as Claude Code background task): `python discord_bot.py` — stdout goes directly to that window
- Or use `Get-Content -Wait ~/discord_mirror.log` in a second terminal to tail the log
- Or deploy bot to Railway so it doesn't need to run on PC at all

### Key files
- `discord_bot.py` — bot; writes mirror lines to `~/discord_mirror.log` + `CONOUT$` attempt
- `discord_tldr.py` — Stop hook; posts Haiku TLDR to Discord webhook
- `discord_mirror_hook.py` — UserPromptSubmit hook; injects Discord log into Claude context
- `~/.claude/settings.json` — has both hooks configured

---

### Next session TODO (in order)

**#1 — Test PC Last Sold tab**
- Open site → PC Last Sold → paste `https://www.pricecharting.com/game/pokemon-crystal-guardians/charizard-4`
- Should show a debug log per proxy attempt (✓/✗)
- If all fail: screenshot the debug log and tell Claude — we'll build a serverless proxy or use a different approach
- If "no sales table found": debug log shows page title + table IDs — paste those to Claude to fix parser

**#2 — Deploy Discord bot to Railway (so it runs 24/7 without PC)**
- railway.app → New Project → Deploy from GitHub repo
- Add env vars in Railway: DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY, EBAY_APP_ID, EBAY_CERT_ID, DISCORD_WEBHOOK_URL
- Procfile already created: `worker: python discord_bot.py`
- See `remote_instructions.txt` Step 7 for full Railway walkthrough

**#3 — Re-fetch watchlist data (new cards need data)**
```bash
python fetch_watchlist_prices.py
git add watchlist_data.json && git commit -m "Refresh watchlist data (15 cards)" && git push
```

**#4 — Verify GitHub Actions is running**
- Go to: github.com/victorachen/pokemon_card_prices/actions
- Should see runs every 4 hours under "Pokemon Deal Finder"
- Can trigger manually with "Run workflow" button

**#5 — PSA population data (optional)**
- Endpoint `api.psacard.com/publicapi/pop/GetPSASetItems/{setId}` works without auth
- Need PSA set IDs for Crystal Guardians, Holon Phantoms, Delta Species, Dragon Frontiers
- Would show PSA 8/9/10 pop counts in each card's tab on the site

---

## Key Files
- `index.html` — live site: 814 cards across 4 sets + watchlist tab for 16 cards (added Zapdos ex FRLG)
- `watchlist_data.json` — fetched locally, committed to repo, read by site JS at runtime
- `fetch_watchlist_prices.py` — run this to refresh prices → commit watchlist_data.json
- `deal_finder.py` — Discord deal alerts (25% below median); runs via GitHub Actions every 4h
- `.github/workflows/deal_finder.yml` — GitHub Actions schedule config
- `prices.db` — SQLite: `alerts_sent` table deduplicates Discord pings by eBay item_id
- `ebay_auction_searches.html` — browser page: all 15 cards × PSA 8/9/10 auction search links
- `discord_bot.py` — Claude Haiku Discord bot; run locally or deploy to Railway
- `remote_instructions.txt` — full guide for setting up Discord bot in any project
- `Procfile` — Railway deployment config (`worker: python discord_bot.py`)
- `pc_last_sold.py` — CLI fallback for PriceCharting scraping (if browser proxy fails)
- `requirements.txt` — all Python dependencies
- `Cards_I_Care_About.txt` — 16-card personal watchlist
- `discord_bot.py` — Claude Haiku Discord bot; responds to `!claude`/`@mention`/`!status`/`!clear`/`!help`; mirrors to `~/discord_mirror.log`
- `discord_tldr.py` — Claude Code Stop hook; Haiku TLDR of every response → Discord webhook
- `discord_mirror_hook.py` — Claude Code UserPromptSubmit hook; injects new Discord messages into Claude context each turn
- `all_set_cards.json` — full card database (426 cards) from pokemontcg.io API
- `generate_card_list.py` — re-fetches all set cards from API → updates all_set_cards.json
- `build_site.py` — re-generates index.html from all_set_cards.json
- `next_time.txt` — session handoff notes
- `.env` — credentials (not committed): EBAY_APP_ID, EBAY_CERT_ID, DISCORD_WEBHOOK_URL, DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY
- `github_secrets.txt` — GitHub secret values for reference (not committed)
- `ebay_prices.py` — OLD/DEAD: used retired Finding API, ignore
- `ebay_tracker.py` — OLD/SUPERSEDED by deal_finder.py
