# Meme Aggregator — @memetionus

Posts 20-30 viral memes/day to Telegram channel from Reddit / IG / Twitter.

- **Channel:** https://t.me/memetionus
- **Bot:** https://t.me/Nova3st_bot (must be admin)
- **Sources:** Reddit r/memes, r/dankmemes, r/wholesomememes + meme-api (covers IG/Twitter style)
- **Schedule:** 24/day = every ~60 min random 70-130% jitter
- **Features:** dedup, watermark @memetionus, auto caption + hashtags, deletes nothing

## Setup

1. Add bot as admin to channel:
   - Channel → Edit → Administrators → Add Administrator → @Nova3st_bot → Post messages ✅

2. Run:
```
pip install requests pillow
python aggregator.py
# keep alive
nohup python aggregator.py > agg.log 2>&1 &
```

## Files
- `aggregator.py` — main loop
- `config.json` — token + channel
- `state.json` — posted ids

By Mohsen Fazeli — Nova Web3 Studio
