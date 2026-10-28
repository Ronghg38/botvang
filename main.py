import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CẤU HÌNH THÔNG TIN ---
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
    """Lấy dữ liệu và tính toán phần trăm thay đổi giá dầu theo các mốc thời gian"""
    try:
        # Lấy dữ liệu khung 30 phút để tính toán các mốc thời gian gần
        df = yf.download(SYMBOL, period="2d", interval="30m", progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        closes = df['Close']
        current_price = float(closes.iloc[-1])
        
        # Hàm tính % thay đổi so với N nến trước (mỗi nến 30 phút)
        # n = 1 -> 30 phút, n = 2 -> 1 giờ, n = 4 -> 2 giờ, n = 6 -> 3 giờ, n = 8 -> 4 giờ
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

        # Xây dựng nội dung tin nhắn giống hệt phong cách mẫu trong video
        msg = f"🛢️ **CHỢ GIÁ - DẦU THÔ (WTI)**\n"
        msg += f"Giá hiện tại là `{current_price:.2f}$`\n"
        
        def format_text(val, label):
            if val is None:
                return ""
            status = "tăng" if val >= 0 else "giảm"
            return f"• Giá {status} `{abs(val)}%` trong vòng {label}\n"

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
            
        msg += f"\n⏰ Cập nhật lúc: `{time_str}`"
        return msg

    except Exception as e:
        print(f"Lỗi tính toán dữ liệu dầu: {e}")
        return None

# --- KHỞI ĐỘNG BOT ---
print("🚀 Oil Price Bot (CAUTURONG) đang chạy...")
init_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
send_telegram_message(f"🚀 *Bot Báo Giá Dầu Thô (CAUTURONG)* đã khởi động thành công lúc `{init_time}`!")

# Vòng lặp gửi báo cáo định kỳ (Ví dụ: Cứ mỗi 30 phút gửi 1 lần)
while True:
    try:
        report_msg = get_oil_report()
        if report_msg:
            send_telegram_message(report_msg)
        
        # Nghỉ 30 phút (1800 giây) rồi quét và báo cáo tiếp
        time.sleep(1800)
        
    except Exception as e:
        print(f"Lỗi vòng lặp báo cáo giá dầu: {e}")
        time.sleep(60)
