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

def get_single_oil_report(symbol, title):
    """Lấy dữ liệu và tính toán chi tiết cho từng loại dầu với bố cục rõ ràng"""
    try:
        df = yf.download(symbol, period="5d", interval="30m", progress=False)
        if df.empty or len(df) < 10:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert(VN_TZ)
        else:
            df.index = df.index.tz_localize('UTC').tz_convert(VN_TZ)

        closes = df['Close']
        current_price = float(closes.iloc[-1])
        latest_time = df.index[-1]

        def get_change_and_time(hours):
            target_time = latest_time - timedelta(hours=hours)
            idx = df.index.get_indexer([target_time], method='nearest')[0]
            past_price = float(closes.iloc[idx])
            past_time_str = df.index[idx].strftime('%H:%M %d/%m')
            pct = ((current_price - past_price) / past_price) * 100
            return round(pct, 2), past_time_str

        pct_1h, time_1h = get_change_and_time(1)
        pct_2h, time_2h = get_change_and_time(2)
        pct_3h, time_3h = get_change_and_time(3)
        pct_4h, time_4h = get_change_and_time(4)

        today_date = get_vn_time().date()
        df_today = df[df.index.date == today_date]
        
        if not df_today.empty:
            open_price_today = float(df_today['Open'].iloc[0])
            open_time_str = df_today.index[0].strftime('%H:%M %d/%m')
            change_day = round(((current_price - open_price_today) / open_price_today) * 100, 2)
            day_label = f"Mở cửa lúc {open_time_str}"
        else:
            df_prev = df[df.index.date < today_date]
            prev_day_close = float(df_prev['Close'].iloc[-1]) if not df_prev.empty else current_price
            change_day = round(((current_price - prev_day_close) / prev_day_close) * 100, 2)
            day_label = "So với hôm trước"

        def format_line(val, hours_label, t_str):
            icon = "🟢" if val >= 0 else "🔴"
            sign = "+" if val >= 0 else ""
            return f"{icon} `{sign}{val}%` | {hours_label} ({t_str})\n"

        msg = f"🛢️ *{title}*\n"
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
        return f"🛢️ *{title}*: ⚠️ Không thể lấy dữ liệu lúc này.\n"

def get_full_report():
    wti_msg = get_single_oil_report("CL=F", "DẦU THÔ WTI (CAUTURONG)")
    brent_msg = get_single_oil_report("BZ=F", "DẦU THÔ BRENT (CAUTURONG)")
    
    if not wti_msg and not brent_msg:
        return None
        
    time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
    
    full_msg = f"{wti_msg}\n═══════════════════\n{brent_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"
    return full_msg

# --- HÀM LẮNG NGHE LỆNH CHAT TỪ TELEGRAM (Gõ 'xem' để lấy dữ liệu thực tế) ---
def check_telegram_commands():
    last_update_id = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "").strip().lower()
                    
                    # Nếu bạn gõ chữ 'xem' trong chat, bot sẽ lập tức lấy dữ liệu thực tế gửi ngay
                    if text == "xem":
                        print("Nhận được từ khóa 'xem' từ Telegram. Đang cập nhật dữ liệu thực tế...")
                        report_msg = get_full_report()
                        if report_msg:
                            send_telegram_message("⚡ *BẢN TIN CẬP NHẬT THỰC TẾ*\n\n" + report_msg)
        except Exception as e:
            print(f"Lỗi đọc lệnh Telegram: {e}")
            time.sleep(5)

# --- VÒNG LẬP CHẠY BOT (5:00 - 21:00, Tần suất 1 tiếng/lần) ---
def run_bot():
    print("🚀 Oil Price Bot (CAUTURONG) đang chạy...")
    init_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
    send_telegram_message(f"🚀 *Bot Báo Giá Dầu Thô (CAUTURONG)* đã khởi động thành công lúc `{init_time}`!")

    # Khởi chạy luồng phụ lắng nghe từ khóa 'xem'
    cmd_thread = Thread(target=check_telegram_commands)
    cmd_thread.daemon = True
    cmd_thread.start()

    last_sent_slot = ""

    while True:
        try:
            now_vn = get_vn_time()
            current_hour = now_vn.hour
            current_minute = now_vn.minute
            current_date = now_vn.date()
            
            is_after_start = (current_hour > 5) or (current_hour == 5 and current_minute >= 0)
            is_before_end = (current_hour < 21) or (current_hour == 21 and current_minute <= 0)
            is_allowed_time = is_after_start and is_before_end
            
            if is_allowed_time:
                if 0 <= current_minute <= 5:
                    slot_name = f"{current_date}-{current_hour}"
                else:
                    slot_name = None

                if slot_name and last_sent_slot != slot_name:
                    print(f"Đang gửi báo cáo định kỳ lúc {current_hour}:{current_minute:02d}...")
                    report_msg = get_full_report()
                    if report_msg:
                        send_telegram_message(report_msg)
                    last_sent_slot = slot_name
            else:
                print(f"Ngoài giờ thông báo ({current_hour}:{current_minute:02d}). Bot đang nghỉ.")

            time.sleep(30)
            
        except Exception as e:
            print(f"Lỗi vòng lặp báo cáo giá dầu: {e}")
            time.sleep(60)

if __name__ == '__main__':
    t = Thread(target=run_bot)
    t.daemon = True
    t.start()
    
    run_web()
