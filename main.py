import time
import requests
import yfinance as yf
import pandas as pd

# ==========================================
# CẤU HÌNH BOT (CONFIGURATION)
# ==========================================
SYMBOL = "GC=F"       # Mã hợp đồng tương lai Vàng trên Yahoo Finance
INTERVAL = "1h"       # Khung thời gian quét nến: 1h, 15m, 5m
EMA_SHORT = 9         # Đường EMA ngắn hạn
EMA_LONG = 21         # Đường EMA dài hạn
RSI_PERIOD = 14       # Chu kỳ RSI
RSI_OVERBOUGHT = 70   # Ngưỡng quá mua
RSI_OVERSOLD = 30     # Ngưỡng quá bán
RISK_PIPS = 6.0       # Biên độ rủi ro (độ rộng Stop Loss tính bằng giá vàng)

# Cấu hình Telegram (Thay bằng Token và Chat ID thực tế của bạn)
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# ==========================================
# CÁC HÀM HỖ TRỢ
# ==========================================
def send_telegram_message(message: str):
    """Gửi thông báo chi tiết đến Telegram Chat"""
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print(f"[CẢNH BÁO]: Chưa cấu hình Telegram Token!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi tin nhắn Telegram: {e}")

def get_gold_data(symbol: str, interval: str) -> pd.DataFrame:
    """Lấy dữ liệu giá vàng từ Yahoo Finance"""
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="5d", interval=interval)
    return df

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Tính toán chỉ báo EMA và RSI"""
    df['EMA_Short'] = df['Close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['EMA_Long'] = df['Close'].ewm(span=EMA_LONG, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def analyze_signals(df: pd.DataFrame):
    """Phân tích tín hiệu và tự động tính toán SL, TP1, TP2"""
    if len(df) < 2:
        return None, 0, 0, 0, 0, 0
    
    current = df.iloc[-1]
    previous = df.iloc[-2]

    ema_cross_up = (previous['EMA_Short'] <= previous['EMA_Long']) and (current['EMA_Short'] > current['EMA_Long'])
    rsi_buy_valid = current['RSI'] < RSI_OVERBOUGHT

    ema_cross_down = (previous['EMA_Short'] >= previous['EMA_Long']) and (current['EMA_Short'] < current['EMA_Long'])
    rsi_sell_valid = current['RSI'] > RSI_OVERSOLD

    entry_price = current['Close']
    rsi = current['RSI']

    if ema_cross_up and rsi_buy_valid:
        sl = entry_price - RISK_PIPS
        tp1 = entry_price + (RISK_PIPS * 1.5)
        tp2 = entry_price + (RISK_PIPS * 3.0)
        return "BUY", entry_price, rsi, sl, tp1, tp2

    elif ema_cross_down and rsi_sell_valid:
        sl = entry_price + RISK_PIPS
        tp1 = entry_price - (RISK_PIPS * 1.5)
        tp2 = entry_price - (RISK_PIPS * 3.0)
        return "SELL", entry_price, rsi, sl, tp1, tp2
    
    return None, entry_price, rsi, 0, 0, 0

# ==========================================
# CHƯƠNG TRÌNH CHÍNH
# ==========================================
def main():
    print("🤖 Gold Trading Bot đang chạy...")
    send_telegram_message("🚀 *Gold Trading Bot đã được khởi động thành công!*")
    
    last_signal = None

    while True:
        try:
            df = get_gold_data(SYMBOL, INTERVAL)
            df = calculate_indicators(df)
            signal, price, rsi, sl, tp1, tp2 = analyze_signals(df)
            
            timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] Giá Vàng: ${price:.2f} | RSI: {rsi:.2f} | Tín hiệu: {signal if signal else 'HOLD'}")

            if signal and signal != last_signal:
                msg = (
                    f"🚨 *TÍN HIỆU GIAO DỊCH VÀNG ({SYMBOL})*\n"
                    f"• Hành động: *{signal}* 🟢\n"
                    f"• Giá vào (Entry): *${price:.2f}*\n\n"
                    f"🛡 *Quản lý rủi ro:*\n"
                    f"• **Stop Loss (SL):** `${sl:.2f}`\n"
                    f"• **Take Profit 1 (TP1):** `${tp1:.2f}`\n"
                    f"• **Take Profit 2 (TP2):** `${tp2:.2f}`\n\n"
                    f"• RSI hiện tại: `{rsi:.2f}`"
                )
                send_telegram_message(msg)
                last_signal = signal

        except Exception as e:
            print(f"Lỗi vòng lặp: {e}")

        time.sleep(60)

if __name__ == "__main__":
    main()
  
