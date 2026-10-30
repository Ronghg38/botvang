import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from flask import Flask
import threading

# --- CẤU HÌNH WEB SERVER CHO RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Oil & Gold Bot (CAUTURONG) is running 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=10000, debug=False, use_reloader=False)

# --- CẤU HÌNH THÔNG TIN BOT ---
TELEGRAM_TOKEN = "8234059775:AAHk8kv9ruTGV_qsGbFXC7SgTxfRwWOO1BI"
TELEGRAM_CHAT_ID = "5931570040"

# 🛠️ ĐỘ LỆCH GIÁ VÀNG SO VỚI TRADINGVIEW
GOLD_OFFSET = -10.36 

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_time():
    """Lấy thời gian chuẩn theo giờ Việt Nam"""
    return datetime.now(VN_TZ)

def send_telegram_message(message):
    """Gửi thông báo văn bản tới Telegram an toàn"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Lỗi gửi tin nhắn Telegram: {e}")

def get_single_asset_report(symbol, title):
    """Lấy dữ liệu và chuẩn hóa mốc thời gian an toàn tuyệt đối"""
    try:
        df = yf.download(symbol, period="2d", interval="30m", progress=False)
        if df is None or df.empty or len(df) < 2:
            return f"📌 *{title}*: ⚠️ Dữ liệu trống."
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert(VN_TZ)
        else:
            df.index = df.index.tz_localize('UTC').tz_convert(VN_TZ)

        closes = df['Close']
        current_price = float(closes.iloc[-1])
        
        if symbol == "GC=F":
            current_price += GOLD_OFFSET

        now_vn = get_vn_time()
        today_date = now_vn.date()
        
        # Mốc mở cửa chính thức trong ngày: 05:00 sáng VN
        morning_5am_today = datetime(today_date.year, today_date.month, today_date.day, 5, 0, 0, tzinfo=VN_TZ)
        if now_vn < morning_5am_today:
            morning_5am_today = morning_5am_today - timedelta(days=1)

        df_today_session = df[df.index >= morning_5am_today]

        if not df_today_session.empty:
            open_price_today = float(df_today_session['Open'].iloc[0])
            open_time_str = df_today_session.index[0].strftime('%H:%M %d/%m')
            if symbol == "GC=F":
                open_price_today += GOLD_OFFSET
            change_day = round(((current_price - open_price_today) / open_price_today) * 100, 2)
            day_label = f"Mở cửa lúc {open_time_str}"
        else:
            df_prev = df[df.index.date < today_date]
            prev_day_close = float(df_prev['Close'].iloc[-1]) if not df_prev.empty else current_price
            if symbol == "GC=F":
                prev_day_close += GOLD_OFFSET
            change_day = round(((current_price - prev_day_close) / prev_day_close) * 100, 2)
            day_label = "So với hôm trước"

        def get_clean_hourly_change(hours_back):
            target_time = now_vn - timedelta(hours=hours_back)
            if target_time < morning_5am_today:
                target_time = morning_5am_today
                
            idx = df.index.get_indexer([target_time], method='nearest')[0]
            past_price = float(closes.iloc[idx])
            if symbol == "GC=F":
                past_price += GOLD_OFFSET
            past_time_str = df.index[idx].strftime('%H:%M %d/%m')
            pct = ((current_price - past_price) / past_price) * 100
            return round(pct, 2), past_time_str

        pct_1h, time_1h = get_clean_hourly_change(1)
        pct_2h, time_2h = get_clean_hourly_change(2)
        pct_3h, time_3h = get_clean_hourly_change(3)
        pct_4h, time_4h = get_clean_hourly_change(4)

        def format_line(val, hours_label, t_str):
            icon = "🟢" if val >= 0 else "🔴"
            sign = "+" if val >= 0 else ""
            return f"{icon} `{sign}{val}%` | {hours_label} ({t_str})\n"

        icon_title = "🟡" if "VÀNG" in title else "🛢️"
        
        msg = f"{icon_title} *{title}*\n"
        msg += f"💵 Giá hiện tại: **{current_price:.2f}$**\n"
        msg += f"───────────────────\n"
        msg += f"• Biến động theo giờ:\n"
        msg += format_line(pct_1h, "1 giờ", time_1h)
        msg += format_line(pct_2h, "2 giờ", time_2h)
        msg += format_line(pct_3h, "3 giờ", time_3h)
        msg += format_line(pct_4h, "4 giờ", time_4h)
        msg += f"───────────────────\n"
        
        day_icon = "🟢" if change_day >= 0 else "🔴"
        day_sign = "+" if change_day >= 0 else ""
        msg += f"📊 Biến động trong ngày:\n"
        msg += f"{day_icon} `{day_sign}{change_day}%` ({day_label})\n"
        
        return msg

    except Exception as e:
        print(f"Lỗi lấy dữ liệu {title}: {e}")
        return f"📌 *{title}*: ⚠️ Không thể lấy dữ liệu lúc này."

def get_oil_report():
    try:
        wti_msg = get_single_asset_report("CL=F", "DẦU THÔ WTI (CAUTURONG)")
        brent_msg = get_single_asset_report("BZ=F", "DẦU THÔ BRENT (CAUTURONG)")
        time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
        return f"{wti_msg}\n═══════════════════\n{brent_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"
    except Exception as e:
        print(f"Lỗi tạo báo cáo dầu: {e}")
        return None

def get_gold_report():
    try:
        gold_msg = get_single_asset_report("GC=F", "VÀNG THẾ GIỚI (CAUTURONG)")
        time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
        return f"{gold_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"
    except Exception as e:
        print(f"Lỗi tạo báo cáo vàng: {e}")
        return None

# --- VÒNG LẶP NỀN XỬ LÝ LỆNH VÀ ĐỊNH KỲ ---
def background_loop():
    last_update_id = 0
    last_sent_slot = ""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    print("🎯 Bot nền đã khởi động và sẵn sàng nhận lệnh...")

    while True:
        try:
            # 1. Kiểm tra tin nhắn Telegram
            params = {"offset": last_update_id, "timeout": 2}
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip().lower()
                    
                    if text == "xem":
                        print("👉 Đang xử lý lệnh 'xem' (Dầu)...")
                        report = get_oil_report()
                        if report:
                            send_telegram_message("⚡ *BẢN TIN DẦU THÔ THỰC TẾ*\n\n" + report)
                            
                    elif text in ["vang", "gold", "vàng"]:
                        print("👉 Đang xử lý lệnh 'vang' (Vàng)...")
                        report = get_gold_report()
                        if report:
                            send_telegram_message("⚡ *BẢN TIN VÀNG THẾ GIỚI THỰC TẾ*\n\n" + report)

            # 2. Kiểm tra giờ gửi báo cáo dầu tự động (05:00 - 21:00)
            now_vn = get_vn_time()
            h, m, d = now_vn.hour, now_vn.minute, now_vn.date()
            
            if (h > 5 or (h == 5 and m >= 0)) and (h < 21 or (h == 21 and m <= 0)):
                slot_name = f"{d}-{h}" if (0 <= m <= 5) else None
                if slot_name and last_sent_slot != slot_name:
                    print(f"Đang gửi báo cáo định kỳ lúc {h}:{m:02d}...")
                    report = get_oil_report()
                    if report:
                        send_telegram_message(report)
                    last_sent_slot = slot_name

        except Exception as e:
            print(f"⚠️ Lỗi ở vòng lặp nền: {e}")
            
        time.sleep(2)

if __name__ == '__main__':
    # Khởi động luồng nền
    t = threading.Thread(target=background_loop)
    t.daemon = True
    t.start()
    
    # Chạy Flask web server
    run_web()
