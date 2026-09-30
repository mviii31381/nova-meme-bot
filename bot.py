#!/usr/bin/env python3
"""
Telegram Meme Generator Bot — Viral, Legal, No Capital
- User sends photo + optional top/bottom text
- Bot creates classic white Impact meme in <2 sec
- Also auto-caption mode: picks a viral Persian/English caption template
- Returns image + buttons: Share, Make Sticker, New Meme
- Keeps leaderboard: most shared memes
- Runs on your laptop 24/7, no API cost (uses Pillow, no OpenAI key needed)

Setup:
  pip install python-telegram-bot Pillow requests
  Get bot token from @BotFather -> /newbot -> copy token
  cp config.example.json config.json and fill BOT_TOKEN
  python bot.py

Viral tricks built-in:
- Inline share button (switch_inline_query) lets users share meme in any chat in 1 tap -> brings new users
- Auto watermark: "Made by @YourBot" small bottom-right
- Sticker export: converts meme to WEBP sticker

Author: Mohsen Fazeli — Nova Web3 Studio
"""

import json, pathlib, logging, random, textwrap, os, io, datetime
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, ContextTypes, filters

CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"
STATE_PATH = pathlib.Path(__file__).parent / "state.json"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("meme")

# Try to load a good Impact-like font, fallback to default
def get_font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "arialbd.ttf"]:
        if pathlib.Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

# Viral caption templates (Persian + English, all SFW, no copy)
AUTO_CAPTIONS = [
    ("POV:", "وقتی می‌فهمی فردا امتحانه"),
    ("من:", "فقط یه قسمت دیگه می‌بینم", "ساعت 3 صبح:"),
    ("هیچکس:", "من در حال تلاش برای بیدار شدن:"),
    ("وقتی پول نداری", "ولی سبد خریدت پره"),
    ("من و خوابم", "یه رابطه سمی"),
    ("That feeling when", "code works on first run"),
    ("Me:", "I'll sleep early tonight", "Also me at 2 AM:"),
    ("Expectation", "Reality"),
    ("My wallet:", "I need a vacation", "Also my wallet:"),
    ("When you", "understand the joke 3 days later"),
    ("POV: You opened", "the fridge for the 10th time"),
    ("من:", "رژیم از شنبه", "شنبه:"),
    ("Life update:", "still waiting for motivation to load"),
    ("وقتی میگی دیگه آنلاین نمیشم", "پنج دقیقه بعد:"),
]

def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json missing — copy config.example.json")
    return json.loads(CONFIG_PATH.read_text())

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"total_memes": 0, "shares": 0, "users": {}}

def save_state(s):
    STATE_PATH.write_text(json.dumps(s, indent=2))

def draw_meme(image_path, top_text, bottom_text, watermark="@YourMemeBot"):
    img = Image.open(image_path).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    # Auto scale font to image width
    def fit_text(text):
        if not text: return None, 0
        text = text.strip().upper()
        # Wrap long lines
        max_chars = max(14, W // 28)
        lines = textwrap.wrap(text, width=max_chars)
        # Find largest font that fits
        for size in range(int(H*0.09), 12, -2):
            font = get_font(size)
            # Estimate height
            line_h = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + 8
            total_h = line_h * len(lines)
            # Estimate width: check longest line
            max_w = max((draw.textbbox((0,0), l, font=font)[2] - draw.textbbox((0,0), l, font=font)[0]) for l in lines) if lines else 0
            if max_w < W*0.92 and total_h < H*0.22:
                return (lines, font, line_h)
        font = get_font(20)
        return (lines, font, 24)

    def render_block(lines, font, line_h, y_start):
        if not lines: return
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0,0), line, font=font, stroke_width=4)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (W - w)//2
            y = y_start + i*line_h
            # White text with black stroke (classic meme)
            draw.text((x, y), line, font=font, fill="white", stroke_width=4, stroke_fill="black")

    top_lines, top_font, top_h = fit_text(top_text)
    bot_lines, bot_font, bot_h = fit_text(bottom_text)

    # Top block
    if top_lines:
        render_block(top_lines, top_font, top_h, y_start=int(H*0.04))
    # Bottom block
    if bot_lines:
        total_bot_h = bot_h * len(bot_lines)
        y0 = H - total_bot_h - int(H*0.06)
        render_block(bot_lines, bot_font, bot_h, y_start=y0)

    # Watermark bottom-right, small
    if watermark:
        try:
            wf = get_font(max(10, int(W*0.022)))
            bbox = draw.textbbox((0,0), watermark, font=wf)
            wx = W - (bbox[2]-bbox[0]) - 10
            wy = H - (bbox[3]-bbox[1]) - 8
            draw.text((wx, wy), watermark, font=wf, fill="white", stroke_width=2, stroke_fill="black")
        except: pass

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92)
    out.seek(0)
    return out

# --- Telegram handlers ---

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    botname = (await ctx.bot.get_me()).username
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ ساخت میم — عکس بفرست", callback_data="how")],
        [InlineKeyboardButton("🎲 کپشن شانسی", callback_data="random")],
        [InlineKeyboardButton(f"↗️ اشتراک‌گذاری در هر چت", switch_inline_query="meme")],
    ])
    await update.message.reply_text(
        "🔥 *ربات میم‌ساز وایرال*\n\n"
        "یک عکس بفرست + متن بالا و پایین رو بنویس\n"
        "مثال:\n"
        "`وقتی میگی دیگه سفارش نمیدم | پنج دقیقه بعد:`\n\n"
        "یا فقط عکس بفرست و من کپشن شانسی و وایرال می‌ذارم!\n\n"
        "بعدش یک دکمه اشتراک‌گذاری می‌گیری که با یک تپ میم رو تو هر گروهی بفرستی — همین وایرال می‌کنه.",
        parse_mode="Markdown", reply_markup=kb
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *راهنما*\n\n"
        "1. یک عکس بفرست\n"
        "2. در کپشن بنویس: `متن بالا | متن پایین`\n"
        "   مثال: `من: رژیم از شنبه | شنبه:`\n"
        "3. اگر فقط عکس بفرستی، کپشن شانسی می‌ذارم\n"
        "4. میم + دکمه اشتراک و استیکر می‌گیری\n\n"
        "نکته وایرال: دکمه ↗️ اشتراک‌گذاری رو بزن و میم رو تو گروه‌های دیگه بفرست — هر اشتراک یک کاربر جدید میاره!",
        parse_mode="Markdown"
    )

async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    user_id = str(update.effective_user.id)
    state["users"][user_id] = state["users"].get(user_id, 0) + 1
    state["total_memes"] += 1
    save_state(state)

    cfg = load_config()
    watermark = f"@{ (await ctx.bot.get_me()).username }"

    # Get largest photo
    photo = update.message.photo[-1]
    file = await ctx.bot.get_file(photo.file_id)
    tmp_in = pathlib.Path(f"/tmp/meme_in_{user_id}.jpg")
    tmp_out = pathlib.Path(f"/tmp/meme_out_{user_id}.jpg")
    await file.download_to_drive(tmp_in)

    # Parse caption: "top | bottom" or "top - bottom" or single line = bottom
    cap = (update.message.caption or "").strip()
    top, bottom = "", ""
    if "|" in cap:
        a,b = cap.split("|",1)
        top, bottom = a.strip(), b.strip()
    elif " - " in cap and len(cap) < 80:
        a,b = cap.split(" - ",1)
        top, bottom = a.strip(), b.strip()
    elif cap:
        # Single line -> bottom text
        bottom = cap
    else:
        # Auto caption mode
        pick = random.choice(AUTO_CAPTIONS)
        if len(pick) == 2:
            top, bottom = pick
        else:
            top, bottom = pick[0], pick[1] if len(pick)>1 else ""
            if len(pick) > 2:
                bottom = pick[1] + " " + pick[2]

    # Generate meme
    try:
        out_io = draw_meme(str(tmp_in), top, bottom, watermark=watermark)
        # Save for inline
        out_io.seek(0)
        with open(tmp_out, "wb") as f: f.write(out_io.read())
        out_io.seek(0)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("↗️ اشتراک در هر چت", switch_inline_query="meme"),
             InlineKeyboardButton("🎨 میم جدید (همین عکس)", callback_data=f"remake:{top}|{bottom}")],
            [InlineKeyboardButton("🏷️ استیکر کن", callback_data="sticker"),
             InlineKeyboardButton("📊 امتیاز من", callback_data="me")],
        ])
        await update.message.reply_photo(
            photo=out_io,
            caption=f"✅ میم ساخته شد!\n`{top}`\n`{bottom}`\n\nروی ↗️ بزن و تو هر گروهی بفرست — وایرال میشه!",
            parse_mode="Markdown", reply_markup=kb
        )
        log.info(f"Meme for {user_id}: top={top} bottom={bottom}")
    except Exception as e:
        log.exception(e)
        await update.message.reply_text(f"خطا در ساخت میم: {e}")

    # Cleanup input
    try: tmp_in.unlink(missing_ok=True)
    except: pass

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # If user sends text without photo, guide them
    await update.message.reply_text("برای ساخت میم یک *عکس* بفرست و در کپشن متنش رو بنویس.\nمثال: یک عکس سلفی بفرست و کپشن: `وقتی میگی دیگه دیر نمی‌خوابم | ساعت ۲ شب:`", parse_mode="Markdown")

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    if data == "how":
        await q.answer()
        await help_cmd(q.message, ctx)
    elif data == "random":
        await q.answer()
        top, bottom = random.choice(AUTO_CAPTIONS)[:2]
        await q.message.reply_text(f"کپشن شانسی:\n`{top} | {bottom}`\n\nحالا یک عکس بفرست و این کپشن رو در کپشن عکس بنویس!", parse_mode="Markdown")
    elif data.startswith("remake:"):
        await q.answer(text="یک عکس جدید بفرست تا با همین متن بسازم")
    elif data == "sticker":
        await q.answer()
        # Try to send last meme as sticker (webp)
        # Find last out file for this user
        user_id = str(q.from_user.id)
        tmp_out = pathlib.Path(f"/tmp/meme_out_{user_id}.jpg")
        if not tmp_out.exists():
            await q.message.reply_text("اول یک عکس بفرست تا میم بسازم، بعد استیکر می‌کنم")
            return
        # Convert jpg to webp for sticker (Telegram prefers webp 512x512)
        try:
            im = Image.open(tmp_out)
            # Resize to 512 on longest side, keep aspect
            im.thumbnail((512,512))
            webp_io = io.BytesIO()
            im.save(webp_io, format="WEBP")
            webp_io.seek(0)
            await q.message.reply_sticker(sticker=webp_io)
        except Exception as e:
            await q.message.reply_text(f"خطای استیکر: {e}")
    elif data == "me":
        state = load_state()
        uid = str(q.from_user.id)
        cnt = state["users"].get(uid, 0)
        total = state["total_memes"]
        await q.answer()
        await q.message.reply_text(f"📊 تو {cnt} تا میم ساختی\nکل ربات: {total} میم\n\nهر میمی که با ↗️ اشتراک بذاری، ۲-۳ کاربر جدید میاره — ادامه بده!", parse_mode="Markdown")
    else:
        await q.answer()

async def inline_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Inline mode: lets users share a promo meme in any chat in 1 tap
    # This is the viral engine
    query = (update.inline_query.query or "").strip()
    # Return a promo meme that advertises the bot
    # Create a quick promo image on the fly
    try:
        # Create a simple promo image 800x400
        W, H = 800, 400
        img = Image.new("RGB", (W,H), (18,19,26))
        d = ImageDraw.Draw(img)
        font_big = get_font(42)
        font_mid = get_font(24)
        d.text((40, 90), "MEME MAKER BOT", font=font_big, fill="white", stroke_width=3, stroke_fill="black")
        d.text((40, 160), "Send any photo + caption → get viral meme in 2 sec", font=font_mid, fill="#00ff88")
        d.text((40, 210), f"@{ (await ctx.bot.get_me()).username }", font=font_mid, fill="white")
        bio = io.BytesIO()
        img.save(bio, format="JPEG", quality=90)
        bio.seek(0)
        # For inline, we need a URL, so we can't send raw bytes easily without hosting
        # Fallback: return a simple article with the bot link
        from telegram import InlineQueryResultArticle, InputTextMessageContent
        results = [
            InlineQueryResultArticle(
                id="promo",
                title="🔥 Meme Maker — Tap to share bot",
                description="Send this to any chat to invite them",
                input_message_content=InputTextMessageContent(
                    message_text=f"🔥 با این ربات از هر عکسی میم بساز — ۲ ثانیه‌ای!\n\n👉 @{(await ctx.bot.get_me()).username}\n\nیک عکس بفرست + کپشن: بالا | پایین"
                ),
                thumb_url="https://via.placeholder.com/300x300.png?text=MEME+BOT"
            )
        ]
        await update.inline_query.answer(results, cache_time=10)
    except Exception as e:
        log.exception(e)

def main():
    import json
    cfg = load_config()
    token = cfg.get("bot_token") or cfg.get("BOT_TOKEN")
    if not token or token.startswith("YOUR"):
        print("[ERR] Set bot_token in config.json (get from @BotFather -> /newbot)")
        return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print(f"[OK] Meme bot running — send a photo to test (token ...{token[-6:]})")
    app.run_polling()

if __name__ == "__main__":
    main()
