import os
import json
import re
import asyncio
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

UPDATE_SECONDS = 60
GROUPS_FILE = "groups.json"

CHANNELS = [
    {
        "username": "@Fankbass1",
        "url": "https://t.me/Fankbass1",
    },
    {
        "username": "@Fankbass",
        "url": "https://t.me/Fankbass",
    },
]

URLS = {
    "dollar": "https://www.tgju.org/profile/price_dollar_dt",
    "euro": "https://www.tgju.org/profile/price_eur",
    "gold18": "https://www.tgju.org/profile/geram18",
    "coin": "https://www.tgju.org/profile/sekee",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12) "
        "AppleWebKit/537.36 "
        "Chrome/120.0 Mobile Safari/537.36"
    )
}

# =========================================================
# WEB SERVER
# =========================================================

web = Flask(__name__)


@web.route("/")
def home():
    return "Telegram Price Bot is running!"


@web.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.environ.get("PORT", "10000"))

    web.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False,
    )


# =========================================================
# GROUP STORAGE
# =========================================================

def load_groups():
    if not os.path.exists(GROUPS_FILE):
        return {}

    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}

    except Exception as e:
        print("GROUP LOAD ERROR:", e)
        return {}


def save_groups(groups):
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                groups,
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:
        print("GROUP SAVE ERROR:", e)


# =========================================================
# NUMBER HELPERS
# =========================================================

def fa_number(value):
    table = str.maketrans(
        "0123456789,.",
        "۰۱۲۳۴۵۶۷۸۹،.",
    )

    return str(value).translate(table)


def toman(value):
    # TGJU usually returns Rial.
    # Convert Rial -> Toman.
    return int(value) // 10


# =========================================================
# PRICE SCRAPER
# =========================================================

def get_price(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

        patterns = [
            r"نرخ فعلی::\s*([\d,٬]+)",
            r"نرخ فعلی:\s*([\d,٬]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)

            if match:
                number = (
                    match.group(1)
                    .replace(",", "")
                    .replace("٬", "")
                )

                return int(number)

        print("PRICE NOT FOUND:", url)
        return None

    except Exception as e:
        print("PRICE ERROR:", url, e)
        return None


def get_prices():
    prices = {}

    for name, url in URLS.items():
        prices[name] = get_price(url)

    if any(value is None for value in prices.values()):
        return None

    return prices


# =========================================================
# PRICE MESSAGE
# =========================================================

def make_message(prices):
    now = datetime.now().strftime("%H:%M:%S")

    dollar = toman(prices["dollar"])
    euro = toman(prices["euro"])
    gold18 = toman(prices["gold18"])
    coin = toman(prices["coin"])

    return f"""
💰 <b>قیمت لحظه‌ای بازار</b>

━━━━━━━━━━━━━━━━━━

💵 دلار آزاد
<b>{fa_number(f"{dollar:,}")} تومان</b>

💶 یورو
<b>{fa_number(f"{euro:,}")} تومان</b>

🪙 طلای ۱۸ عیار
<b>{fa_number(f"{gold18:,}")} تومان / گرم</b>

👑 سکه امامی
<b>{fa_number(f"{coin:,}")} تومان</b>

━━━━━━━━━━━━━━━━━━

🕐 آخرین بروزرسانی:
<b>{fa_number(now)}</b>

🔄 بروزرسانی خودکار: هر ۱ دقیقه

📊 منبع: TGJU
"""


# =========================================================
# SUBSCRIPTION
# =========================================================

def subscription_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 عضویت کانال اول",
                    url=CHANNELS[0]["url"],
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 عضویت کانال دوم",
                    url=CHANNELS[1]["url"],
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ تأیید عضویت",
                    callback_data="check_subscription",
                )
            ],
        ]
    )


def subscription_text():
    return """
🔐 <b>عضویت اجباری</b>

برای استفاده از ربات باید در هر دو کانال عضو شوید:

📢 @Fankbass1

📢 @Fankbass

بعد از عضویت روی:

✅ <b>تأیید عضویت</b>

بزنید.
"""


async def check_subscription(bot, user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(
                channel["username"],
                user_id,
            )

            if member.status in (
                "creator",
                "administrator",
                "member",
            ):
                continue

            if (
                member.status == "restricted"
                and getattr(member, "is_member", False)
            ):
                continue

            return False

        except Exception as e:
            print("SUB ERROR:", channel["username"], e)
            return False

    return True


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_subscription(
        context.bot,
        user_id,
    ):
        await update.message.reply_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        """
🤖 <b>ربات قیمت دلار و طلا</b>

✅ عضویت شما تأیید شد.

💰 دریافت قیمت:

/price

برای فعال کردن قیمت خودکار در گروه:

/on

برای خاموش کردن:

/off
""",
        parse_mode="HTML",
    )


# =========================================================
# SUBSCRIPTION BUTTON
# =========================================================

async def check_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if not await check_subscription(
        context.bot,
        user_id,
    ):
        await query.edit_message_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )
        return

    await query.edit_message_text(
        """
✅ <b>عضویت تأیید شد!</b>

حالا می‌توانید از ربات استفاده کنید.

💰 /price
""",
        parse_mode="HTML",
    )


# =========================================================
# PRICE COMMAND
# =========================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    if not await check_subscription(
        context.bot,
        user_id,
    ):
        await update.message.reply_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )
        return

    msg = await update.message.reply_text(
        "⏳ در حال دریافت قیمت..."
    )

    prices = await asyncio.to_thread(get_prices)

    if prices is None:
        await msg.edit_text(
            "❌ دریافت قیمت ناموفق بود.\n"
            "لطفاً چند لحظه بعد دوباره امتحان کنید."
        )
        return

    await msg.edit_text(
        make_message(prices),
        parse_mode="HTML",
    )


# =========================================================
# ON
# =========================================================

async def on_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "❌ این دستور فقط داخل گروه قابل استفاده است."
        )
        return

    user_id = update.effective_user.id

    if not await check_subscription(
        context.bot,
        user_id,
    ):
        await update.message.reply_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML",
        )
        return

    groups = load_groups()
    chat_id = str(chat.id)

    if chat_id not in groups:
        groups[chat_id] = {
            "message_id": None
        }

        save_groups(groups)

    await update.message.reply_text(
        "✅ قیمت خودکار فعال شد.\n"
        "قیمت هر ۱ دقیقه به‌روزرسانی می‌شود."
    )


# =========================================================
# OFF
# =========================================================

async def off_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat_id = str(update.effective_chat.id)

    groups = load_groups()

    if chat_id in groups:
        del groups[chat_id]
        save_groups(groups)

    await update.message.reply_text(
        "🛑 قیمت خودکار خاموش شد."
    )


# =========================================================
# UPDATE GROUPS
# =========================================================

async def update_groups(
    context: ContextTypes.DEFAULT_TYPE,
):
    groups = load_groups()

    if not groups:
        return

    prices = await asyncio.to_thread(get_prices)

    if prices is None:
        print("❌ قیمت دریافت نشد.")
        return

    text = make_message(prices)

    changed = False

    for chat_id, info in list(groups.items()):
        try:
            message_id = info.get("message_id")

            if not message_id:
                msg = await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode="HTML",
                )

                groups[chat_id]["message_id"] = msg.message_id
                changed = True

            else:
                await context.bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=message_id,
                    text=text,
                    parse_mode="HTML",
                )

        except Exception as e:
            print("GROUP ERROR:", chat_id, e)

    if changed:
        save_groups(groups)


# =========================================================
# MAIN
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing"
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("price", price)
    )

    application.add_handler(
        CommandHandler("on", on_command)
    )

    application.add_handler(
        CommandHandler("off", off_command)
    )

    application.add_handler(
        CallbackQueryHandler(
            check_button,
            pattern="^check_subscription$",
        )
    )

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue is unavailable. "
            "Install python-telegram-bot[job-queue]."
        )

    application.job_queue.run_repeating(
        update_groups,
        interval=UPDATE_SECONDS,
        first=10,
    )

    print("🤖 BOT STARTED")
    print("🔄 UPDATE: 60 SECONDS")

    # Flask health server
    threading.Thread(
        target=run_web,
        daemon=True,
    ).start()

    application.run_polling()


if __name__ == "__main__":
    main()
