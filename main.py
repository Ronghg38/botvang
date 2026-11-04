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
    return "Oil & Gold Price Bot (CAUTURONG) is running 24/7!"

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
    """Gửi thông báo văn bản tới Telegram"""
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
    """Lấy dữ liệu và tính toán tỷ lệ phần trăm khớp chuẩn TradingView CFD"""
    try:
        df_daily = yf.download(symbol, period="5d", interval="1d", progress=False)
        if df_daily.empty or len(df_daily) < 2:
            return f"📌 *{title}*: ⚠️ Dữ liệu trống."
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.droplevel(1)
            
        df_daily.index = pd.to_datetime(df_daily.index)
        if df_daily.index.tz is not None:
            df_daily.index = df_daily.index.tz_convert(VN_TZ)
        else:
            df_daily.index = df_daily.index.tz_localize('UTC').tz_convert(VN_TZ)

        current_price = float(df_daily['Close'].iloc[-1])
        prev_close_price = float(df_daily['Close'].iloc[-2])
        
        if symbol == "GC=F":
            current_price += GOLD_OFFSET
            prev_close_price += GOLD_OFFSET

        change_day = round(((current_price - prev_close_price) / prev_close_price) * 100, 2)
        day_label = "So với hôm trước"

        df = yf.download(symbol, period="5d", interval="30m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert(VN_TZ)
        else:
            df.index = df.index.tz_localize('UTC').tz_convert(VN_TZ)

        closes = df['Close']
        now_vn = get_vn_time()
        today_date = now_vn.date()
        
        morning_5am_today = datetime(today_date.year, today_date.month, today_date.day, 5, 0, 0, tzinfo=VN_TZ)
        if now_vn < morning_5am_today:
            morning_5am_today = morning_5am_today - timedelta(days=1)

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
        return f"📌 *{title}*: ⚠️ Không thể lấy dữ liệu lúc này.\n"

def get_oil_report():
    wti_msg = get_single_asset_report("CL=F", "DẦU THÔ WTI (USOIL)")
    brent_msg = get_single_asset_report("BZ=F", "DẦU THÔ BRENT (UKOIL)")
    if not wti_msg and not brent_msg:
        return None
    time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
    return f"{wti_msg}\n═══════════════════\n{brent_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"

def get_gold_report():
    gold_msg = get_single_asset_report("GC=F", "VÀNG THẾ GIỚI (GOLD)")
    if not gold_msg:
        return None
    time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
    return f"{gold_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"

# --- VÒNG LẶP NỀN XỬ LÝ LỆNH SIÊU NHẠY ---
def background_loop():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    print("🎯 Bot nền đã khởi động và sẵn sàng nhận lệnh...")
    
    last_update_id = 0
    try:
        res = requests.get(url, params={"timeout": 1}, timeout=3)
        data = res.json()
        if data.get("ok") and data.get("result"):
            last_update_id = data["result"][-1]["update_id"] + 1
    except Exception as e:
        print(f"Khởi tạo offset lỗi: {e}")

    while True:
        try:
            params = {"offset": last_update_id, "timeout": 2}
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"] + 1
                    message = update.get("message", {})
                    
                    # Chỉ nhận tin nhắn trực tiếp từ chat (bỏ qua tin nhắn chuyển tiếp hoặc từ bot khác)
                    if not message or "text" not in message:
                        continue
                        
                    text = message.get("text", "").strip().lower()
                    print(f"📥 Nhận được lệnh: '{text}'")
                    
                    if text in ["xem", "dau", "dầu"]:
                        print("👉 Đang xử lý lệnh Dầu...")
                        report = get_oil_report()
                        if report:
                            send_telegram_message("⚡ *BẢN TIN DẦU THÔ THỰC TẾ*\n\n" + report)
                            
                    elif text in ["vang", "gold", "vàng", "vàn"]:
                        print("👉 Đang xử lý lệnh Vàng...")
                        report = get_gold_report()
                        if report:
                            send_telegram_message("⚡ *BẢN TIN VÀNG THẾ GIỚI THỰC TẾ*\n\n" + report)

        except Exception as e:
            print(f"⚠️ Lỗi ở vòng lặp nền: {e}")
            
        time.sleep(1)

if __name__ == '__main__':
    t = Thread(target=background_loop)
    t.daemon = True
    t.start()
    
    run_web()
