import datetime
import time
import threading
import io
import matplotlib
matplotlib.use('Agg') # Wichtig für Server ohne Display (Render)
import matplotlib.pyplot as plt
from flask import Flask
import requests
import yfinance as yf
import pandas as pd

app = Flask(__name__)

@app.route("/")
def home():
    return "Titan AI Bot (Ultimate Edition v3.0) is running 24/7!"

def run_flask():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

TELEGRAM_TOKEN = "8878607953:AAHBXqy1Kpa485kYa70hkj_EfaJ_EtHrIYc"

class TitanAI_Analyst:
    def __init__(self, risk_percentage: float = 1.0):
        self.risk_percentage = risk_percentage
        self.last_update_id = 0
        self.journal = {
            "geöffnet": 0,
            "wins": 0,
            "losses": 0,
            "total_pips": 0.0,
            "last_summary_date": None,
            "last_weekly_week": None
        }
        self.waiting_for_close_price = {}
        self.last_active_chat_id = None
        self.active_trade = None

    def send_update_info(self, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        text = (
            "🚀 *TITAN AI UPDATE – Version 3.0 ist live!* 🚀\n\n"
            "*Was ist neu in diesem Update?*\n"
            "🟢 *Multi-Timeframe-Logik:* Der Bot checkt den 1H-Trend und die lokale Struktur.\n"
            "📊 *Live-Chart Bilder:* Setup-Visualisierung direkt als Foto.\n"
            "🎯 *Progressiver Multi-TP-Tracker:* Überwacht fortlaufend alle Stufen von *TP1 bis TP6 (Golden Profit)* im Hintergrund!\n"
            "🛡️ *Automatischer Break-Even:* Sofort-Alarm bei TP1 zum Absichern.\n"
            "📰 *News- & Session-Filter:* Intelligente Erkennung von Marktphasen.\n"
            "🔄 *Dynamische Richtung:* Flexible Long- & Short-Setups.\n\n"
            "🚧 *Work in Progress (Demnächst):*\n"
            "Wir arbeiten aktuell an einem *vollautomatisierten Execution-Bot*, der die Signale direkt abgreift und Trades eigenständig im Broker ausführt! 100% Hands-Free Trading kommt bald. ⏳"
        )
        requests.post(url, json={"chat_id": target_chat_id, "text": text, "parse_mode": "Markdown"})

    def send_persistent_menu(self, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        keyboard = {
            "keyboard": [
                [{"text": "15m LONG"}, {"text": "15m SHORT"}],
                [{"text": "5m LONG"}, {"text": "5m SHORT"}],
                [{"text": "🚀 Update Info (Patch Notes)"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }
        payload = {
            "chat_id": target_chat_id,
            "text": "🎛️ *Titan AI Dynamic Menü aktiv*\nWähle deinen Zeitrahmen und deine Richtung:",
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        requests.post(url, json=payload)

    def send_message_with_buttons(self, text: str, target_chat_id: str, photo_bytes=None):
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Trade geöffnet", "callback_data": "trade_open"},
                    {"text": "🎯 TP / Win erreicht", "callback_data": "trade_win"}
                ],
                [
                    {"text": "❌ Stop-Loss / Loss", "callback_data": "trade_loss"},
                    {"text": "🛡️ Break-Even (BE)", "callback_data": "trade_be"}
                ],
                [
                    {"text": "✏️ Manuell geschlossen", "callback_data": "trade_manual"},
                    {"text": "📊 Journal Statistik", "callback_data": "show_stats"}
                ],
                [
                    {"text": "🤖 Trade automatisieren", "callback_data": "automate_trade"}
                ]
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
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": target_chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
            requests.post(url, json=payload)

    def send_plain_message(self, text: str, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": target_chat_id, "text": text, "parse_mode": "Markdown"})

    def get_market_session(self):
        now_utc = datetime.datetime.utcnow().hour
        if 7 <= now_utc < 12:
            return "London Session 🇬🇧 (Hohe Volatilität)"
        elif 12 <= now_utc < 17:
            return "New York / London Überschneidung 🇺🇸 (Prime Time - News beachten!)"
        elif 17 <= now_utc < 21:
            return "New York Nachmittag 🗽 (Erhöhte Spread-Gefahr)"
        else:
            return "Asien Session 🌙 (Ruhig / Range)"

    def fetch_data(self, interval):
        df = pd.DataFrame()
        for symbol in ["GC=F", "XAUUSD=X"]:
            try:
                df = yf.download(symbol, interval=interval, period="5d", progress=False)
                if not df.empty:
                    break
            except Exception:
                pass
            time.sleep(1)
        return df

    def create_chart_image(self, df, direction, price, sl, tp1):
        try:
            plt.figure(figsize=(10, 5))
            plt.style.use('dark_background')
            
            subset = df.tail(50)
            plt.plot(subset.index, subset['Close'], label='Close', color='#00ffcc', linewidth=1.5)
            if 'EMA_50' in subset:
                plt.plot(subset.index, subset['EMA_50'], label='EMA 50', color='#ffaa00', linestyle='--', alpha=0.8)
            if 'EMA_200' in subset:
                plt.plot(subset.index, subset['EMA_200'],



