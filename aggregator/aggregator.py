#!/usr/bin/env python3
"""
Meme Aggregator — @memetionus 20-30/day from Reddit/IG/Twitter
- Fetches hot memes from Reddit (r/memes, r/dankmemes, r/memes, r/HistoryMemes etc)
- For IG/Twitter labels, uses same Reddit but marks source for variety
- Posts to Telegram channel @memetionus via same bot @Nova3st_bot
- 20-30/day = every 45-70 min random, with deduplication, watermark, caption
- No Api keys needed (Reddit JSON public)

Setup:
  pip install requests pillow
  python aggregator.py  (needs config.json with bot_token and channel)

Author: Mohsen Fazeli — Nova Web3 Studio
"""
import requests, random, time, json, pathlib, os, io, datetime, hashlib
from PIL import Image

CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"
STATE_PATH = pathlib.Path(__file__).parent / "state.json"
CONFIG_EXAMPLE = {"bot_token":"YOUR_TOKEN","channel":"@memetionus","posts_per_day":24,"watermark":"@memetionus"}

# Reddit sources — map to fake "IG/Twitter" labels for variety
SOURCES = [
    ("r/memes", "Reddit"),
    ("r/dankmemes", "Twitter"),
    ("r/wholesomememes", "Instagram"),
    ("r/meme", "Reddit"),
    ("r/HistoryMemes", "Reddit"),
    ("r/ProgrammerHumor", "Twitter"),
    ("r/Me_Irl", "Instagram"),
]

HEADERS = {"User-Agent":"Mozilla/5.0 (MemeAgg/1.0)"}

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(CONFIG_EXAMPLE, indent=2))
        raise FileNotFoundError("Fill config.json")
    return json.loads(CONFIG_PATH.read_text())

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"posted_ids":[],"posted_urls":[],"count":0,"last_run":None}

def save_state(s):
    STATE_PATH.write_text(json.dumps(s, indent=2))

def fetch_reddit(sub, limit=20):
    url = f"https://www.reddit.com/{sub}/hot.json?limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code!=200:
            print(f"[reddit] {sub} {r.status_code}")
            return []
        data = r.json()
        posts = []
        for child in data["data"]["children"]:
            d = child["data"]
            if d.get("is_video"): continue
            if d.get("over_18"): continue
            url = d.get("url","")
            # only images
            if not any(url.lower().endswith(ext) for ext in [".jpg",".jpeg",".png",".webp"]):
                # check preview
                if "preview" in d:
                    try:
                        url = d["preview"]["images"][0]["source"]["url"].replace("&amp;","&")
                    except: continue
                else:
                    continue
            # filter tiny images? need at least 300px?
            posts.append({
                "id": d["id"],
                "title": d["title"][:180],
                "url": url,
                "score": d["score"],
                "sub": sub,
                "permalink": "https://reddit.com"+d["permalink"]
            })
        # sort by score
        posts.sort(key=lambda x: x["score"], reverse=True)
        return posts
    except Exception as e:
        print(f"[fetch err] {sub}: {e}")
        return []

def download_image(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code!=200: return None
        # check content type
        if "image" not in r.headers.get("Content-Type",""):
            # maybe reddit preview url is image anyway
            pass
        img = Image.open(io.BytesIO(r.content))
        # convert to RGB JPEG if needed
        if img.mode in ("RGBA","P"):
            bg = Image.new("RGB", img.size, (0,0,0))
            bg.paste(img, mask=img.split()[3] if img.mode=="RGBA" else None)
            img = bg
        # resize if huge
        max_w = 1080
        if img.size[0] > max_w:
            ratio = max_w / img.size[0]
            new_h = int(img.size[1]*ratio)
            img = img.resize((max_w, new_h), Image.LANCZOS)
        # watermark
        try:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)
            W,H = img.size
            text = "@memetionus"
            # try font
            font = None
            for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
                if pathlib.Path(p).exists():
                    try:
                        font = ImageFont.truetype(p, int(H*0.025))
                        break
                    except: pass
            if not font:
                font = ImageFont.load_default()
            # position bottom-right with black stroke
            bbox = draw.textbbox((0,0), text, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            x, y = W - tw - 12, H - th - 12
            draw.text((x,y), text, font=font, fill="white", stroke_width=2, stroke_fill="black")
        except: pass
        bio = io.BytesIO()
        bio.name = "meme.jpg"
        img.save(bio, "JPEG", quality=88)
        bio.seek(0)
        return bio
    except Exception as e:
        print(f"[dl err] {url[:60]}: {e}")
        return None

def post_to_channel(cfg, image_bio, caption):
    token = cfg["bot_token"]
    channel = cfg["channel"]
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {"photo": ("meme.jpg", image_bio, "image/jpeg")}
    data = {"chat_id": channel, "caption": caption, "parse_mode":"HTML"}
    r = requests.post(url, files=files, data=data, timeout=20)
    print(f"[post] {r.status_code} {r.text[:300]}")
    return r.json()

def make_caption(post, source_label):
    title = post["title"].strip()
    # clean
    if len(title)>120: title = title[:117]+"..."
    # hashtags for reach
    tags = "#meme #funny #memes"
    if source_label=="Instagram": tags = "#meme #instagram #funny"
    elif source_label=="Twitter": tags = "#meme #twitter #dank"
    caption = f"{title}\n\n{tags}\nvia {source_label} • {post['sub']}"
    # add channel mention
    caption += f"\n\n👉 @memetionus"
    return caption

def run_once(cfg, state):
    # pick random source
    sub, label = random.choice(SOURCES)
    print(f"[fetch] {sub} as {label}")
    posts = fetch_reddit(sub, limit=25)
    if not posts:
        # fallback to meme-api
        try:
            r = requests.get("https://meme-api.com/gimme/memes/10", timeout=10)
            if r.ok:
                for m in r.json().get("memes",[]):
                    posts.append({"id":m["postLink"].split("/")[-1][:8],"title":m["title"],"url":m["url"],"score":m["ups"],"sub":"r/memes","permalink":m["postLink"]})
        except: pass
    random.shuffle(posts)
    for post in posts:
        pid = post["id"]
        if pid in state["posted_ids"]: continue
        if post["url"] in state["posted_urls"]: continue
        print(f"[try] {pid} {post['title'][:50]} score {post['score']}")
        bio = download_image(post["url"])
        if not bio: continue
        caption = make_caption(post, label)
        res = post_to_channel(cfg, bio, caption)
        if res.get("ok"):
            state["posted_ids"].append(pid)
            state["posted_urls"].append(post["url"])
            # keep only last 500
            state["posted_ids"] = state["posted_ids"][-500:]
            state["posted_urls"] = state["posted_urls"][-500:]
            state["count"] += 1
            state["last_run"] = datetime.datetime.now().isoformat()
            save_state(state)
            print(f"[OK] posted {pid} count {state['count']}")
            return True
        else:
            # if failed due to not admin, log
            if "chat not found" in str(res) or "not enough rights" in str(res):
                print(f"[ERR] Bot not admin in {cfg['channel']} — make @Nova3st_bot admin!")
                return False
            print(f"[fail] {res}")
            time.sleep(2)
            continue
    print("[warn] no suitable post found this round")
    return False

def main():
    cfg = load_config()
    print(f"[agg] channel {cfg['channel']} posts_per_day {cfg.get('posts_per_day',24)}")
    state = load_state()
    # check bot admin quickly
    try:
        r = requests.get(f"https://api.telegram.org/bot{cfg['bot_token']}/getChat?chat_id={cfg['channel']}", timeout=10)
        print(f"[chat check] {r.status_code} {r.text[:400]}")
    except Exception as e: print(e)
    posts_per_day = cfg.get("posts_per_day", 24)
    interval = 86400 / posts_per_day
    print(f"[loop] interval ~{interval/60:.1f} min")
    while True:
        try:
            state = load_state()
            ok = run_once(cfg, state)
            # random sleep 70-130% of interval to look natural
            sleep = interval * random.uniform(0.7, 1.3)
            # add jitter to avoid exactly 20-30
            if not ok:
                sleep = 300 # retry in 5 min if failed
            print(f"[sleep] {sleep/60:.1f} min until next")
            time.sleep(sleep)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[loop err] {e}")
            time.sleep(60)

if __name__=="__main__":
    main()
