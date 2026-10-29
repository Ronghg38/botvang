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
    """Lấy dữ liệu và tính toán % thay đổi chuẩn theo múi giờ VN"""
    try:
        df = yf.download(SYMBOL, period="5d", interval="30m", progress=False)
        if df.empty or len(df) < 10:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        # Quy đổi index của dữ liệu về múi giờ Việt Nam để so sánh ngày chính xác
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert(VN_TZ)
        else:
            df.index = df.index.tz_localize('UTC').tz_convert(VN_TZ)

        closes = df['Close']
        current_price = float(closes.iloc[-1])
        
        def calc_change(n):
            if len(closes) > n:
                past_price = float(closes.iloc[-1 - n])
                pct = ((current_price - past_price) / past_price) * 100
                return round(pct, 2)
            return None

        change_1h = calc_change(2)
        change_2h = calc_change(4)
        change_3h = calc_change(6)
        change_4h = calc_change(8)

        # Tính % thay đổi trong ngày so với giá ĐÓNG CỬA ngày hôm trước (theo múi giờ VN)
        today_date = get_vn_time().date()
        df_prev = df[df.index.date < today_date]
        if not df_prev.empty:
            prev_day_close = float(df_prev['Close'].iloc[-1])
            change_day = round(((current_price - prev_day_close) / prev_day_close) * 100, 2)
        else:
            change_day = 0.0

        time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')

        # Thiết kế giao diện báo cáo
        msg = f"🛢️ **CHỢ GIÁ - DẦU THÔ (WTI) [CAUTURONG]**\n"
        msg += f"💵 Giá hiện tại: **{current_price:.2f}$**\n"
        msg += f"───────────────────\n"
        
        def format_text(val, label):
            if val is None:
                return ""
            if val >= 0:
                return f"🟢 Tăng `+{val}%` ({label})\n"
            else:
                return f"🔴 Giảm `{val}%` ({label})\n"

        if change_1h is not None:
            msg += format_text(change_1h, "trong 1 giờ")
        if change_2h is not None:
            msg += format_text(change_2h, "trong 2 giờ")
        if change_3h is not None:
            msg += format_text(change_3h, "trong 3 giờ")
        if change_4h is not None:
            msg += format_text(change_4h, "trong 4 giờ")
            
        msg += f"───────────────────\n"
        msg += format_text(change_day, "trong ngày")
        msg += f"───────────────────\n"
        msg += f"⏰ Cập nhật: `{time_str}`"
        return msg

    except Exception as e:
        print(f"Lỗi tính toán dữ liệu dầu: {e}")
        return None

# --- VÒNG LẬP CHẠY BOT (5:00 - 21:00, Tần suất 1 tiếng/lần) ---
def run_bot():
    print("🚀 Oil Price Bot (CAUTURONG) đang chạy...")
    init_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
    send_telegram_message(f"🚀 *Bot Báo Giá Dầu Thô (CAUTURONG)* đã khởi động thành công lúc `{init_time}`!")

    last_sent_slot = ""

    while True:
        try:
            now_vn = get_vn_time()
            current_hour = now_vn.hour
            current_minute = now_vn.minute
            current_date = now_vn.date()
            
            # Khung giờ hoạt động: Từ 5:00 sáng đến 21:00 tối
            is_after_start = (current_hour > 5) or (current_hour == 5 and current_minute >= 0)
            is_before_end = (current_hour < 21) or (current_hour == 21 and current_minute <= 0)
            is_allowed_time = is_after_start and is_before_end
            
            if is_allowed_time:
                # Bắt mốc phút từ 0 đến 5 của mỗi giờ (Tần suất 1 tiếng/lần)
                if 0 <= current_minute <= 5:
                    slot_name = f"{current_date}-{current_hour}"
                else:
                    slot_name = None

                # Gửi tin nếu đúng khung giờ và chưa gửi trong slot giờ đó
                if slot_name and last_sent_slot != slot_name:
                    print(f"Đang gửi báo cáo định kỳ lúc {current_hour}:{current_minute:02d}...")
                    report_msg = get_oil_report()
                    if report_msg:
                        send_telegram_message(report_msg)
                    last_sent_slot = slot_name
            else:
                print(f"Ngoài giờ thông báo ({current_hour}:{current_minute:02d}). Bot đang nghỉ.")

            # Kiểm tra lại mỗi 30 giây
            time.sleep(30)
            
        except Exception as e:
            print(f"Lỗi vòng lặp báo cáo giá dầu: {e}")
            time.sleep(60)

# Khởi chạy Web server và Bot song song
if __name__ == '__main__':
    t = Thread(target=run_bot)
    t.daemon = True
    t.start()
    
    run_web()
