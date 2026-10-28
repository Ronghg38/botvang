import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from threading import Thread
from flask import Flask

# --- CẤU HÌNH WEB SERVER CHO RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Oil Price Bot (CAUTURONG) is running 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

# --- CẤU HÌNH THÔNG TIN BOT ---
TELEGRAM_TOKEN = "8234059775:AAHk8kv9ruTGV_qsGbFXC7SgTxfRwWOO1BI"
TELEGRAM_CHAT_ID = "5931570040"
SYMBOL = "CL=F"  # Mã dầu thô WTI trên Yahoo Finance

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_time():
    """Lấy thời gian chuẩn theo giờ Việt Nam"""
    return datetime.now(VN_TZ)

def send_telegram_message(message):
    """Gửi thông báo văn bản tới Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Lỗi gửi tin nhắn Telegram: {e}")

def get_oil_report():
    """Lấy dữ liệu và tính toán % thay đổi với màu sắc sinh động (Xanh/Đỏ)"""
    try:
        df = yf.download(SYMBOL, period="2d", interval="30m", progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        closes = df['Close']
        current_price = float(closes.iloc[-1])
        
        def calc_change(n):
            if len(closes) > n:
                past_price = float(closes.iloc[-1 - n])
                pct = ((current_price - past_price) / past_price) * 100
                return round(pct, 2)
            return None

        change_30m = calc_change(1)
        change_1h = calc_change(2)
        change_2h = calc_change(4)
        change_3h = calc_change(6)
        change_4h = calc_change(8)

        time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')

        # Thiết kế giao diện sinh động hơn
        msg = f"🛢️ **CHỢ GIÁ - DẦU THÔ (WTI)**\n"
        msg += f"💵 Giá hiện tại: **{current_price:.2f}$**\n"
        msg += f"───────────────────\n"
        
        def format_text(val, label):
            if val is None:
                return ""
            if val >= 0:
                return f"🟢 Tăng `+{val}%` (trong {label})\n"
            else:
                return f"🔴 Giảm `{val}%` (trong {label})\n"

        if change_30m is not None:
            msg += format_text(change_30m, "30 phút")
        if change_1h is not None:
            msg += format_text(change_1h, "1 giờ")
        if change_2h is not None:
            msg += format_text(change_2h, "2 giờ")
        if change_3h is not None:
            msg += format_text(change_3h, "3 giờ")
        if change_4h is not None:
            msg += format_text(change_4h, "4 giờ")
            
        msg += f"───────────────────\n"
        msg += f"⏰ Cập nhật: `{time_str}`"
        return msg

    except Exception as e:
        print(f"Lỗi tính toán dữ liệu dầu: {e}")
        return None

# --- VÒNG LẬP CHẠY BOT ---
def run_bot():
    print("🚀 Oil Price Bot (CAUTURONG) đang chạy...")
    init_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
    send_telegram_message(f"🚀 *Bot Báo Giá Dầu Thô (CAUTURONG)* đã khởi động thành công lúc `{init_time}`!")

    while True:
        try:
            report_msg = get_oil_report()
            if report_msg:
                send_telegram_message(report_msg)
            
            # Báo cáo định kỳ mỗi 30 phút (1800 giây)
            time.sleep(1800)
            
        except Exception as e:
            print(f"Lỗi vòng lặp báo cáo giá dầu: {e}")
            time.sleep(60)

# Khởi chạy Web server và Bot song song
if __name__ == '__main__':
    t = Thread(target=run_bot)
    t.daemon = True
    t.start()
    
    run_web()
