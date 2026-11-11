import datetime
import time
import threading
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, jsonify
import requests
import yfinance as yf
import pandas as pd

app = Flask(__name__)
pending_signal = None

@app.route("/")
def home():
    return "Titan AI Bot (Ultimate Edition v3.0) is running 24/7!"

@app.route("/api/signal", methods=["GET"])
def get_signal():
    global pending_signal
    if pending_signal:
        data = pending_signal
        pending_signal = None 
        return jsonify({"status": "success", "signal": data})
    return jsonify({"status": "empty"})

def run_flask():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

TELEGRAM_TOKEN = "8878607953:AAHBXqy1Kpa485kYa70hkj_EfaJ_EtHrIYc"
ADMIN_USER_ID = 8789124240

class TitanAI_Analyst:
    def __init__(self, risk_percentage: float = 1.0):
        self.risk_percentage = risk_percentage
        self.last_update_id = 0
        self.journal = {"geöffnet": 0, "wins": 0, "losses": 0, "total_pips": 0.0}
        self.last_active_chat_id = None
        self.active_trade = None

    def send_persistent_menu(self, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        keyboard = {
            "keyboard": [
                [{"text": "15m LONG"}, {"text": "15m SHORT"}],
                [{"text": "5m LONG"}, {"text": "5m SHORT"}],
                [{"text": "⚡ LIVE Markt-Analyse"}],
                [{"text": "🚀 Update Info"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }
        payload = {
            "chat_id": target_chat_id,
            "text": "🎛️ *Titan AI Menü*\nWähle deine Analyse aus:",
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        requests.post(url, json=payload)

    def send_message_with_buttons(self, text: str, target_chat_id: str, photo_bytes=None, is_live=False):
        # Dynamischer Button je nach Analyse-Typ
        auto_btn = {"text": "⚡ Sofort Live reingehen!", "callback_data": "automate_live"} if is_live else {"text": "🤖 Als Pending-Order setzen", "callback_data": "automate_pending"}
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Trade geöffnet", "callback_data": "trade_open"},
                    {"text": "🎯 TP / Win erreicht", "callback_data": "trade_win"}
                ],
                [
                    {"text": "❌ Stop-Loss / Loss", "callback_data": "trade_loss"},
                    {"text": "🛡️ Break-Even", "callback_data": "trade_be"}
                ],
                [auto_btn]
            ]
        }

        if photo_bytes:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': ('chart.png', photo_bytes, 'image/png')}
            data = {
                "chat_id": target_chat_id,
                "caption": text,
                "parse_mode": "Markdown",
                "reply_markup": str(keyboard).replace("'", '"')
            }
            requests.post(url, data=data, files=files)

    def send_plain_message(self, text: str, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": target_chat_id, "text": text, "parse_mode": "Markdown"})

    def fetch_data(self, interval):
        df = pd.DataFrame()
        for symbol in ["GC=F", "XAUUSD=X"]:
            try:
                df = yf.download(symbol, interval=interval, period="5d", progress=False)
                if not df.empty: break
            except: pass
            time.sleep(1)
        return df

    def create_chart_image(self, df, direction, price, sl, tp1):
        try:
            plt.figure(figsize=(10, 5))
            plt.style.use('dark_background')
            subset = df.tail(50)
            plt.plot(subset.index, subset['Close'], label='Close', color='#00ffcc')
            plt.axhline(price, color='#ffffff', linestyle='-', label=f'Entry: {price}')
            plt.axhline(sl, color='#ff3333', linestyle=':', label=f'SL: {sl}')
            plt.axhline(tp1, color='#33ff33', linestyle=':', label=f'TP1: {tp1}')
            plt.title(f"Titan AI Setup | {direction}")
            plt.legend(loc='upper left', fontsize=8)
            plt.grid(color='#333333', linestyle='--', linewidth=0.5)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            plt.close()
            return buf.getvalue()
        except:
            return None

    def analyze_market(self, timeframe="15m", force_direction="LONG", is_live_mode=False):
        df_exec = self.fetch_data(timeframe)
        if df_exec.empty: return "⚠️ Marktdaten fehlen.", None

        if isinstance(df_exec.columns, tuple) or hasattr(df_exec.columns, 'levels'):
            df_exec.columns = [col[0] if isinstance(col, tuple) else col for col in df_exec.columns]
        df_exec['EMA_200'] = df_exec['Close'].ewm(span=200, adjust=False).mean()
        
        current = df_exec.iloc[-1]
        price = round(float(current['Close']), 2)
        ema200 = float(current['EMA_200'])

        # Automatische Richtung im Live-Modus bestimmen
        if is_live_mode:
            force_direction = "LONG" if price > ema200 else "SHORT"

        raw_dir = force_direction
        direction = f"🟢 {raw_dir} 📈" if raw_dir == "LONG" else f"🔴 {raw_dir} 📉"

        # Dynamischer ATR für SL/TP
        high_low = df_exec['High'] - df_exec['Low']
        high_close = (df_exec['High'] - df_exec['Close'].shift()).abs()
        low_close = (df_exec['Low'] - df_exec['Close'].shift()).abs()
        atr = float(pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).ewm(alpha=1/14, adjust=False).mean().iloc[-1])

        sl_dist = round(atr * 1.2, 2)
        if raw_dir == "LONG":
            sl = price - sl_dist
            tp1 = price + 3.0; tp2 = price + 6.0; tp6 = price + (atr*4.0)
        else:
            sl = price + sl_dist
            tp1 = price - 3.0; tp2 = price - 6.0; tp6 = price - (atr*4.0)
        
        mode_title = "⚡ LIVE MARKT-ANALYSE" if is_live_mode else f"🚨 SETUP [{timeframe}]"
        
        self.active_trade = {
            "direction": raw_dir,
            "entry": price,
            "sl": sl,
            "tps": [tp1, tp2, tp6],
            "chat_id": self.last_active_chat_id
        }

        chart_bytes = self.create_chart_image(df_exec, raw_dir, price, sl, tp1)

        report = (
            f"*{mode_title}*\n\n"
            f"• *Richtung:* `{direction}`\n"
            f"• *Aktueller Preis:* `{price}`\n"
            f"• *Stop-Loss:* `{sl:.2f}`\n\n"
            f"🎯 *Take Profits:*\n"
            f"• *TP1:* `{tp1:.2f}` | *TP2:* `{tp2:.2f}`\n"
        )
        return report, chart_bytes

    def handle_callback(self, callback_query):
        global pending_signal
        query_id = callback_query.get("id")
        data = callback_query.get("data")
        user_id = callback_query.get("from", {}).get("id")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        self.last_active_chat_id = chat_id

        answer_text = "Erfolgreich vermerkt!"
        
        if data in ["automate_live", "automate_pending"]:
            if user_id != ADMIN_USER_ID:
                answer_text = "Zugriff verwehrt! Nur der Admin darf das."
            else:
                if self.active_trade:
                    order_type = "MARKET" if data == "automate_live" else "PENDING"
                    pending_signal = {
                        "direction": self.active_trade["direction"],
                        "entry": self.active_trade["entry"],
                        "sl": self.active_trade["sl"],
                        "tp1": self.active_trade["tps"][0],
                        "type": order_type
                    }
                    answer_text = f"Signal ({order_type}) an PC gesendet!"
                    self.send_plain_message(f"⚡ **{order_type}-Order an PC geschickt!**\nWird jetzt in MT5 eingetragen.", str(chat_id))
                else:
                    answer_text = "⚠️ Kein aktiver Trade im Speicher!"
        
        elif data == "trade_open": self.journal["geöffnet"] += 1
        elif data == "trade_win": self.journal["wins"] += 1; self.active_trade = None
        elif data == "trade_loss": self.journal["losses"] += 1; self.active_trade = None

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id, "text": answer_text})

    def listen(self):
        try: requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook", timeout=5)
        except: pass
        
        print("Titan AI v3.0 Polling gestartet...")
        while True:
            try:
                res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={self.last_update_id + 1}&timeout=10", timeout=15).json()
                if res.get("ok") and res.get("result"):
                    for update in res["result"]:
                        self.last_update_id = update["update_id"]
                        if "callback_query" in update:
                            self.handle_callback(update["callback_query"])
                            continue

                        msg = update.get("message") or {}
                        chat_id = msg.get("chat", {}).get("id")
                        text_cmd = msg.get("text", "").strip().lower()
                        if not chat_id: continue
                        self.last_active_chat_id = chat_id

                        if text_cmd in ["/start", "update info"]:
                            self.send_persistent_menu(str(chat_id))
                        elif "live markt-analyse" in text_cmd:
                            setup, chart = self.analyze_market("5m", is_live_mode=True)
                            self.send_message_with_buttons(setup, str(chat_id), chart, is_live=True)
                        elif text_cmd == "15m long":
                            setup, chart = self.analyze_market("15m", "LONG")
                            self.send_message_with_buttons(setup, str(chat_id), chart, is_live=False)
                        elif text_cmd == "15m short":
                            setup, chart = self.analyze_market("15m", "SHORT")
                            self.send_message_with_buttons(setup, str(chat_id), chart, is_live=False)
                        elif text_cmd == "5m long":
                            setup, chart = self.analyze_market("5m", "LONG")
                            self.send_message_with_buttons(setup, str(chat_id), chart, is_live=False)
                        elif text_cmd == "5m short":
                            setup, chart = self.analyze_market("5m", "SHORT")
                            self.send_message_with_buttons(setup, str(chat_id), chart, is_live=False)
            except: pass
            time.sleep(2)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    analyst = TitanAI_Analyst()
    print("Titan AI Dienste aktiv...")
    analyst.listen()


