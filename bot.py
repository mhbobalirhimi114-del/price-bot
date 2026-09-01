import os
import json
import re
import asyncio
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


# =========================================================
# SETTINGS
# =========================================================

# برای Pydroid 3:
# توکن را اینجا وارد کن
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# اگر خواستی مستقیم داخل Pydroid اجرا کنی:
# BOT_TOKEN = "توکن_ربات_اینجا"

UPDATE_SECONDS = 60

GROUPS_FILE = "groups.json"

# =========================================================
# PRICE SOURCES
# =========================================================

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

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    web.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


# =========================================================
# GROUP STORAGE
# =========================================================

def load_groups():

    if not os.path.exists(GROUPS_FILE):
        return {}

    try:

        with open(
            GROUPS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as e:

        print(
            "GROUP LOAD ERROR:",
            e
        )

        return {}


def save_groups(groups):

    try:

        with open(
            GROUPS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                groups,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print(
            "GROUP SAVE ERROR:",
            e
        )


# =========================================================
# NUMBER HELPERS
# =========================================================

def fa_number(value):

    table = str.maketrans(
        "0123456789,.",
        "۰۱۲۳۴۵۶۷۸۹،."
    )

    return str(value).translate(
        table
    )


def toman(value):

    # TGJU معمولاً قیمت را ریالی می‌دهد.
    # تبدیل ریال به تومان
    return int(value) // 10


# =========================================================
# PRICE SCRAPER
# =========================================================

def get_price(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        patterns = [

            r"نرخ فعلی::\s*([\d,٬]+)",

            r"نرخ فعلی:\s*([\d,٬]+)"

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:

                number = (
                    match.group(1)
                    .replace(",", "")
                    .replace("٬", "")
                )

                return int(number)

        print(
            "PRICE NOT FOUND:",
            url
        )

        return None

    except Exception as e:

        print(
            "PRICE ERROR:",
            url,
            e
        )

        return None


def get_prices():

    prices = {}

    for name, url in URLS.items():

        prices[name] = get_price(
            url
        )

    if any(
        value is None
        for value in prices.values()
    ):

        return None

    return prices


# =========================================================
# PRICE MESSAGE
# =========================================================

def make_message(prices):

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

    dollar = toman(
        prices["dollar"]
    )

    euro = toman(
        prices["euro"]
    )

    gold18 = toman(
        prices["gold18"]
    )

    coin = toman(
        prices["coin"]
    )

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
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        """
🤖 <b>ربات قیمت دلار و طلا</b>

👋 خوش آمدید!

💰 دریافت قیمت لحظه‌ای:

/price

📢 فعال کردن قیمت خودکار در گروه:

/on

🛑 خاموش کردن قیمت خودکار در گروه:

/off

ℹ️ قیمت‌ها هر ۱ دقیقه بروزرسانی می‌شوند.
""",

        parse_mode="HTML"
    )


# =========================================================
# PRICE
# =========================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    msg = await update.message.reply_text(
        "⏳ در حال دریافت قیمت..."
    )

    prices = await asyncio.to_thread(
        get_prices
    )

    if prices is None:

        await msg.edit_text(

            "❌ دریافت قیمت ناموفق بود.\n\n"
            "لطفاً چند لحظه بعد دوباره امتحان کنید."
        )

        return

    await msg.edit_text(

        make_message(prices),

        parse_mode="HTML"
    )


# =========================================================
# ON
# =========================================================

async def on_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat

    # فقط گروه
    if chat.type not in (
        "group",
        "supergroup"
    ):

        await update.message.reply_text(

            "❌ دستور /on فقط داخل گروه قابل استفاده است."
        )

        return

    groups = load_groups()

    chat_id = str(
        chat.id
    )

    if chat_id not in groups:

        groups[chat_id] = {

            "message_id": None,

            "enabled": True
        }

    else:

        groups[chat_id]["enabled"] = True

    save_groups(
        groups
    )

    await update.message.reply_text(

        "✅ قیمت خودکار فعال شد.\n\n"
        "🔄 قیمت هر ۱ دقیقه بروزرسانی می‌شود."
    )


# =========================================================
# OFF
# =========================================================

async def off_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat

    if chat.type not in (
        "group",
        "supergroup"
    ):

        await update.message.reply_text(

            "❌ دستور /off فقط داخل گروه قابل استفاده است."
        )

        return

    groups = load_groups()

    chat_id = str(
        chat.id
    )

    if chat_id in groups:

        del groups[chat_id]

        save_groups(
            groups
        )

    await update.message.reply_text(

        "🛑 قیمت خودکار برای این گروه خاموش شد."
    )


# =========================================================
# UPDATE GROUPS
# =========================================================

async def update_groups(
    context: ContextTypes.DEFAULT_TYPE
):

    groups = load_groups()

    if not groups:
        return

    prices = await asyncio.to_thread(
        get_prices
    )

    if prices is None:

        print(
            "❌ قیمت دریافت نشد."
        )

        return

    text = make_message(
        prices
    )

    changed = False

    for chat_id, info in list(
        groups.items()
    ):

        try:

            # اگر خاموش شده
            if not info.get(
                "enabled",
                True
            ):

                continue

            message_id = info.get(
                "message_id"
            )

            # اولین پیام
            if not message_id:

                msg = await context.bot.send_message(

                    chat_id=int(
                        chat_id
                    ),

                    text=text,

                    parse_mode="HTML"
                )

                groups[chat_id][
                    "message_id"
                ] = msg.message_id

                changed = True

            else:

                # همان پیام را ویرایش می‌کنیم
                await context.bot.edit_message_text(

                    chat_id=int(
                        chat_id
                    ),

                    message_id=message_id,

                    text=text,

                    parse_mode="HTML"
                )

        except Exception as e:

            print(
                "GROUP ERROR:",
                chat_id,
                e
            )

    if changed:

        save_groups(
            groups
        )


# =========================================================
# STATUS
# =========================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    groups = load_groups()

    await update.message.reply_text(

        "🤖 <b>وضعیت ربات</b>\n\n"
        "🟢 ربات فعال است\n"
        "🔄 بروزرسانی: هر ۱ دقیقه\n"
        f"👥 تعداد گروه‌های فعال: "
        f"<b>{fa_number(len(groups))}</b>",

        parse_mode="HTML"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(

            "BOT_TOKEN تنظیم نشده است.\n\n"
            "برای Pydroid 3 توکن را در بالای کد "
            "داخل BOT_TOKEN قرار بده."
        )

    application = (

        Application

        .builder()

        .token(
            BOT_TOKEN
        )

        .build()
    )

    # /start
    application.add_handler(

        CommandHandler(
            "start",
            start
        )
    )

    # /price
    application.add_handler(

        CommandHandler(
            "price",
            price
        )
    )

    # /on
    application.add_handler(

        CommandHandler(
            "on",
            on_command
        )
    )

    # /off
    application.add_handler(

        CommandHandler(
            "off",
            off_command
        )
    )

    # /status
    application.add_handler(

        CommandHandler(
            "status",
            status
        )
    )

    # Job Queue
    if application.job_queue is None:

        raise RuntimeError(

            "JobQueue نصب نیست.\n"
            "این دستور را اجرا کن:\n\n"
            "pip install "
            "\"python-telegram-bot[job-queue]\""
        )

    application.job_queue.run_repeating(

        update_groups,

        interval=UPDATE_SECONDS,

        first=10
    )

    # Flask
    threading.Thread(

        target=run_web,

        daemon=True

    ).start()

    print(
        "================================"
    )

    print(
        "🤖 BOT STARTED"
    )

    print(
        "💰 PRICE UPDATE: 60 SECONDS"
    )

    print(
        "🔐 FORCE SUBSCRIPTION: DISABLED"
    )

    print(
        "================================"
    )

    application.run_polling()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
