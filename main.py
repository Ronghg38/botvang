import time
from datetime import datetime, timezone, timedelta
import yfinance as yf
import requests
from flask import Flask

# --- CẤU HÌNH BOT TELEGRAM VÀ RENDER ---
TOKEN = "TOKEN_TELEGRAM_CUA_BAN"  # Thay token bot của bạn vào đây
CHAT_ID = "CHAT_ID_CUA_BAN"        # Thay chat_id của bạn vào đây

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Báo Giá Dầu CAUTURONG đang chạy 24/7!"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Lỗi gửi tin nhắn Telegram: {e}")
        return None

def get_oil_price_report():
    try:
        ticker = yf.Ticker("CL=F")
        df = ticker.history(period="2d", interval="30m")
        
        if df.empty or len(df) < 9:
            return "⚠️ Không thể lấy đủ dữ liệu giá dầu lúc này."
            
        current_price = df['Close'].iloc[-1]
        
        def format_change(val):
            icon = "🟢" if val >= 0 else "🔴"
            text = "Tăng" if val >= 0 else "Giảm"
            return f"{icon} {text} {val:+.2f}%"

        change_30m = ((current_price - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
        change_1h = ((current_price - df['Close'].iloc[-3]) / df['Close'].iloc[-3]) * 100
        change_2h = ((current_price - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
        change_3h = ((current_price - df['Close'].iloc[-8]) / df['Close'].iloc[-8]) * 100
        change_4h = ((current_price - df['Close'].iloc[-10]) / df['Close'].iloc[-10]) * 100

        today_date = datetime.now(timezone(timedelta(hours=7))).date()
        df_today = df[df.index.date == today_date]
        
        if not df_today.empty:
            open_price_today = df_today['Open'].iloc[0]
            change_day = ((current_price - open_price_today) / open_price_today) * 100
        else:
            change_day = 0.0

        message = (
            f"🛢️ <b>CHỢ GIÁ - DẦU THÔ (WTI) [CAUTURONG]</b>\n"
            f"💰 Giá hiện tại: <b>{current_price:.2f}$</b>\n"
            f"----------------------------------\n"
            f"{format_change(change_30m)} (trong 30 phút)\n"
            f"{format_change(change_1h)} (trong 1 giờ)\n"
            f"{format_change(change_2h)} (trong 2 giờ)\n"
            f"{format_change(change_3h)} (trong 3 giờ)\n"
            f"{format_change(change_4h)} (trong 4 giờ)\n"
            f"----------------------------------\n"
            f"📊 <b>{format_change(change_day)} (trong ngày)</b>\n"
            f"----------------------------------\n"
            f"⏰ Cập nhật: {datetime.now(timezone(timedelta(hours=7))).strftime('%H:%M - %d/%m/%Y')}"
        )
        return message
    except Exception as e:
        return f"⚠️ Lỗi lấy giá dầu: {e}"

def run_bot_schedule():
    VN_TIMEZONE = timezone(timedelta(hours=7))
    print("🤖 Bot Báo Giá Dầu (CAUTURONG) đã khởi động thành công!")
    
    # Gửi ngay tin nhắn thông báo khởi động thành công lên Telegram
    init_time = datetime.now(VN_TIMEZONE).strftime('%H:%M - %d/%m/%Y')
    send_telegram_message(f"🚀 <b>Bot CAUTURONG đã khởi động lại thành công lúc {init_time}!</b>")

    last_sent_slot = ""

    while True:
        try:
            now_vn = datetime.now(VN_TIMEZONE)
            current_hour = now_vn.hour
            current_minute = now_vn.minute
            current_date = now_vn.date()
            
            # Khung giờ hoạt động: Từ 5:00 đến 20:30
            is_after_start = (current_hour > 5) or (current_hour == 5 and current_minute >= 0)
            is_before_end = (current_hour < 20) or (current_hour == 20 and current_minute <= 30)
            is_allowed_time = is_after_start and is_before_end
            
            if is_allowed_time:
                # Gom nhóm mốc thời gian thành 2 khoảng: nửa đầu giờ (phút 0-5) hoặc nửa sau giờ (phút 30-35)
                if 0 <= current_minute <= 5:
                    slot_name = f"{current_date}-{current_hour}-00"
                elif 30 <= current_minute <= 35:
                    slot_name = f"{current_date}-{current_hour}-30"
                else:
                    slot_name = None

                # Nếu đang nằm trong khung phút hợp lệ và chưa gửi trong slot này
                if slot_name and last_sent_slot != slot_name:
                    print(f"Đang gửi báo cáo định kỳ lúc {current_hour}:{current_minute:02d}...")
                    report_msg = get_oil_price_report()
                    send_telegram_message(report_msg)
                    last_sent_slot = slot_name
            else:
                print(f"Ngoài giờ thông báo ({current_hour}:{current_minute:02d}). Bot đang nghỉ.")

            # Kiểm tra lại sau mỗi 30 giây
            time.sleep(30)
            
        except Exception as e:
            print(f"Lỗi trong vòng lặp chính: {e}")
            time.sleep(60)

if __name__ == '__main__':
    import threading
    bot_thread = threading.Thread(target=run_bot_schedule)
    bot_thread.daemon = True
    bot_thread.start()
    
    app.run(host='0.0.0.0', port=10000)
