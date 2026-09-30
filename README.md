# Telegram Meme Maker Bot — Viral, Legal, No Capital

Makes a classic white Impact meme from any photo in <2 sec. Built to go viral on Telegram.

## Why this goes viral (vs. music leak bot)
- Music leak = instant ban + lawsuit. Meme bot = 100% legal, every share brings 2-3 new users.
- Inline share `↗️` lets anyone forward the meme to any group in 1 tap — each share is free marketing.
- No API cost, no OpenAI key, runs on your laptop.

## What it does
- User sends photo + caption `top | bottom` (e.g. `وقتی میگی دیگه سفارش نمیدم | پنج دقیقه بعد:`)
- If no caption, picks a viral Persian/English template automatically
- Returns JPEG meme + buttons: Share in any chat, Make Sticker (WEBP), My Score
- Watermark `@YourBot` bottom-right for attribution
- State in `state.json` → leaderboard, total memes, per-user count

## Setup (on your laptop, 5 min)

1. Create bot:
   - Telegram → @BotFather → `/newbot` → name `MemeMaker` → username ends in `bot` → copy token `123456:ABC...`
   - Also send `/setinline` → pick your bot → placeholder `meme` (enables ↗️ share)

2. Install:
   ```
   pip install python-telegram-bot Pillow requests
   ```

3. Configure:
   ```
   cp config.example.json config.json
   # edit config.json → paste BOT_TOKEN
   ```

4. Run:
   ```
   python bot.py
   ```
   Keep alive:
   ```
   nohup python bot.py > meme.log 2>&1 &
   tail -f meme.log
   ```

## How to make it hit millions
- Don't spam the same group. Post 1 meme/day in each group, at most 1 per subreddit-style channel per day.
- Use the inline button — it is the growth engine. Every user who shares brings 3 new users.
- Add your shop link in the bot's /start message after 1k users: `Check my shop: @NovaShopBot`

## Files
- `bot.py` — main bot
- `config.example.json` — token template
- `state.json` — auto-created stats

Made for Mohsen — Nova Web3 Studio
