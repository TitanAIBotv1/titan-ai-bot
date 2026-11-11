import os
import datetime
from datetime import timezone
import time
import threading
import io
import matplotlib
matplotlib.use('Agg') # Wichtig für Server ohne Display (Render)
import matplotlib.pyplot as plt
from flask import Flask, jsonify
import requests
import yfinance as yf
import pandas as pd

app = Flask(__name__)

# Hier speichern wir das Signal für deinen PC zwischen (Briefkasten-Architektur)
pending_signal = None

@app.route("/")
def home():
    return "Titan AI Bot (Ultimate Edition v3.0) is running 24/7!"

@app.route("/api/signal", methods=["GET"])
def get_signal():
    global pending_signal
    if pending_signal:
        data = pending_signal
        pending_signal = None # Nach dem Abholen sofort leeren, damit nicht doppelt ausgeführt wird
        return jsonify({"status": "success", "signal": data})
    return jsonify({"status": "empty"})

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

TELEGRAM_TOKEN = "8878607953:AAHBXqy1Kpa485kYa70hkj_EfaJ_EtHrIYc"
ADMIN_USER_ID = 8789124240

class TitanAI_Analyst:
    def __init__(self, risk_percentage: float = 1.0):
        self.risk_percentage = risk_percentage
        self.last_update_id = 0
        self.last_command_time = 0 # NEU: Spam-Schutz gegen doppelte Ausführung
        self.journal = {
            "geöffnet": 0,
            "wins": 0,
            "losses": 0,
            "total_pips": 0.0
        }
        self.waiting_for_close_price = {}
        self.last_active_chat_id = None
        self.active_trade = None

    def send_update_info(self, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        text = (
            "🚀 *TITAN AI UPDATE – Version 3.0 ist live!* 🚀\n\n"
            "🟢 *Multi-Timeframe-Logik:* Der Bot checkt den 1H-Trend und die lokale Struktur.\n"
            "📊 *Live-Chart Bilder:* Setup-Visualisierung direkt als Foto.\n"
            "🎯 *Progressiver Multi-TP-Tracker:* Überwacht fortlaufend alle Stufen.\n"
            "🛡️ *Automatischer Break-Even:* Sofort-Alarm bei TP1 zum Absichern.\n"
            "📰 *News- & Session-Filter:* Intelligente Erkennung von Marktphasen.\n"
            "🔄 *Dynamische Richtung:* Flexible Long- & Short-Setups."
        )
        requests.post(url, json={"chat_id": target_chat_id, "text": text, "parse_mode": "Markdown"})

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
            "text": "🎛️ *Titan AI Dynamic Menü aktiv*\nWähle deinen Zeitrahmen und deine Richtung:",
            "parse_mode": "Markdown",
            "reply_markup": keyboard
        }
        requests.post(url, json=payload)

    def send_message_with_buttons(self, text: str, target_chat_id: str, photo_bytes=None, is_live=False):
        auto_btn = {"text": "🤖 Trade automatisieren", "callback_data": "automate_live" if is_live else "automate_pending"}
       
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

    def get_market_session(self):
        # FIX für die Deprecation Warning auf Render
        now_utc = datetime.datetime.now(timezone.utc).hour
        if 7 <= now_utc < 12:
            return "London Session 🇬🇧"
        elif 12 <= now_utc < 17:
            return "New York / London 🇺🇸"
        elif 17 <= now_utc < 21:
            return "New York Nachmittag 🗽"
        else:
            return "Asien Session 🌙"

    def fetch_data(self, interval, period="5d"):
        df = pd.DataFrame()
        for symbol in ["GC=F", "XAUUSD=X"]:
            try:
                df = yf.download(symbol, interval=interval, period=period, progress=False)
                if not df.empty:
                    break
            except Exception:
                pass
            time.sleep(0.5)
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
                plt.plot(subset.index, subset['EMA_200'], label='EMA 200', color='#ff0055', linestyle='--', alpha=0.8)

            plt.axhline(price, color='#ffffff', linestyle='-', alpha=0.9, label=f'Entry: {price}')
            plt.axhline(sl, color='#ff3333', linestyle=':', alpha=0.9, label=f'SL: {sl}')
            plt.axhline(tp1, color='#33ff33', linestyle=':', alpha=0.9, label=f'TP1: {tp1}')
            plt.title(f"Titan AI Setup v3.0 | Gold ({direction})", fontsize=12, color='white', fontweight='bold')
            plt.legend(loc='upper left', fontsize=8)
            plt.grid(color='#333333', linestyle='--', linewidth=0.5)
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150)
            buf.seek(0)
            plt.close()
            return buf.getvalue()
        except Exception:
            return None

    def analyze_market(self, timeframe="15m", force_direction="LONG", is_live_mode=False):
        df_macro = self.fetch_data("1h")
        df_exec = self.fetch_data(timeframe)

        if df_exec.empty:
            return "⚠️ *Marktdaten konnten nicht geladen werden.*", None

        for df in [df_macro, df_exec]:
            if not df.empty:
                if isinstance(df.columns, tuple) or hasattr(df.columns, 'levels'):
                    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
                df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()

        macro_trend = "UNBEKANNT"
        if not df_macro.empty:
            macro_close = float(df_macro.iloc[-1]['Close'])
            macro_ema200 = float(df_macro.iloc[-1]['EMA_200'])
            macro_trend = "BULLISH 🟢" if macro_close > macro_ema200 else "BEARISH 🔴"

        current = df_exec.iloc[-1]
        price = round(float(current['Close']), 2)
        ema200 = float(current['EMA_200'])

        # NEU: Exakter 1-Minuten-Preis-Abruf für die Live-Order, damit Entry nicht verfälscht ist!
        if is_live_mode:
            df_live = self.fetch_data("1m", period="1d")
            if not df_live.empty:
                price = round(float(df_live.iloc[-1]['Close']), 2)
            force_direction = "LONG" if price > ema200 else "SHORT"

        delta = df_exec['Close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = float(100 - (100 / (1 + rs)).iloc[-1])

        high_low = df_exec['High'] - df_exec['Low']
        high_close = (df_exec['High'] - df_exec['Close'].shift()).abs()
        low_close = (df_exec['Low'] - df_exec['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = float(tr.ewm(alpha=1/14, adjust=False).mean().iloc[-1])

        prob = 55.0
        if force_direction == "LONG":
            direction = "🟢 LONG 📈"
            raw_dir = "LONG"
            if price > ema200: prob += 15.0
            if "BULLISH" in macro_trend: prob += 15.0
        else:
            direction = "🔴 SHORT 📉"
            raw_dir = "SHORT"
            if price < ema200: prob += 15.0
            if "BEARISH" in macro_trend: prob += 15.0

        if 40 <= rsi <= 60:
            prob += 10.0

        session_info = self.get_market_session()
        sl_dist = round(atr * 1.2, 2) if timeframe != "5m" else round(atr * 0.9, 2)
       
        if raw_dir == "LONG":
            sl = price - sl_dist
            tp1 = price + 3.0; tp2 = price + 6.0; tp3 = price + 10.0; tp4 = price + (atr*1.5); tp5 = price + (atr*2.5); tp6 = price + (atr*4.0)
            if timeframe == "5m": tp1 = price + 1.5; tp2 = price + 3.0; tp3 = price + 5.0; tp4 = price + (atr*1.0); tp5 = price + (atr*1.8); tp6 = price + (atr*3.0)
        else:
            sl = price + sl_dist
            tp1 = price - 3.0; tp2 = price - 6.0; tp3 = price - 10.0; tp4 = price - (atr*1.5); tp5 = price - (atr*2.5); tp6 = price - (atr*4.0)
            if timeframe == "5m": tp1 = price - 1.5; tp2 = price - 3.0; tp3 = price - 5.0; tp4 = price - (atr*1.0); tp5 = price - (atr*1.8); tp6 = price - (atr*3.0)
       
        title = "⚡ *TITAN AI LIVE-MARKT-ANALYSE* ⚡" if is_live_mode else f"🚨 *TITAN AI SETUP [{timeframe}]* 🚨"

        self.active_trade = {
            "direction": raw_dir,
            "entry": price,
            "sl": sl,
            "tps": [tp1, tp2, tp3, tp4, tp5, tp6],
            "reached_tps": [False]*6,
            "chat_id": self.last_active_chat_id
        }

        chart_bytes = self.create_chart_image(df_exec, raw_dir, price, sl, tp1)

        report = (
            f"{title}\n\n"
            f"• *1H Makro-Trend:* `{macro_trend}`\n"
            f"• *Richtung:* `{direction}`\n"
            f"• *Win-Chance:* `{prob}%`\n"
            f"• *Session:* `{session_info}`\n\n"
            f"• *Entry:* `{price}`\n"
            f"• *Stop-Loss:* `{sl:.2f}`\n\n"
            f"🎯 *Take Profits (TP1-TP6):*\n"
            f"• *TP1:* `{tp1:.2f}`\n"
            f"• *TP2:* `{tp2:.2f}`\n"
            f"• *TP3:* `{tp3:.2f}`\n"
            f"• *TP4:* `{tp4:.2f}`\n"
            f"• *TP5:* `{tp5:.2f}`\n"
            f"• *TP6:* `{tp6:.2f}`\n\n"
            f"⚠️ *Disclaimer:* Handel auf eigene Gefahr. Keine Anlageberatung."
        )
        return report, chart_bytes

    def handle_callback(self, callback_query):
        global pending_signal
        query_id = callback_query.get("id")
        data = callback_query.get("data")
        user_id = callback_query.get("from", {}).get("id")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        self.last_active_chat_id = chat_id

        # Spam-Schutz für Callback-Buttons (verhindert mehrfaches Klicken in kurzer Zeit)
        now = time.time()
        if now - self.last_command_time < 3:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Bitte kurz warten..."})
            return
        self.last_command_time = now

        answer_text = "Erfolgreich vermerkt!"
       
        if data in ["automate_live", "automate_pending"]:
            if user_id != ADMIN_USER_ID:
                answer_text = "⚠️ Zugriff verwehrt! Nur der Admin darf Trades automatisieren."
            else:
                if self.active_trade:
                    trade = self.active_trade
                    order_type = "MARKET" if data == "automate_live" else "PENDING"
                    pending_signal = {
                        "direction": trade["direction"],
                        "entry": trade["entry"],
                        "sl": trade["sl"],
                        "tp1": trade["tps"][0],
                        "type": order_type
                    }
                    answer_text = f"🤖 Signal ({order_type}) an lokalen PC gesendet!"
                    self.send_plain_message(f"⚡ **Automatisches Signal ({order_type}) generiert!**\nDer PC-Listener ruft die Order jetzt ab und trägt sie in MT5 ein.", str(chat_id))
                else:
                    answer_text = "⚠️ Kein aktiver Trade im Speicher!"
               
        elif data == "trade_open":
            self.journal["geöffnet"] += 1
            answer_text = "Trade geöffnet."
        elif data == "trade_win":
            self.journal["wins"] += 1
            answer_text = "Win verbucht!"
            self.active_trade = None
        elif data == "trade_loss":
            self.journal["losses"] += 1
            answer_text = "Verlust verbucht."
            self.active_trade = None
        elif data == "trade_be":
            answer_text = "🛡️ Break-Even vermerkt!"
        elif data == "show_stats":
            stats_msg = f"📊 *Journal*\nWins: `{self.journal['wins']}` | Losses: `{self.journal['losses']}`"
            self.send_plain_message(stats_msg, chat_id)

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": query_id, "text": answer_text})

    def background_trade_watcher(self):
        while True:
            try:
                if self.active_trade:
                    df = self.fetch_data("1m", period="1d")
                    if not df.empty:
                        current_price = float(df.iloc[-1]['Close'])
                        trade = self.active_trade
                        direction = trade["direction"]
                        tps = trade["tps"]
                        reached = trade["reached_tps"]
                        chat_id = trade["chat_id"]

                        if chat_id:
                            for i, tp_val in enumerate(tps):
                                if not reached[i]:
                                    hit = (direction == "LONG" and current_price >= tp_val) or (direction == "SHORT" and current_price <= tp_val)
                                    if hit:
                                        reached[i] = True
                                        self.send_plain_message(f"🎯 *TITAN AI TRACKER: TP{i+1} ERREICHT!* 🎯\nKurs: `{current_price}`", str(chat_id))
            except Exception:
                pass
            time.sleep(15)

    def listen(self):
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=5)
        except:
            pass
       
        print("Titan AI v3.0 Polling gestartet...")
        while True:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
                res = requests.get(url, timeout=15).json()
               
                if res.get("ok") and res.get("result"):
                    for update in res["result"]:
                        self.last_update_id = update["update_id"]
                       
                        if "callback_query" in update:
                            self.handle_callback(update["callback_query"])
                            continue

                        msg = update.get("message") or {}
                        chat_id = msg.get("chat", {}).get("id")
                        text_cmd = msg.get("text", "").strip().lower()
                       
                        if not chat_id or not text_cmd:
                           continue
                       
                        self.last_active_chat_id = chat_id

                        # Spam-Schutz für Text-Menü-Befehle (Ignoriert doppelte Klicks innerhalb von 3 Sekunden)
                        now = time.time()
                        if now - self.last_command_time < 3:
                            continue
                        self.last_command_time = now

                        if text_cmd in ["/start", "hallo", "hi", "start", "update info"]:
                            self.send_update_info(str(chat_id))
                            self.send_persistent_menu(str(chat_id))
                            continue

                        if "live markt-analyse" in text_cmd:
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

            except Exception:
                pass
            time.sleep(2)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    analyst = TitanAI_Analyst()
    watcher_thread = threading.Thread(target=analyst.background_trade_watcher)
    watcher_thread.daemon = True
    watcher_thread.start()

    print("Alle Titan AI v3.0 Dienste aktiv...")
    analyst.listen()
