import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- CẤU HÌNH THÔNG TIN ---
TELEGRAM_TOKEN = "8234059775:AAHk8kv9ruTGV_qsGbFXC7SgTxfRwWOO1BI"
TELEGRAM_CHAT_ID = "5931570040"
SYMBOL = "GC=F"  # Mã vàng trên Yahoo Finance (XAU/USD)

def send_telegram_message(message):
    """Gửi thông báo tới Telegram"""
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

def fetch_data(interval="5m"):
    """Lấy dữ liệu giá vàng qua yfinance (Hỗ trợ chạy trên Render)"""
    try:
        # Lấy đủ dữ liệu để tính MA200 (cần ít nhất vài trăm nến)
        period = "5d" if interval == "5m" else "30d"
        df = yf.download(SYMBOL, period=period, interval=interval, progress=False)
        if df.empty:
            return None
        # Xử lý đa cấp index của yfinance nếu có
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        print(f"Lỗi tải dữ liệu {interval}: {e}")
        return None

def calculate_indicators(df):
    """Tính toán EMA (9, 21), RSI (14) và MA 200"""
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean() # Bộ lọc xu hướng dài hạn
    
    # Tính RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def check_signal(df, timeframe_name):
    """Kiểm tra tín hiệu giao dịch kết hợp bộ lọc MA200"""
    if df is None or len(df) < 210:
        return
    
    df = calculate_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = float(last['Close'])
    ema9 = float(last['EMA9'])
    ema21 = float(last['EMA21'])
    ma200 = float(last['MA200'])
    rsi = float(last['RSI'])
    
    prev_ema9 = float(prev['EMA9'])
    prev_ema21 = float(prev['EMA21'])

    # Điều kiện MUA (Buy): Giá nằm trên MA200 + EMA9 cắt lên EMA21 + RSI > 50
    if price > ma200 and prev_ema9 <= prev_ema21 and ema9 > ema21 and rsi > 50:
        sl = price - 6.0
        tp1 = price + (6.0 * 1.5)
        tp2 = price + (6.0 * 3.0)
        
        msg = (
            f"🟢 **TÍN HIỆU MUA (BUY) - Khung {timeframe_name}** 🟢\n\n"
            f"🪙 Tài sản: XAU/USD (Gold)\n"
            f"📍 Điểm vào (Entry): `{price:.2f}`\n"
            f"🛑 Cắt lỗ (SL): `{sl:.2f}` (6 pips)\n"
            f"🎯 Chốt lời 1 (TP1): `{tp1:.2f}` (1.5R)\n"
            f"🎯 Chốt lời 2 (TP2): `{tp2:.2f}` (3.0R)\n"
            f"🛡️ *Bộ lọc xu hướng: Giá nằm trên MA200*\n"
            f"💡 *Gợi ý: Khi đạt TP1, dời SL về hòa vốn (Entry).* \n"
            f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_message(msg)

    # Điều kiện BÁN (Sell): Giá nằm dưới MA200 + EMA9 cắt xuống EMA21 + RSI < 50
    elif price < ma200 and prev_ema9 >= prev_ema21 and ema9 < ema21 and rsi < 50:
        sl = price + 6.0
        tp1 = price - (6.0 * 1.5)
        tp2 = price - (6.0 * 3.0)
        
        msg = (
            f"🔴 **TÍN HIỆU BÁN (SELL) - Khung {timeframe_name}** 🔴\n\n"
            f"🪙 Tài sản: XAU/USD (Gold)\n"
            f"📍 Điểm vào (Entry): `{price:.2f}`\n"
            f"🛑 Cắt lỗ (SL): `{sl:.2f}` (6 pips)\n"
            f"🎯 Chốt lời 1 (TP1): `{tp1:.2f}` (1.5R)\n"
            f"🎯 Chốt lời 2 (TP2): `{tp2:.2f}` (3.0R)\n"
            f"🛡️ *Bộ lọc xu hướng: Giá nằm dưới MA200*\n"
            f"💡 *Gợi ý: Khi đạt TP1, dời SL về hòa vốn (Entry).* \n"
            f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_message(msg)

# --- KHỞI ĐỘNG BOT TRÊN RENDER ---
print("🚀 Gold Trading Bot (Render Cloud + MA200) đang chạy...")
send_telegram_message("🚀 *Gold Trading Bot (Chạy Cloud 24/7 + Lọc MA200)* đã được khởi động thành công!")

last_daily_report_date = None

while True:
    try:
        current_time = datetime.now()
        
        # 1. Quét khung M5
        df_m5 = fetch_data("5m")
        check_signal(df_m5, "M5")
        
        time.sleep(10)
        
        # 2. Quét khung M15
        df_m15 = fetch_data("15m")
        check_signal(df_m15, "M15")
        
        # 3. Báo cáo tổng kết cuối ngày lúc 23:59
        if current_time.hour == 23 and current_time.minute >= 55:
            if last_daily_report_date != current_time.date():
                summary_msg = (
                    f"📊 **BÁO CÁO TỔNG KẾT TRONG NGÀY** 📊\n"
                    f"📅 Ngày: {current_time.strftime('%d/%m/%Y')}\n"
                    f"✅ Bot cloud hoạt động ổn định 24/7 trên cả M5 và M15."
                )
                send_telegram_message(summary_msg)
                last_daily_report_date = current_time.date()

        # Nghỉ 3 phút trước vòng lặp quét tiếp theo
        time.sleep(180)
        
    except Exception as e:
        print(f"Lỗi vòng lặp chính: {e}")
        time.sleep(60)
