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
        # Lấy dữ liệu lịch sử giá dầu thô WTI (CL=F)
        ticker = yf.Ticker("CL=F")
        df = ticker.history(period="2d", interval="30m")
        
        if df.empty or len(df) < 2:
            return "⚠️ Không thể lấy đủ dữ liệu giá dầu lúc này."
            
        current_price = df['Close'].iloc[-1]
        
        # 1. Tính % thay đổi trong 30 phút qua
        prev_price_30m = df['Close'].iloc[-2]
        change_30m = ((current_price - prev_price_30m) / prev_price_30m) * 100
        
        # 2. Tính % thay đổi trong ngày (so với giá mở cửa phiên giao dịch hôm nay)
        today_date = datetime.now(timezone(timedelta(hours=7))).date()
        df_today = df[df.index.date == today_date]
        
        if not df_today.empty:
            open_price_today = df_today['Open'].iloc[0]
            change_day = ((current_price - open_price_today) / open_price_today) * 100
        else:
            change_day = 0.0

        def format_change(val):
            icon = "🟢" if val >= 0 else "🔴"
            text = "Tăng" if val >= 0 else "Giảm"
            return f"{icon} {text} {val:+.2f}%"

        str_30m = format_change(change_30m)
        str_day = format_change(change_day)

        message = (
            f"🛢️ <b>CHỢ GIÁ - DẦU THÔ (WTI) [CAUTURONG]</b>\n"
            f"💰 Giá hiện tại: <b>{current_price:.2f}$</b>\n"
            f"----------------------------------\n"
            f"{str_30m} (trong 30 phút)\n"
            f"{str_day} (trong ngày)\n"
            f"----------------------------------\n"
            f"⏰ Cập nhật: {datetime.now(timezone(timedelta(hours=7))).strftime('%H:%M - %d/%m/%Y')}"
        )
        return message
    except Exception as e:
        return f"⚠️ Lỗi lấy giá dầu: {e}"

def run_bot_schedule():
    VN_TIMEZONE = timezone(timedelta(hours=7))
    print("🤖 Bot Báo Giá Dầu (CAUTURONG) đã khởi động thành công!")
    
    last_sent_minute = -1

    while True:
        try:
            now_vn = datetime.now(VN_TIMEZONE)
            current_hour = now_vn.hour
            current_minute = now_vn.minute
            
            # --- KHUNG GIỜ HOẠT ĐỘNG: Từ 5:00 sáng đến 20:30 tối ---
            # Từ 5:00 đến trước 20:30 (tính đến mốc 20:30)
            is_after_start = (current_hour > 5) or (current_hour == 5 and current_minute >= 0)
            is_before_end = (current_hour < 20) or (current_hour == 20 and current_minute <= 30)
            is_allowed_time = is_after_start and is_before_end
            
            if is_allowed_time:
                # Cứ mỗi 30 phút (phút 0 hoặc phút 30) thì gửi tin
                if current_minute in [0, 30] and current_minute != last_sent_minute:
                    print(f"Đang gửi báo cáo định kỳ lúc {current_hour}:{current_minute:02d}...")
                    report_msg = get_oil_price_report()
                    send_telegram_message(report_msg)
                    last_sent_minute = current_minute
            else:
                print(f"Ngoài giờ thông báo ({current_hour}:{current_minute:02d}). Bot đang nghỉ.")

            # Kiểm tra lại sau mỗi 20 giây để bắt chuẩn xác mốc phút
            time.sleep(20)
            
        except Exception as e:
            print(f"Lỗi trong vòng lặp chính: {e}")
            time.sleep(60)

if __name__ == '__main__':
    import threading
    bot_thread = threading.Thread(target=run_bot_schedule)
    bot_thread.daemon = True
    bot_thread.start()
    
    app.run(host='0.0.0.0', port=10000)
