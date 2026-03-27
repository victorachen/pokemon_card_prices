"""
discord_bot.py — Discord bot that lets you interact with Claude about the
Pokemon card tracking project from your phone or anywhere.

Usage:
    In Discord:
        !claude <your message>   — ask Claude anything
        @mention <your message>  — same as !claude
        !clear                   — reset conversation history for this channel
        !status                  — show current watchlist price summary
        !help                    — show commands

Setup:
    Add to .env:
        DISCORD_BOT_TOKEN=your_bot_token
        ANTHROPIC_API_KEY=your_anthropic_api_key

    Run: python discord_bot.py
    Or deploy to Railway (see README section in CLAUDE.md)
"""

import os
import io
import sys
import json
import discord
import anthropic
from datetime import datetime, timezone
from dotenv import load_dotenv

# Force UTF-8 stdout/stderr so Unicode chars (arrows, symbols) don't crash on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Open the Windows console directly so output appears in the Claude Code terminal
# regardless of stdout redirection on the background process.
try:
    _CONOUT = open("CONOUT$", "w", encoding="utf-8", errors="replace")
except Exception:
    _CONOUT = None

def console_print(text: str):
    if _CONOUT:
        try:
            _CONOUT.write(text + "\n")
            _CONOUT.flush()
        except Exception:
            pass

load_dotenv(dotenv_path=".env")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
WATCHLIST_FILE    = "watchlist_data.json"

MAX_HISTORY = 20  # messages kept per channel before oldest are dropped

# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful assistant for Victor's Pokemon card tracking project. \
You help him monitor eBay for deals on specific vintage Pokemon cards from the ex-era sets.

## Project Overview
Two tools with distinct jobs:
- PriceCharting = fair value baseline (real sold data)
- eBay active listings = deal detector (what people are asking right now)
- Gap between them = buy alert (listing underpriced vs fair value)

Key scripts:
- fetch_watchlist_prices.py — fetches eBay listings + TCGPlayer prices for all 15 watchlist \
cards, saves watchlist_data.json. Run locally, then commit+push.
- deal_finder.py — scans eBay for PSA 8/9/10 listings 25%+ below market median, \
sends Discord embed alerts. Runs automatically every 4h via GitHub Actions.
- index.html — GitHub Pages site: 814 cards across 4 sets with TCGPlayer prices + \
watchlist tab with PSA 8/9/10/NM-LP/Raw/TCGPlayer sub-tabs.
- ebay_auction_searches.html — manual browser page for eBay Live (not indexed by Browse API).

## 16-Card Watchlist
1. Charizard Crystal Guardians Rev Holo
2. Charizard Crystal Guardians Holo
3. Gyarados Holon Phantoms Rev Holo
4. Gyarados Holon Phantoms Holo
5. Meowth Holon Phantoms Rev Holo
6. Gloom Holon Phantoms Rev Holo
7. Salamence ex Dragon Frontiers
8. Feraligatr Dragon Frontiers Rev Holo
9. Typhlosion Dragon Frontiers Rev Holo
10. Dragonite Delta Species Rev Holo
11. Dragonite Delta Species Holo
12. Ampharos Dragon Frontiers Rev Holo
13. Gardevoir ex Dragon Frontiers
14. Vaporeon Delta Species Rev Holo
15. Vaporeon Holon Research Tower (Japanese)
16. Zapdos ex FireRed LeafGreen

## Sets in Full Database
- Holon Phantoms (ex13): 215 entries
- Crystal Guardians (ex14): 188 entries
- Delta Species (ex11): 221 entries
- Dragon Frontiers (ex15): 190 entries
Total: 814 tracked entries (regular + reverse holo)

Reverse holo rules: pokemon-ex, Gold Star, and Secret Rare cards get regular only; \
all others get regular + reverse holo.

## eBay Setup
- Account: manu2020 on developer.ebay.com
- App ID: VictorCh-deltaspe-PRD-7f6069bf2-543b0316
- Uses Browse API with OAuth client credentials
- eBay Live auctions are NOT visible via Browse API — check ebay_auction_searches.html manually
- Deal threshold: 25% below market median (PSA 8/9/10 only)
- Deduplication: prices.db (alerts_sent table) prevents repeat pings for same eBay item_id

## Credentials (.env file — never committed)
EBAY_APP_ID, EBAY_CERT_ID, DISCORD_WEBHOOK_URL, DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY

## GitHub Actions
.github/workflows/deal_finder.yml — runs deal_finder.py every 4 hours.
Secrets stored in repo settings. prices.db persisted via Actions cache.
GitHub repo: victorachen/pokemon_card_prices (GitHub Pages site is live there)

## Common Tasks
- Refresh prices: python fetch_watchlist_prices.py → git add watchlist_data.json && git push
- Check for deals manually: python deal_finder.py --dry-run
- Rebuild site: python build_site.py (if card database changes)
- Regenerate card list: python generate_card_list.py

Answer Victor's questions concisely and practically. Help him debug, suggest improvements, \
write code, or explain what's happening. When mentioning file paths or line numbers, \
be specific so he can navigate on mobile."""

# ── Bot state ──────────────────────────────────────────────────────────────────

conversation_history: dict[int, list[dict]] = {}  # channel_id → message list

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_history(channel_id: int) -> list[dict]:
    return conversation_history.get(channel_id, [])


def append_history(channel_id: int, role: str, content: str):
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []
    conversation_history[channel_id].append({"role": role, "content": content})
    # Keep only the most recent MAX_HISTORY messages
    if len(conversation_history[channel_id]) > MAX_HISTORY:
        conversation_history[channel_id] = conversation_history[channel_id][-MAX_HISTORY:]


MIRROR_LOG = os.path.expanduser("~/discord_mirror.log")

def mirror_log(line: str):
    """Write line to console + log file so it appears in the Claude Code terminal."""
    console_print(line)
    with open(MIRROR_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def bot_print(text: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f'[{ts}] Bot: "{text}"'
    mirror_log(line)


async def send_chunked(message: discord.Message, text: str):
    """Send text that may exceed Discord's 2000 char limit as multiple messages."""
    bot_print(text)
    first = True
    while text:
        if len(text) <= 1990:
            chunk, text = text, ""
        else:
            split = text.rfind("\n", 0, 1990)
            if split == -1:
                split = 1990
            chunk = text[:split]
            text = text[split:].lstrip("\n")

        if first:
            await message.reply(chunk)
            first = False
        else:
            await message.channel.send(chunk)


def load_watchlist_summary() -> str:
    """Build a short text summary of watchlist_data.json for !status."""
    if not os.path.exists(WATCHLIST_FILE):
        return "watchlist_data.json not found — run fetch_watchlist_prices.py first."

    with open(WATCHLIST_FILE, encoding="utf-8") as f:
        data = json.load(f)

    updated = data.get("last_updated", "unknown")
    # Parse ISO datetime and make it readable
    try:
        dt = datetime.fromisoformat(updated)
        updated = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass

    lines = [f"**Watchlist prices** (fetched {updated})\n"]
    for card in data.get("cards", []):
        name = card["name"]
        m = card.get("market_medians", {})
        p8  = f"${m['psa8']:.0f}"  if m.get("psa8")  else "—"
        p9  = f"${m['psa9']:.0f}"  if m.get("psa9")  else "—"
        p10 = f"${m['psa10']:.0f}" if m.get("psa10") else "—"
        tcg = f"${card['tcgplayer_market']:.2f}" if card.get("tcgplayer_market") else "—"
        lines.append(f"**{name}**  PSA8:{p8}  PSA9:{p9}  PSA10:{p10}  TCG:{tcg}")

    return "\n".join(lines)


# ── Events ─────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}  (id {bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.webhook_id:
        return

    content = message.content.strip()
    is_mention = bot.user in message.mentions

    # Mirror every incoming message to terminal and log
    ts = datetime.now().strftime("%H:%M")
    line = f'Victor sent "{content}" on Discord {ts}'
    mirror_log(line)

    # ── Special commands ──────────────────────────────────────────────────────

    if content == "!clear":
        conversation_history.pop(message.channel.id, None)
        reply_text = "Conversation history cleared."
        bot_print(reply_text)
        await message.reply(reply_text)
        return

    if content == "!help":
        reply_text = (
            "**Pokemon Deal Bot**\n\n"
            "Just type anything — every message goes to Claude automatically\n"
            "`!status` — Current watchlist price summary\n"
            "`!clear` — Reset conversation history for this channel\n"
            "`!help` — This message\n\n"
            "Conversation history is kept per channel (last 20 messages) so follow-ups work naturally."
        )
        bot_print(reply_text)
        await message.reply(reply_text)
        return

    if content == "!status":
        async with message.channel.typing():
            summary = load_watchlist_summary()
        await send_chunked(message, summary)
        return

    # ── Claude chat (every message is treated as directed to the bot) ────────

    prompt = content
    if content.startswith("!claude"):
        prompt = content[len("!claude"):].strip()
    elif is_mention:
        prompt = content.replace(f"<@{bot.user.id}>", "").strip()

    if not prompt:
        reply_text = "What do you want to know? Try `!help` for usage."
        bot_print(reply_text)
        await message.reply(reply_text)
        return

    append_history(message.channel.id, "user", prompt)

    async with message.channel.typing():
        try:
            response = claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=get_history(message.channel.id),
            )
            reply = response.content[0].text
            append_history(message.channel.id, "assistant", reply)
            await send_chunked(message, reply)

        except anthropic.APIError as e:
            err = f"Claude API error: {e}"
            bot_print(err)
            await message.reply(err)
        except Exception as e:
            err = f"Unexpected error: {e}"
            bot_print(err)
            await message.reply(err)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    missing = []
    if not DISCORD_BOT_TOKEN:
        missing.append("DISCORD_BOT_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"ERROR: Missing in .env: {', '.join(missing)}")
        raise SystemExit(1)

    bot.run(DISCORD_BOT_TOKEN)
