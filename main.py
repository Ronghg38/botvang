import time
import requests
import pandas as pd
from datetime import datetime
import MetaTrader5 as mt5

# --- CẤU HÌNH THÔNG TIN ---
TELEGRAM_TOKEN = "8234059775:AAHk8kv9ruTGV_qsGbFXC7SgTxfRwWOO1BI"
TELEGRAM_CHAT_ID = "5931570040"
SYMBOL = "XAUUSD"  # Hoặc "GOLD" tùy sàn của bạn

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

def initialize_mt5():
    """Khởi kết nối với phần mềm MetaTrader 5"""
    if not mt5.initialize():
        print(f"Lỗi kết nối MT5, mã lỗi: {mt5.last_error()}")
        return False
    print("Kết nối MetaTrader 5 thành công!")
    return True

def fetch_mt5_data(timeframe, count=250):
    """Lấy dữ liệu nến từ MT5 (cần tối thiểu 200 nến để tính MA200 chính xác)"""
    rates = mt5.copy_rates_from_pos(SYMBOL, timeframe, 0, count)
    if rates is None:
        print(f"Không thể lấy dữ liệu cho mã {SYMBOL}")
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.rename(columns={'close': 'Close'}, inplace=True)
    return df

def calculate_indicators(df):
    """Tính toán EMA 9, EMA 21, RSI 14 và Bộ lọc MA 200"""
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean() # Bộ lọc xu hướng dài hạn
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def check_signal(timeframe_enum, timeframe_name):
    """Kiểm tra tín hiệu giao dịch có kết hợp bộ lọc MA200"""
    df = fetch_mt5_data(timeframe_enum, count=250)
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
            f"🟢 **TÍN HIỆU MUA (BUY) - MT5 [{timeframe_name}]** 🟢\n\n"
            f"🪙 Tài sản: XAU/USD (Gold)\n"
            f"📍 Điểm vào (Entry): `{price:.2f}`\n"
            f"🛑 Cắt lỗ (SL): `{sl:.2f}` (6 pips)\n"
            f"🎯 Chốt lời 1 (TP1): `{tp1:.2f}` (1.5R)\n"
            f"🎯 Chốt lời 2 (TP2): `{tp2:.2f}` (3.0R)\n"
            f"🛡️ *Bộ lọc xu hướng: Giá nằm trên MA200 (Xu hướng Tăng)*\n"
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
            f"🔴 **TÍN HIỆU BÁN (SELL) - MT5 [{timeframe_name}]** 🔴\n\n"
            f"🪙 Tài sản: XAU/USD (Gold)\n"
            f"📍 Điểm vào (Entry): `{price:.2f}`\n"
            f"🛑 Cắt lỗ (SL): `{sl:.2f}` (6 pips)\n"
            f"🎯 Chốt lời 1 (TP1): `{tp1:.2f}` (1.5R)\n"
            f"🎯 Chốt lời 2 (TP2): `{tp2:.2f}` (3.0R)\n"
            f"🛡️ *Bộ lọc xu hướng: Giá nằm dưới MA200 (Xu hướng Giảm)*\n"
            f"💡 *Gợi ý: Khi đạt TP1, dời SL về hòa vốn (Entry).* \n"
            f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_message(msg)

# --- KHỞI ĐỘNG CHƯƠNG TRÌNH ---
if not initialize_mt5():
    quit()

send_telegram_message("🚀 *Gold Trading Bot (MT5 + MA200 Filter)* đã được khởi động thành công!")
last_daily_report_date = None

while True:
    try:
        current_time = datetime.now()
        
        # Quét khung M5 và M15 từ MT5
        check_signal(mt5.TIMEFRAME_M5, "M5")
        time.sleep(5)
        check_signal(mt5.TIMEFRAME_M15, "M15")
        
        # Báo cáo cuối ngày lúc 23:59
        if current_time.hour == 23 and current_time.minute >= 55:
            if last_daily_report_date != current_time.date():
                summary_msg = (
                    f"📊 **BÁO CÁO TỔNG KẾT TRONG NGÀY (MT5 + MA200)** 📊\n"
                    f"📅 Ngày: {current_time.strftime('%d/%m/%Y')}\n"
                    f"✅ Bot lọc xu hướng dài hạn hoạt động ổn định."
                )
                send_telegram_message(summary_msg)
                last_daily_report_date = current_time.date()

        # Nghỉ 3 phút trước vòng lặp quét tiếp theo
        time.sleep(180)
        
    except Exception as e:
        print(f"Lỗi vòng lặp chính: {e}")
        time.sleep(60)

mt5.shutdown()
