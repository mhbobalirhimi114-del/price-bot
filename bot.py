import os
import json
import re
import asyncio
import threading
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)


BOT_TOKEN = os.environ.get("8432734624:AAEnO5Ipsq8PmX-4aQueQljO0_nOlS7CEUk)
UPDATE_SECONDS = 60
GROUPS_FILE = "groups.json"


CHANNELS = [
    {
        "username": "@Fankbass1",
        "url": "https://t.me/Fankbass1"
    },
    {
        "username": "@Fankbass",
        "url": "https://t.me/Fankbass"
    }
]


URLS = {
    "dollar": "https://www.tgju.org/profile/price_dollar_dt",
    "euro": "https://www.tgju.org/profile/price_eur",
    "gold18": "https://www.tgju.org/profile/geram18",
    "coin": "https://www.tgju.org/profile/sekee"
}


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Linux; Android 12) "
        "AppleWebKit/537.36 "
        "Chrome/120.0 Mobile Safari/537.36"
}


# =========================
# Web server برای Render
# =========================

web = Flask(__name__)


@web.route("/")
def home():
    return "Telegram Price Bot is running!"


@web.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.environ.get("PORT", 10000))

    web.run(
        host="0.0.0.0",
        port=port
    )


# =========================
# گروه‌ها
# =========================

def load_groups():

    if not os.path.exists(GROUPS_FILE):
        return {}

    try:

        with open(
            GROUPS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return {}


def save_groups(groups):

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


# =========================
# اعداد فارسی
# =========================

def fa_number(value):

    table = str.maketrans(
        "0123456789,.",
        "۰۱۲۳۴۵۶۷۸۹،."
    )

    return str(value).translate(table)


def toman(value):
    return int(value) // 10


# =========================
# دریافت قیمت
# =========================

def get_price(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
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
            r"نرخ فعلی::\s*([\d,]+)",
            r"نرخ فعلی:\s*([\d,]+)"
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

        return None

    except Exception as e:

        print("PRICE ERROR:", e)

        return None


def get_prices():

    prices = {}

    for name, url in URLS.items():

        prices[name] = get_price(url)

    if any(
        value is None
        for value in prices.values()
    ):

        return None

    return prices


# =========================
# پیام قیمت
# =========================

def make_message(prices):

    now = datetime.now().strftime(
        "%H:%M:%S"
    )

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

🔄 بروزرسانی: هر ۱ دقیقه

📊 منبع: TGJU
"""


# =========================
# عضویت اجباری
# =========================

def subscription_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "📢 عضویت کانال اول",
                url=CHANNELS[0]["url"]
            )
        ],

        [
            InlineKeyboardButton(
                "📢 عضویت کانال دوم",
                url=CHANNELS[1]["url"]
            )
        ],

        [
            InlineKeyboardButton(
                "✅ تأیید عضویت",
                callback_data="check_subscription"
            )
        ]

    ])


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


async def check_subscription(
    bot,
    user_id
):

    for channel in CHANNELS:

        try:

            member = await bot.get_chat_member(
                channel["username"],
                user_id
            )

            if member.status in [
                "creator",
                "administrator",
                "member"
            ]:

                continue

            if (
                member.status == "restricted"
                and member.is_member
            ):

                continue

            return False

        except Exception as e:

            print(
                "SUB ERROR:",
                e
            )

            return False

    return True


# =========================
# /start
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not await check_subscription(
        context.bot,
        user_id
    ):

        await update.message.reply_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
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
        parse_mode="HTML"
    )


# =========================
# تأیید عضویت
# =========================

async def check_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if not await check_subscription(
        context.bot,
        user_id
    ):

        await query.edit_message_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return

    await query.edit_message_text(
        """
✅ <b>عضویت تأیید شد!</b>

حالا می‌توانید از ربات استفاده کنید.

💰 /price
""",
        parse_mode="HTML"
    )


# =========================
# /price
# =========================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not await check_subscription(
        context.bot,
        user_id
    ):

        await update.message.reply_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

        return

    msg = await update.message.reply_text(
        "⏳ در حال دریافت قیمت..."
    )

    prices = await asyncio.to_thread(
        get_prices
    )

    if prices is None:

        await msg.edit_text(
            "❌ دریافت قیمت ناموفق بود."
        )

        return

    await msg.edit_text(
        make_message(prices),
        parse_mode="HTML"
    )


# =========================
# /on
# =========================

async def on_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat

    if chat.type not in [
        "group",
        "supergroup"
    ]:

        await update.message.reply_text(
            "❌ این دستور فقط داخل گروه قابل استفاده است."
        )

        return

    user_id = update.effective_user.id

    if not await check_subscription(
        context.bot,
        user_id
    ):

        await update.message.reply_text(
            subscription_text(),
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
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
        "✅ قیمت خودکار فعال شد."
    )


# =========================
# /off
# =========================

async def off_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = str(
        update.effective_chat.id
    )

    groups = load_groups()

    if chat_id in groups:

        del groups[chat_id]

        save_groups(groups)

    await update.message.reply_text(
        "🛑 قیمت خودکار خاموش شد."
    )


# =========================
# بروزرسانی گروه
# =========================

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

    text = make_message(prices)

    changed = False

    for chat_id, info in list(
        groups.items()
    ):

        try:

            message_id = info.get(
                "message_id"
            )

            if not message_id:

                msg = await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode="HTML"
                )

                groups[chat_id][
                    "message_id"
                ] = msg.message_id

                changed = True

            else:

                await context.bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=message_id,
                    text=text,
                    parse_mode="HTML"
                )

        except Exception as e:

            print(
                "GROUP ERROR:",
                e
            )

    if changed:

        save_groups(groups)


# =========================
# اجرای ربات
# =========================

async def run_bot():

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "price",
            price
        )
    )

    application.add_handler(
        CommandHandler(
            "on",
            on_command
        )
    )

    application.add_handler(
        CommandHandler(
            "off",
            off_command
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            check_button,
            pattern="^check_subscription$"
        )
    )

    application.job_queue.run_repeating(
        update_groups,
        interval=UPDATE_SECONDS,
        first=10
    )

    print("🤖 BOT STARTED")
    print("🔄 UPDATE: 60 SECONDS")

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    try:

        while True:

            await asyncio.sleep(3600)

    finally:

        await application.updater.stop()
        await application.stop()
        await application.shutdown()


# =========================
# START
# =========================

if __name__ == "__main__":

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing"
        )

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    asyncio.run(
        run_bot()
)
