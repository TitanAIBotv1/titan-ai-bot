import datetime
import time
import threading
from flask import Flask
import requests
import yfinance as yf
import pandas as pd

app = Flask(__name__)

@app.route("/")
def home():
    return "Titan AI Bot is running 24/7!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

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

    def send_persistent_menu(self, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        keyboard = {
            "keyboard": [
                [{"text": "15m"}, {"text": "5m"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }
        payload = {
            "chat_id": target_chat_id,
            "text": "🎛️ *Titan AI Steuerungs-Menü aktiv*\nWähle direkt über die Buttons unten:",
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        res = requests.post(url, json=payload)
        print(f"send_persistent_menu Status: {res.status_code}")

    def send_message_with_buttons(self, text: str, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
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
                ]
            ]
        }
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        res = requests.post(url, json=payload)
        print(f"send_message_with_buttons Status: {res.status_code}")

    def send_plain_message(self, text: str, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": target_chat_id, "text": text, "parse_mode": "Markdown"})

    def get_market_session(self):
        now_utc = datetime.datetime.utcnow().hour
        if 7 <= now_utc < 12:
            return "London Session 🇬🇧"
        elif 12 <= now_utc < 17:
            return "New York / London Überschneidung 🇺🇸"
        elif 17 <= now_utc < 21:
            return "New York Nachmittag 🗽"
        else:
            return "Asien Session 🌙 (Ruhig)"

    def fetch_data(self, interval):
        df = pd.DataFrame()
        for symbol in ["GC=F", "XAUUSD=X"]:
            try:
                df = yf.download(symbol, interval=interval, period="5d", progress=False)
                if not df.empty:
                    print(f"Marktdaten erfolgreich geladen von {symbol}")
                    break
            except Exception as e:
                print(f"Fehler bei yfinance Download ({symbol}): {e}")
            time.sleep(1)
        return df

    def analyze_market(self, timeframe="15m"):
        df = self.fetch_data(timeframe)
        if df.empty:
            print("Fehler: Yahoo Finance hat leere Daten geliefert.")
            return "⚠️ *Marktdaten konnten aktuell nicht geladen werden.* Bitte erneut versuchen."

        if isinstance(df.columns, tuple) or hasattr(df.columns, 'levels'):
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()

        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATRr_14'] = tr.ewm(alpha=1/14, adjust=False).mean()
       
        current = df.iloc[-1]
       
        price = round(float(current['Close']), 2)
        ema50 = float(current['EMA_50'])
        ema200 = float(current['EMA_200'])
        rsi = float(current['RSI_14'])
        atr = float(current['ATRr_14'])

        prob = 50.0
       
        if price > ema200:
            direction = "🟢 LONG 📈 *(Kurs über EMA)*"
            raw_dir = "LONG"
        else:
            direction = "🔴 SHORT 📉 *(Kurs unter EMA)*"
            raw_dir = "SHORT"
       
        if raw_dir == "LONG" and price > ema50: prob += 15.0
        if raw_dir == "SHORT" and price < ema50: prob += 15.0
        if 40 <= rsi <= 60: prob += 10.0
       
        session_info = self.get_market_session()

        if timeframe == "5m":
            sl_dist = round(atr * 0.9, 2)
            if raw_dir == "LONG":
                sl = price - sl_dist
                tp1 = price + 1.5; tp2 = price + 3.0; tp3 = price + 5.0
                tp4 = price + (atr * 1.0); tp5 = price + (atr * 1.8); tp6 = price + (atr * 3.0)
            else:
                sl = price + sl_dist
                tp1 = price - 1.5; tp2 = price - 3.0; tp3 = price - 5.0
                tp4 = price - (atr * 1.0); tp5 = price - (atr * 1.8); tp6 = price - (atr * 3.0)
            title = "⚡ *TITAN AI SCALP-ALERT [5m]* ⚡"
        else:
            sl_dist = round(atr * 1.2, 2)
            if raw_dir == "LONG":
                sl = price - sl_dist
                tp1 = price + 3.0; tp2 = price + 6.0; tp3 = price + 10.0
                tp4 = price + (atr * 1.5); tp5 = price + (atr * 2.5); tp6 = price + (atr * 4.0)
            else:
                sl = price + sl_dist
                tp1 = price - 3.0; tp2 = price - 6.0; tp3 = price - 10.0
                tp4 = price - (atr * 1.5); tp5 = price - (atr * 2.5); tp6 = price - (atr * 4.0)
            title = "🚨 *TITAN AI SETUP-ALERT [15m]* 🚨"

        return (
            f"{title}\n\n"
            f"• *Richtung:* `{direction}`\n"
            f"• *Win-Wahrscheinlichkeit:* `{prob}%`\n"
            f"• *Handelsphase:* `{session_info}`\n\n"
            f"• *Live-Entry:* `{price}`\n"
            f"• *Stop-Loss:* `{sl:.2f}`\n"
            f"• *Risiko:* `{self.risk_percentage}%`\n\n"
            f"🎯 *Take Profits & Management:*\n"
            f"• *TP1:* `{tp1:.2f}`\n"
            f"• *TP2:* `{tp2:.2f}`\n"
            f"• *TP3:* `{tp3:.2f}`\n"
            f"• *TP4:* `{tp4:.2f}`\n"
            f"• *TP5:* `{tp5:.2f}`\n"
            f"• *🏆 Golden Profit (TP6):* `{tp6:.2f}`\n\n"
            f"⚖️ *Disclaimer:* Dies ist eine rein algorithmische Marktanalyse und keine Handelsempfehlung."
        )

    def handle_callback(self, callback_query):
        query_id = callback_query.get("id")
        data = callback_query.get("data")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        self.last_active_chat_id = chat_id

        answer_text = "Erfolgreich vermerkt!"
        if data == "trade_open":
            self.journal["geöffnet"] += 1
            answer_text = "Trade als geöffnet vermerkt."
        elif data == "trade_win":
            self.journal["wins"] += 1
            self.journal["total_pips"] += 30.0
            answer_text = "Win verbucht!"
        elif data == "trade_loss":
            self.journal["losses"] += 1
            self.journal["total_pips"] -= 15.0
            answer_text = "Verlust verbucht."
        elif data == "trade_be":
            answer_text = "🛡️ Break-Even vermerkt! Stopp liegt auf Einstieg."
        elif data == "trade_manual":
            self.waiting_for_close_price[chat_id] = True
            answer_text = "Bitte antworte jetzt im Chat mit deinem geschlossenen Exit-Preis."
        elif data == "show_stats":
            self.send_stats_report(chat_id)

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                      json={"callback_query_id": query_id, "text": answer_text})

    def send_stats_report(self, chat_id, title="📊 *Titan AI Tagesjournal*"):
        stats_msg = (
            f"{title}\n\n"
            f"• Geöffnete Trades: `{self.journal['geöffnet']}`\n"
            f"• Wins: `{self.journal['wins']}` | Losses: `{self.journal['losses']}`\n"
            f"• Netto Pips / Punkte: `{self.journal['total_pips']:.1f}`"
        )
        self.send_plain_message(stats_msg, chat_id)

    def listen(self):
        print("Titan AI Polling Loop gestartet...")
        while True:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
                res = requests.get(url, timeout=15).json()
               
                if res.get("ok") and res.get("result"):
                    for update in res["result"]:
                        self.last_update_id = update["update_id"]
                       
                        if "callback_query" in update:
                            print("Callback Query empfangen!")
                            self.handle_callback(update["callback_query"])
                            continue

                        msg = update.get("message") or update.get("channel_post") or {}
                        chat_id = msg.get("chat", {}).get("id")
                        text_cmd = msg.get("text", "").strip().lower()
                       
                        if not chat_id:
                            continue
                       
                        self.last_active_chat_id = chat_id
                        print(f"Nachricht empfangen von Chat {chat_id}: '{text_cmd}'")

                        if text_cmd in ["/start", "hallo", "hi", "start"]:
                            self.send_persistent_menu(str(chat_id))
                            continue

                        if chat_id in self.waiting_for_close_price and self.waiting_for_close_price[chat_id]:
                            try:
                                close_price = float(text_cmd.replace(",", "."))
                                self.waiting_for_close_price[chat_id] = False
                                self.journal["wins"] += 1
                                self.journal["total_pips"] += 10.0
                                self.send_plain_message(f"✅ Manueller Exit bei `{close_price}` erfasst!", str(chat_id))
                            except ValueError:
                                self.send_plain_message("⚠️ Bitte gib eine gültige Zahl ein (z.B. 2650.50).", str(chat_id))
                            continue

                        if text_cmd in ["/signal", "15m"]:
                            print("15m Signal wird verarbeitet...")
                            setup = self.analyze_market("15m")
                            self.send_message_with_buttons(setup, str(chat_id))
                        elif text_cmd in ["/scalp", "5m"]:
                            print("5m Scalp wird verarbeitet...")
                            setup = self.analyze_market("5m")
                            self.send_message_with_buttons(setup, str(chat_id))

            except Exception as e:
                print(f"Fehler in Polling Loop: {e}")
            time.sleep(2)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask Keep-Alive Server läuft im Hintergrund...")

    TitanAI_Analyst().listen()
   
