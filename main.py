import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone

# --- CẤU HÌNH THÔNG TIN ---
TELEGRAM_TOKEN = "8234059775:AAHk8kv9ruTGV_qsGbFXC7SgTxfRwWOO1BI"
TELEGRAM_CHAT_ID = "5931570040"
SYMBOL = "GC=F"  # Mã vàng trên Yahoo Finance
SL_PIPS = 4.0    # Khoảng cách Stop Loss (4 giá)

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_time():
    """Lấy thời gian chuẩn theo giờ Việt Nam"""
    return datetime.now(VN_TZ)

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
    """Lấy dữ liệu giá vàng qua yfinance"""
    try:
        period = "5d" if interval == "5m" else "30d"
        df = yf.download(SYMBOL, period=period, interval=interval, progress=False)
        if df.empty:
            return None
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
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def check_signal(df, timeframe_name):
    """Kiểm tra tín hiệu giao dịch và format tên CAUTURONG"""
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
    time_str = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')

    # Điều kiện MUA (Buy)
    if price > ma200 and prev_ema9 <= prev_ema21 and ema9 > ema21 and rsi > 50:
        sl = price - SL_PIPS
        tp1 = price + (SL_PIPS * 1.0)
        tp2 = price + (SL_PIPS * 2.2)
        
        msg = (
            f"🟢 **LỆNH MUA (CAUTURONG)**\n"
            f"Cặp: XAUUSD | {timeframe_name.lower()}\n"
            f"Entry: `{price:.2f}`\n"
            f"SL: `{sl:.2f}`\n"
            f"TP1: `{tp1:.2f}`\n"
            f"TP2: `{tp2:.2f}`\n"
            f"⏰ `{time_str}`"
        )
        send_telegram_message(msg)

    # Điều kiện BÁN (Sell)
    elif price < ma200 and prev_ema9 >= prev_ema21 and ema9 < ema21 and rsi < 50:
        sl = price + SL_PIPS
        tp1 = price - (SL_PIPS * 1.0)
        tp2 = price - (SL_PIPS * 2.2)
        
        msg = (
            f"🔴 **LỆNH BÁN (CAUTURONG)**\n"
            f"Cặp: XAUUSD | {timeframe_name.lower()}\n"
            f"Entry: `{price:.2f}`\n"
            f"SL: `{sl:.2f}`\n"
            f"TP1: `{tp1:.2f}`\n"
            f"TP2: `{tp2:.2f}`\n"
            f"⏰ `{time_str}`"
        )
        send_telegram_message(msg)

# --- KHỞI ĐỘNG BOT ---
print("🚀 Gold Trading Bot (CAUTURONG) đang chạy...")
init_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
send_telegram_message(f"🚀 *Gold Trading Bot (CAUTURONG)* đã khởi động thành công lúc `{init_time}`!")

last_daily_report_date = None

while True:
    try:
        current_time = get_vn_time()
        
        # 1. Quét khung M5
        df_m5 = fetch_data("5m")
        check_signal(df_m5, "m5")
        
        time.sleep(10)
        
        # 2. Quét khung M15
        df_m15 = fetch_data("15m")
        check_signal(df_m15, "m15")
        
        # 3. Báo cáo tổng kết cuối ngày lúc 23:59 giờ VN
        if current_time.hour == 23 and current_time.minute >= 55:
            if last_daily_report_date != current_time.date():
                summary_msg = (
                    f"📊 **BÁO CÁO TỔNG KẾT TRONG NGÀY**\n"
                    f"📅 Ngày: {current_time.strftime('%d/%m/%Y')}\n"
                    f"✅ Hệ thống CAUTURONG chạy ổn định."
                )
                send_telegram_message(summary_msg)
                last_daily_report_date = current_time.date()

        # Nghỉ 3 phút trước vòng lặp quét tiếp theo
        time.sleep(180)
        
    except Exception as e:
        print(f"Lỗi vòng lặp chính: {e}")
        time.sleep(60)
