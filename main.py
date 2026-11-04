
import os
import time
import logging
from io import BytesIO
from datetime import datetime, timedelta, timezone
from threading import Thread, Lock

import requests
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import Flask, jsonify

# =====================================
# CAUTURONG - BOT BAO GIA DAU VA VANG
# =====================================

app = Flask(__name__)

VN_TZ = timezone(timedelta(hours=7))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
PORT = int(os.getenv("PORT", "10000"))

GOLD_OFFSET = float(os.getenv("GOLD_OFFSET", "0"))
SCHEDULE_GOLD = os.getenv("SCHEDULE_GOLD", "false").lower() == "true"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("CAUTURONG")

http = requests.Session()
send_lock = Lock()

ASSETS = {
    "wti": ("CL=F", "DAU THO WTI"),
    "brent": ("BZ=F", "DAU THO BRENT"),
    "gold": ("GC=F", "VANG THE GIOI")
}


def vn_now():
    return datetime.now(VN_TZ)


@app.route("/")
def home():
    return jsonify({
        "bot": "CAUTURONG",
        "status": "running",
        "time": vn_now().isoformat()
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def telegram_api(method, payload):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"

    response = http.post(
        url,
        json=payload,
        timeout=20
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(str(result))

    return result


def send_message(message):
    if not TOKEN or not CHAT_ID:
        log.error("Chua cau hinh Telegram")
        return

    try:
        with send_lock:
            telegram_api("sendMessage", {
                "chat_id": CHAT_ID,
                "text": message
            })

    except Exception:
        log.exception("Loi gui Telegram")


def send_photo(photo, caption):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"

        with send_lock:
            response = http.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption
                },
                files={
                    "photo": (
                        "chart.png",
                        photo,
                        "image/png"
                    )
                },
                timeout=30
            )

        response.raise_for_status()

    except Exception:
        log.exception("Loi gui bieu do")


def get_data(symbol):

    df = yf.download(
        symbol,
        period="5d",
        interval="30m",
        progress=False,
        auto_adjust=False,
        threads=False
    )

    if df.empty:
        raise ValueError("Khong co du lieu")

    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            df.columns = df.columns.get_level_values(0)
        else:
            df.columns = df.columns.get_level_values(-1)

    df = df.copy()

    idx = pd.to_datetime(df.index)

    if idx.tz is None:
        idx = idx.tz_localize("UTC")

    df.index = idx.tz_convert(VN_TZ)

    return df.sort_index()


def asset_report(key):

    symbol, title = ASSETS[key]

    try:
        df = get_data(symbol)

        close = pd.to_numeric(
            df["Close"], errors="coerce"
        ).dropna()

        if close.empty:
            raise ValueError("Gia khong hop le")

        offset = GOLD_OFFSET if key == "gold" else 0

        current = float(close.iloc[-1]) + offset

        now = vn_now()

        last_time = close.index[-1]

        age = int(
            (now - last_time).total_seconds() / 60
        )

        start = now.replace(
            hour=5,
            minute=0,
            second=0,
            microsecond=0
        )

        if now < start:
            start -= timedelta(days=1)

        session = df[df.index >= start]

        if not session.empty:
            base = float(session["Open"].iloc[0]) + offset
        else:
            previous = close[close.index < start]

            if previous.empty:
                base = current
            else:
                base = float(previous.iloc[-1]) + offset

        day_change = (
            (current - base) / base * 100
            if base else 0
        )

        lines = [
            f"📊 {title}",
            f"💰 Gia hien tai: {current:.2f} USD",
            f"🕒 Nen du lieu: {last_time:%H:%M %d/%m}",
            "",
            "BIEN DONG THEO GIO:"
        ]

        for hours in [1, 2, 3, 4]:

            target = now - timedelta(hours=hours)

            if target < start:
                target = start

            past = close[close.index <= target]

            if past.empty:
                lines.append(
                    f"{hours} gio: Chua du du lieu"
                )
                continue

            old = float(past.iloc[-1]) + offset

            change = (
                (current - old) / old * 100
                if old else 0
            )

            icon = "🟢" if change >= 0 else "🔴"

            lines.append(
                f"{icon} {hours} gio: {change:+.2f}%"
            )

        icon = "🟢" if day_change >= 0 else "🔴"

        lines += [
            "",
            "BIEN DONG TRONG NGAY:",
            f"{icon} {day_change:+.2f}%",
            "",
            f"Du lieu cach hien tai: {age} phut",
            "",
            "Nguon: Yahoo Finance Futures.",
            "Gia tham khao, khong phai gia Platts/Singapore."
        ]

        if age > 90:
            lines.append(
                "⚠️ Canh bao: Du lieu co the da cu."
            )

        return "\n".join(lines)

    except Exception as e:

        log.exception("Loi lay gia")

        return f"⚠️ {title}: Khong lay duoc du lieu."


def oil_report():

    return (
        "🛢️ BAO CAO GIA DAU CAUTURONG\n\n"
        + asset_report("wti")
        + "\n\n--------------------\n\n"
        + asset_report("brent")
        + "\n\nCap nhat: "
        + vn_now().strftime("%H:%M %d/%m/%Y")
    )


def gold_report():

    return (
        "🟡 BAO CAO GIA VANG CAUTURONG\n\n"
        + asset_report("gold")
        + "\n\nCap nhat: "
        + vn_now().strftime("%H:%M %d/%m/%Y")
    )


def make_chart(key):

    symbol, title = ASSETS[key]

    df = get_data(symbol).tail(48)

    offset = GOLD_OFFSET if key == "gold" else 0

    prices = df["Close"].dropna() + offset

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(prices.index, prices.values)

    ax.set_title(title)

    ax.set_xlabel("Gio Viet Nam")

    ax.set_ylabel("USD")

    ax.grid(True)

    fig.autofmt_xdate()

    output = BytesIO()

    fig.savefig(
        output,
        format="png",
        dpi=150
    )

    plt.close(fig)

    output.seek(0)

    return output


def send_chart(key):

    try:
        photo = make_chart(key)

        send_photo(
            photo,
            f"Bieu do {ASSETS[key][1]}"
        )

    except Exception:
        log.exception("Loi tao bieu do")


def help_text():

    return """
🤖 BOT CAUTURONG

xem - Bao cao gia dau
vang - Bao cao gia vang
tatca - Bao cao tat ca
bieudo - Bieu do dau
bieudovang - Bieu do vang
help - Huong dan

Du lieu mang tinh tham khao.
"""


def process_command(command):

    command = command.strip().lower().replace("/", "")

    if command in ["start", "help"]:

        send_message(help_text())

    elif command == "xem":

        send_message(oil_report())

    elif command == "vang":

        send_message(gold_report())

    elif command == "tatca":

        send_message(
            oil_report()
            + "\n\n"
            + gold_report()
        )

    elif command == "bieudo":

        send_message("Dang tao bieu do dau...")

        send_chart("wti")
        send_chart("brent")

    elif command == "bieudovang":

        send_message("Dang tao bieu do vang...")

        send_chart("gold")


def telegram_listener():

    offset = None

    while True:

        try:

            params = {"timeout": 25}

            if offset is not None:
                params["offset"] = offset

            response = http.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params=params,
                timeout=35
            )

            response.raise_for_status()

            data = response.json()

            for update in data.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message", {})

                chat = str(
                    message.get("chat", {}).get("id", "")
                )

                command = message.get("text", "")

                if chat != str(CHAT_ID):
                    continue

                if command:
                    process_command(command)

        except Exception:

            log.exception("Loi Telegram")

            time.sleep(5)


def scheduler():

    last_slot = None

    while True:

        try:

            now = vn_now()

            if (
                5 <= now.hour <= 21
                and now.minute == 0
            ):

                slot = now.strftime("%Y%m%d%H")

                if slot != last_slot:

                    message = oil_report()

                    if SCHEDULE_GOLD:
                        message += "\n\n" + gold_report()

                    send_message(message)

                    last_slot = slot

            time.sleep(15)

        except Exception:

            log.exception("Loi lich gui")

            time.sleep(30)


def main():

    if not TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Thieu TELEGRAM_BOT_TOKEN hoac TELEGRAM_CHAT_ID"
        )

    send_message(
        "🚀 BOT CAUTURONG DA KHOI DONG!"
    )

    Thread(
        target=telegram_listener,
        daemon=True
    ).start()

    Thread(
        target=scheduler,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":
    main()
