import time
import requests
import yfinance as yf
import pandas as pd
import sqlite3
import io
import matplotlib
matplotlib.use('Agg') # Bắt buộc để vẽ biểu đồ trên server Linux (Render)
import matplotlib.pyplot as plt
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

# --- KHỞI TẠO DATABASE SQLITE ---
def init_db():
    """Khởi tạo bảng lưu lịch sử giá"""
    try:
        conn = sqlite3.connect('price_history.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                price REAL
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Lỗi khởi tạo Database: {e}")

def save_price_to_db(symbol, price):
    """Lưu giá tài sản vào SQLite"""
    try:
        conn = sqlite3.connect('price_history.db')
        cursor = conn.cursor()
        now_str = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO history (timestamp, symbol, price) VALUES (?, ?, ?)", (now_str, symbol, price))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Lỗi lưu giá vào DB: {e}")

# --- GỬI TIN NHẮN / ẢNH QUA TELEGRAM ---
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

def send_telegram_photo(buf, caption):
    """Gửi ảnh biểu đồ tới Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {'photo': ('chart.png', buf, 'image/png')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=data, files=files, timeout=15)
    except Exception as e:
        print(f"Lỗi gửi ảnh biểu đồ: {e}")

# --- HÀM LẤY DỮ LIỆU VÀ TÍNH TOÁN CHO TỪNG TÀI SẢN ---
def get_single_asset_report(symbol, title):
    """Lấy dữ liệu, tính biến động (1 giờ, 24 giờ, 1 tuần, 1 tháng) và lưu lịch sử"""
    try:
        # Lấy dữ liệu 1 tháng để tính toán đầy đủ các khung thời gian
        df = yf.download(symbol, period="1mo", interval="1h", progress=False)
        if df.empty or len(df) < 5:
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

        # Lưu giá hiện tại vào database lịch sử
        save_price_to_db(symbol, current_price)

        now_vn = get_vn_time()
        
        # Hàm tính biến động theo mốc thời gian cách hiện tại (số giờ)
        def get_past_change(hours_ago):
            target_time = now_vn - timedelta(hours=hours_ago)
            idx = df.index.get_indexer([target_time], method='nearest')[0]
            past_price = float(closes.iloc[idx])
            if symbol == "GC=F":
                past_price += GOLD_OFFSET
            pct = ((current_price - past_price) / past_price) * 100
            past_time_str = df.index[idx].strftime('%H:%M %d/%m')
            return round(pct, 2), past_time_str

        pct_1h, time_1h = get_past_change(1)
        pct_24h, _ = get_past_change(24)
        pct_1wk, _ = get_past_change(168) # 7 ngày * 24h
        pct_1mo, _ = get_past_change(720) # 30 ngày * 24h

        def format_line(val, label):
            icon = "🟢" if val >= 0 else "🔴"
            sign = "+" if val >= 0 else ""
            return f"{icon} `{sign}{val}%` | {label}\n"

        icon_title = "🟡" if "VÀNG" in title else "🛢️"
        
        msg = f"{icon_title} *{title}*\n"
        msg += f"💵 Giá hiện tại: **{current_price:.2f}$**\n"
        msg += f"───────────────────\n"
        msg += f"📊 Thống kê biến động:\n"
        msg += format_line(pct_1h, f"1 giờ qua (lúc {time_1h})")
        msg += format_line(pct_24h, "24 giờ qua")
        msg += format_line(pct_1wk, "1 tuần qua")
        msg += format_line(pct_1mo, "1 tháng qua")
        msg += f"───────────────────\n"
        
        return msg

    except Exception as e:
        print(f"Lỗi lấy dữ liệu {title}: {e}")
        return f"📌 *{title}*: ⚠️ Không thể lấy dữ liệu lúc này.\n"

# Các hàm báo cáo nhóm tài sản
def get_oil_report():
    wti_msg = get_single_asset_report("CL=F", "DẦU THÔ WTI (USOIL)")
    brent_msg = get_single_asset_report("BZ=F", "DẦU THÔ BRENT (UKOIL)")
    time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
    return f"{wti_msg}\n═══════════════════\n{brent_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"

def get_gold_report():
    gold_msg = get_single_asset_report("GC=F", "VÀNG THẾ GIỚI (GOLD)")
    time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
    return f"{gold_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"

def get_all_market_report():
    """Báo cáo gộp chung cả Dầu và Vàng"""
    wti_msg = get_single_asset_report("CL=F", "DẦU THÔ WTI (USOIL)")
    gold_msg = get_single_asset_report("GC=F", "VÀNG THẾ GIỚI (GOLD)")
    time_str = get_vn_time().strftime('%H:%M - %d/%m/%Y')
    return f"⚡ *BẢN TIN THỊ TRƯỜNG TỔNG HỢP*\n\n{wti_msg}\n═══════════════════\n{gold_msg}\n═══════════════════\n⏰ Cập nhật lúc: `{time_str}`"

# --- HÀM VẼ BIỂU ĐỒ XU HƯỚNG TỪ DATABASE ---
def generate_and_send_chart(symbol, title):
    """Vẽ biểu đồ xu hướng giá từ dữ liệu SQLite đã lưu"""
    try:
        conn = sqlite3.connect('price_history.db')
        query = f"SELECT timestamp, price FROM history WHERE symbol = '{symbol}' ORDER BY timestamp DESC LIMIT 72"
        df_db = pd.read_sql(query, conn)
        conn.close()

        if df_db.empty or len(df_db) < 3:
            send_telegram_message(f"⚠️ Chưa đủ dữ liệu lịch sử để vẽ biểu đồ cho *{title}*.")
            return

        df_db = df_db.sort_values('timestamp')
        
        # Vẽ biểu đồ Matplotlib
        plt.figure(figsize=(10, 5))
        plt.plot(pd.to_datetime(df_db['timestamp']), df_db['price'], marker='o', color='tab:blue', linewidth=2, markersize=4)
        plt.title(f"Biểu đồ biến động {title} (Lịch sử Bot)", fontsize=14, fontweight='bold')
        plt.xlabel("Thời gian (VN)", fontsize=10)
        plt.ylabel("Giá ($)", fontsize=10)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.xticks(rotation=25)
        plt.tight_layout()

        # Lưu vào buffer bộ nhớ
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        buf.seek(0)
        plt.close()

        send_telegram_photo(buf, f"📈 *Biểu đồ xu hướng thực tế: {title}*")

    except Exception as e:
        print(f"Lỗi vẽ biểu đồ: {e}")
        send_telegram_message(f"⚠️ Lỗi khi vẽ biểu đồ {title}.")

# --- LẮNG NGHE LỆNH TỪ TELEGRAM ---
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
                    
                    if text in ["xem", "dau", "dầu"]:
                        print("Nhận lệnh Dầu. Đang gửi...")
                        report_msg = get_oil_report()
                        send_telegram_message("⚡ *BẢN TIN DẦU THÔ*\n\n" + report_msg)
                            
                    elif text in ["vang", "gold", "vàng", "vàn"]:
                        print("Nhận lệnh Vàng. Đang gửi...")
                        report_msg = get_gold_report()
                        send_telegram_message("⚡ *BẢN TIN VÀNG THẾ GIỚI*\n\n" + report_msg)

                    elif text in ["chung", "all", "tonghop", "tổng hợp"]:
                        print("Nhận lệnh Tổng hợp. Đang gửi...")
                        report_msg = get_all_market_report()
                        send_telegram_message(report_msg)

                    elif text in ["bieudo dau", "biểu đồ dầu", "chart dau"]:
                        print("Gửi biểu đồ Dầu WTI...")
                        generate_and_send_chart("CL=F", "DẦU THÔ WTI (USOIL)")

                    elif text in ["bieudo vang", "biểu đồ vàng", "chart vang"]:
                        print("Gửi biểu đồ Vàng...")
                        generate_and_send_chart("GC=F", "VÀNG THẾ GIỚI (GOLD)")
                            
                    elif text in ["/start", "/help", "help", "giúp"]:
                        help_msg = (
                            "🤖 *HƯỚNG DẪN SỬ DỤNG BOT CAUTURONG*\n\n"
                            "• `dau` hoặc `xem`: Xem báo cáo giá Dầu (WTI & Brent)\n"
                            "• `vang` hoặc `gold`: Xem báo cáo giá Vàng Thế Giới\n"
                            "• `chung`: Xem bảng tổng hợp cả Dầu và Vàng\n"
                            "• `bieudo dau`: Nhận ảnh biểu đồ xu hướng Dầu\n"
                            "• `bieudo vang`: Nhận ảnh biểu đồ xu hướng Vàng\n\n"
                            "⏱️ *Bot tự động gửi bản tin hằng giờ (Thứ 2 đến Thứ 6).*_"
                        )
                        send_telegram_message(help_msg)
                            
        except Exception as e:
            print(f"Lỗi đọc lệnh Telegram: {e}")
            time.sleep(5)

# --- VÒNG LẶP CHẠY BOT ĐỊNH KỲ ---
def run_bot():
    init_db() # Khởi tạo database khi khởi động
    print("🚀 Bot (CAUTURONG) đang chạy...")
    init_time = get_vn_time().strftime('%Y-%m-%d %H:%M:%S')
    send_telegram_message(f"🚀 *Bot Báo Giá (CAUTURONG)* đã khởi động thành công lúc `{init_time}`!")

    cmd_thread = Thread(target=check_telegram_commands)
    cmd_thread.daemon = True
    cmd_thread.start()

    last_sent_slot = ""

    while True:
        try:
            now_vn = get_vn_time()
            weekday = now_vn.weekday() # 0-4 (Thứ 2 đến Thứ 6), 5-6 (Cuối tuần)
            current_hour = now_vn.hour
            current_minute = now_vn.minute
            current_date = now_vn.date()
            
            # Tạm nghỉ tự động vào cuối tuần
            if weekday >= 5:
                print(f"Hôm nay là cuối tuần. Bot tạm nghỉ thông báo tự động.")
                time.sleep(300)
                continue

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
                    report_msg = get_oil_report() # Giữ nguyên báo cáo hằng giờ cũ cho Dầu (hoặc bạn có thể đổi thành get_all_market_report() nếu muốn gửi cả Vàng hằng giờ)
                    send_telegram_message(report_msg)
                    last_sent_slot = slot_name
            else:
                print(f"Ngoài giờ thông báo ({current_hour}:{current_minute:02d}). Bot đang nghỉ.")

            time.sleep(30)
            
        except Exception as e:
            print(f"Lỗi vòng lặp báo cáo giá: {e}")
            time.sleep(60)

if __name__ == '__main__':
    # Chạy vòng lặp bot ở luồng phụ
    t = Thread(target=run_bot)
    t.daemon = True
    t.start()
    
    # Chạy Flask Web Server ở luồng chính (cho Render)
    run_web()
