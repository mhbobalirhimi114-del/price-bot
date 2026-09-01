import os
import json
import asyncio
import threading
from datetime import datetime

import requests
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

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()

UPDATE_SECONDS = 60

GROUPS_FILE = "groups.json"

REQUEST_TIMEOUT = 15


# =========================================================
# API SOURCES
# =========================================================

# اصلی بازار ایران
PERSIAN_TOOLBOX_URL = (
    "https://persiantoolbox.ir/api/market"
)

# پشتیبان طلا
GOLD_API_URL = (
    "https://api.goldprice.dev/v1/prices"
)

# پشتیبان ارزهای جهانی
FRANKFURTER_URL = (
    "https://api.frankfurter.dev/v2/rates"
)


HEADERS = {
    "User-Agent":
        "NerKhinoo/2.0 "
        "(Telegram Price Bot)"
}


# =========================================================
# WEB SERVER
# =========================================================

web = Flask(__name__)


@web.route("/")
def home():

    return (
        "NerKhinoo Price Bot is running!"
    )


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

    if not os.path.exists(
        GROUPS_FILE
    ):
        return {}

    try:

        with open(
            GROUPS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):

            return data

    except Exception as error:

        print(
            "GROUP LOAD ERROR:",
            error
        )

    return {}


def save_groups(groups):

    try:

        with open(
            GROUPS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                groups,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:

        print(
            "GROUP SAVE ERROR:",
            error
        )


# =========================================================
# NUMBER HELPERS
# =========================================================

def fa_number(value):

    table = str.maketrans(
        "0123456789,.",
        "۰۱۲۳۴۵۶۷۸۹،."
    )

    return str(value).translate(table)


def clean_number(value):

    if value is None:
        return None

    try:

        text = str(value)

        text = (
            text
            .replace(",", "")
            .replace("٬", "")
            .replace(" ", "")
        )

        return float(text)

    except Exception:

        return None


def format_number(value):

    if value is None:
        return "—"

    try:

        value = float(value)

        if value >= 100:

            return fa_number(
                f"{int(round(value)):,}"
            )

        return fa_number(
            f"{value:,.4f}"
        )

    except Exception:

        return "—"


def toman_from_irr(value):

    value = clean_number(value)

    if value is None:
        return None

    return value / 10


# =========================================================
# PERSIAN TOOLBOX
# =========================================================

def get_persian_toolbox():

    try:

        response = requests.get(
            PERSIAN_TOOLBOX_URL,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            params={
                "_": int(
                    datetime.now().timestamp()
                )
            }
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("ok"):
            return None

        return data

    except Exception as error:

        print(
            "PERSIAN TOOLBOX ERROR:",
            error
        )

        return None


# =========================================================
# GOLDPRICE.DEV
# =========================================================

def get_gold_backup():

    try:

        response = requests.get(

            GOLD_API_URL,

            headers=HEADERS,

            timeout=REQUEST_TIMEOUT,

            params={
                "symbol":
                    "XAU-USD-SPOT"
            }
        )

        response.raise_for_status()

        data = response.json()

        symbols = data.get(
            "symbols",
            []
        )

        if not symbols:
            return None

        item = symbols[0]

        return item

    except Exception as error:

        print(
            "GOLD BACKUP ERROR:",
            error
        )

        return None


# =========================================================
# FRANKFURTER
# =========================================================

def get_frankfurter():

    try:

        response = requests.get(

            FRANKFURTER_URL,

            headers=HEADERS,

            timeout=REQUEST_TIMEOUT,

            params={
                "base": "USD"
            }
        )

        response.raise_for_status()

        return response.json()

    except Exception as error:

        print(
            "FRANKFURTER ERROR:",
            error
        )

        return None


# =========================================================
# BUILD MARKET DATA
# =========================================================

def get_prices():

    market = {

        "dollar": None,

        "euro": None,

        "gold18": None,

        "coin": None,

        "half_coin": None,

        "quarter_coin": None,

        "gram_coin": None,

        "source": "NONE",

        "source_time": None,

        "freshness": None,

        "gold_source": None,

        "currency_source": None,
    }


    # =====================================================
    # 1. PERSIAN TOOLBOX
    # =====================================================

    pt = get_persian_toolbox()


    if pt:

        data = pt.get(
            "data",
            {}
        )

        currencies = data.get(
            "currencies",
            {}
        )


        # -------------------------------------------------
        # IRR
        # -------------------------------------------------

        irr_item = currencies.get(
            "IRR"
        )

        irr_rate = None

        if isinstance(
            irr_item,
            dict
        ):

            irr_rate = clean_number(
                irr_item.get(
                    "rate"
                )
            )

        else:

            irr_rate = clean_number(
                irr_item
            )


        # -------------------------------------------------
        # USD
        # -------------------------------------------------

        usd_item = currencies.get(
            "USD"
        )

        usd_rate = None

        if isinstance(
            usd_item,
            dict
        ):

            usd_rate = clean_number(
                usd_item.get(
                    "rate"
                )
            )

        else:

            usd_rate = clean_number(
                usd_item
            )


        # -------------------------------------------------
        # EUR
        # -------------------------------------------------

        eur_item = currencies.get(
            "EUR"
        )

        eur_rate = None

        if isinstance(
            eur_item,
            dict
        ):

            eur_rate = clean_number(
                eur_item.get(
                    "rate"
                )
            )

        else:

            eur_rate = clean_number(
                eur_item
            )


        # =================================================
        # IMPORTANT
        #
        # PersianToolbox currencies are relative to USD.
        #
        # Example:
        #
        # USD = 1
        # IRR = 42000
        #
        # Therefore:
        #
        # USD in IRR = 42000 / 1
        # EUR in IRR = 42000 / EUR_RATE
        # =================================================


        if (
            irr_rate is not None
            and usd_rate is not None
            and usd_rate != 0
        ):

            market[
                "dollar"
            ] = toman_from_irr(
                irr_rate / usd_rate
            )


        if (
            irr_rate is not None
            and eur_rate is not None
            and eur_rate != 0
        ):

            market[
                "euro"
            ] = toman_from_irr(
                irr_rate / eur_rate
            )


        # -------------------------------------------------
        # GOLD
        # -------------------------------------------------

        gold = data.get(
            "gold"
        )


        if isinstance(
            gold,
            dict
        ):

            gold_price = clean_number(
                gold.get(
                    "pricePerGram"
                )
            )

            if gold_price is not None:

                market[
                    "gold18"
                ] = toman_from_irr(
                    gold_price
                )


        # -------------------------------------------------
        # FRESHNESS
        # -------------------------------------------------

        market[
            "freshness"
        ] = data.get(
            "freshness"
        )


        market[
            "source_time"
        ] = data.get(
            "timestamp"
        )


        market[
            "source"
        ] = "PersianToolbox"


        market[
            "currency_source"
        ] = "PersianToolbox"


        market[
            "gold_source"
        ] = "PersianToolbox"


    # =====================================================
    # 2. GOLD BACKUP
    # =====================================================

    # اگر طلای اصلی موجود نبود
    if market["gold18"] is None:

        gold_backup = get_gold_backup()


        if gold_backup:

            usd_gold = clean_number(
                gold_backup.get(
                    "price"
                )
            )


            # اگر قیمت طلا به دلار داریم
            # و دلار ایران هم داریم،
            # تبدیل به تومان انجام می‌دهیم.

            dollar = market[
                "dollar"
            ]


            if (
                usd_gold is not None
                and dollar is not None
            ):

                # XAU price is per troy ounce.
                # 31.1034768 grams / troy ounce.

                gold24_per_gram = (
                    usd_gold
                    / 31.1034768
                )


                gold18_usd = (
                    gold24_per_gram
                    * 18
                    / 24
                )


                market[
                    "gold18"
                ] = (
                    gold18_usd
                    * dollar
                )


                market[
                    "gold_source"
                ] = "GoldPrice.dev"


    # =====================================================
    # 3. FRANKFURTER BACKUP
    # =====================================================

    frank = get_frankfurter()


    if frank:

        rates = frank.get(
            "rates",
            []
        )


        # تبدیل لیست به dictionary

        rate_map = {}


        if isinstance(
            rates,
            list
        ):

            for item in rates:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                quote = item.get(
                    "quote"
                )

                rate = clean_number(
                    item.get(
                        "rate"
                    )
                )

                if quote and rate:

                    rate_map[
                        quote
                    ] = rate


        # -------------------------------------------------
        # این قسمت فقط زمانی استفاده می‌شود
        # که PersianToolbox نرخ یورو را ندهد.
        #
        # چون Frankfurter نرخ مرجع جهانی است،
        # نه دلار آزاد ایران.
        # -------------------------------------------------

        if market[
            "euro"
        ] is None:

            eur_rate = rate_map.get(
                "EUR"
            )


            dollar = market[
                "dollar"
            ]


            if (
                eur_rate
                and dollar
            ):

                market[
                    "euro"
                ] = (
                    dollar
                    / eur_rate
                )


                market[
                    "currency_source"
                ] = (
                    "Frankfurter"
                )


    # =====================================================
    # RETURN
    # =====================================================

    return market


# =========================================================
# MESSAGE
# =========================================================

def make_message(prices):

    now = datetime.now().strftime(
        "%H:%M:%S"
    )


    source = prices.get(
        "source",
        "—"
    )


    currency_source = prices.get(
        "currency_source",
        "—"
    )


    gold_source = prices.get(
        "gold_source",
        "—"
    )


    freshness = prices.get(
        "freshness"
    )


    freshness_text = (
        str(freshness)
        if freshness
        else
        "نامشخص"
    )


    return f"""
💰 <b>قیمت لحظه‌ای بازار</b>

━━━━━━━━━━━━━━━━━━

💵 <b>دلار آزاد</b>
{format_number(prices.get("dollar"))} تومان

💶 <b>یورو</b>
{format_number(prices.get("euro"))} تومان

🪙 <b>طلای ۱۸ عیار</b>
{format_number(prices.get("gold18"))} تومان / گرم

👑 <b>سکه امامی</b>
{format_number(prices.get("coin"))} تومان

🪙 <b>نیم سکه</b>
{format_number(prices.get("half_coin"))} تومان

🪙 <b>ربع سکه</b>
{format_number(prices.get("quarter_coin"))} تومان

🪙 <b>سکه گرمی</b>
{format_number(prices.get("gram_coin"))} تومان

━━━━━━━━━━━━━━━━━━

🟢 ارز:
<b>{currency_source}</b>

🟡 طلا:
<b>{gold_source}</b>

📡 وضعیت:
<b>{freshness_text}</b>

🕐 زمان دریافت ربات:
<b>{fa_number(now)}</b>

🔄 بروزرسانی خودکار:
<b>هر ۱ دقیقه</b>

━━━━━━━━━━━━━━━━━━

📊 NerKhinoo
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
🤖 <b>NerKhinoo</b>

💰 ربات حرفه‌ای قیمت بازار

━━━━━━━━━━━━━━━━━━

💵 دلار آزاد
💶 یورو
🪙 طلای ۱۸ عیار
👑 سکه امامی
🪙 نیم سکه
🪙 ربع سکه
🪙 سکه گرمی

━━━━━━━━━━━━━━━━━━

📌 دستورات:

/price
💰 دریافت آخرین قیمت

/on
🔄 فعال کردن قیمت خودکار گروه

/off
🛑 خاموش کردن قیمت خودکار

/status
📊 وضعیت سیستم

━━━━━━━━━━━━━━━━━━

⚡ چند منبع برای دریافت نرخ
🔁 سیستم Backup خودکار
"""
        ,
        parse_mode="HTML"
    )


# =========================================================
# PRICE
# =========================================================

async def price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = await update.message.reply_text(
        "⏳ در حال دریافت آخرین نرخ..."
    )


    prices = await asyncio.to_thread(
        get_prices
    )


    if prices is None:

        await message.edit_text(

            "❌ دریافت قیمت ناموفق بود.\n"
            "چند لحظه بعد دوباره امتحان کنید."
        )

        return


    await message.edit_text(

        make_message(
            prices
        ),

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


    if chat.type not in (
        "group",
        "supergroup"
    ):

        await update.message.reply_text(
            "❌ این دستور فقط داخل گروه است."
        )

        return


    groups = load_groups()


    chat_id = str(
        chat.id
    )


    old = groups.get(
        chat_id,
        {}
    )


    groups[
        chat_id
    ] = {

        "message_id":
            old.get(
                "message_id"
            ),

        "enabled":
            True
    }


    save_groups(
        groups
    )


    await update.message.reply_text(

        "✅ قیمت خودکار فعال شد.\n\n"
        "🔄 بروزرسانی هر ۱ دقیقه."
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
            "❌ این دستور فقط داخل گروه است."
        )

        return


    groups = load_groups()


    chat_id = str(
        chat.id
    )


    if chat_id in groups:

        del groups[
            chat_id
        ]

        save_groups(
            groups
        )


    await update.message.reply_text(
        "🛑 قیمت خودکار خاموش شد."
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
            "PRICE UPDATE FAILED"
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

            if not info.get(
                "enabled",
                True
            ):

                continue


            message_id = info.get(
                "message_id"
            )


            if not message_id:

                sent = (
                    await context
                    .bot
                    .send_message(

                        chat_id=int(
                            chat_id
                        ),

                        text=text,

                        parse_mode="HTML"
                    )
                )


                groups[
                    chat_id
                ][
                    "message_id"
                ] = sent.message_id


                changed = True


            else:

                await context.bot.edit_message_text(

                    chat_id=int(
                        chat_id
                    ),

                    message_id=message_id,

                    text=text,

                    parse_mode="HTML"
                )


        except Exception as error:

            print(
                "GROUP ERROR:",
                chat_id,
                error
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

        "🤖 <b>NerKhinoo Status</b>\n\n"

        "🟢 ربات فعال است\n"

        "🇮🇷 PersianToolbox: "
        "<b>PRIMARY</b>\n"

        "🥇 GoldPrice.dev: "
        "<b>GOLD BACKUP</b>\n"

        "🌍 Frankfurter: "
        "<b>FX BACKUP</b>\n\n"

        "🔄 بروزرسانی گروه‌ها: "
        "<b>۶۰ ثانیه</b>\n"

        f"👥 گروه‌های فعال: "
        f"<b>{fa_number(len(groups))}</b>",

        parse_mode="HTML"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است."
        )


    application = (

        Application
        .builder()
        .token(
            BOT_TOKEN
        )
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
        CommandHandler(
            "status",
            status
        )
    )


    if application.job_queue is None:

        raise RuntimeError(

            "JobQueue نصب نیست.\n\n"

            "اجرا کن:\n"

            "pip install "
            "\"python-telegram-bot[job-queue]\""
        )


    application.job_queue.run_repeating(

        update_groups,

        interval=UPDATE_SECONDS,

        first=10
    )


    threading.Thread(

        target=run_web,

        daemon=True

    ).start()


    print(
        "================================"
    )

    print(
        "🤖 NerKhinoo STARTED"
    )

    print(
        "🇮🇷 PersianToolbox = PRIMARY"
    )

    print(
        "🥇 GoldPrice.dev = GOLD BACKUP"
    )

    print(
        "🌍 Frankfurter = FX BACKUP"
    )

    print(
        "🔄 UPDATE = 60 SECONDS"
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
