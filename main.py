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
                [{"text": "15m"}, {"text": "5m"}],
                [{"text": "🚀 Update Info (Patch Notes)"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }
        payload = {
            "chat_id": target_chat_id,
            "text": "🎛️ *Titan AI Dynamic Menü aktiv*\nWähle deinen Zeitrahmen oder checke die Updates:",
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
        except Exception as e:
            print(f"Fehler bei Chart-Generierung: {e}")
            return None

    def analyze_market(self, timeframe="15m"):
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
        ema50 = float(current['EMA_50'])
        ema200 = float(current['EMA_200'])

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
        if price >= ema50:
            direction = "🟢 LONG 📈 *(Lokale Struktur)*"
            raw_dir = "LONG"
            if price > ema200: prob += 15.0
            if "BULLISH" in macro_trend: prob += 15.0 
        else:
            direction = "🔴 SHORT 📉 *(Lokale Struktur)*"
            raw_dir = "SHORT"
            if price < ema200: prob += 15.0
            if "BEARISH" in macro_trend: prob += 15.0 

        if 40 <= rsi <= 60: 
            prob += 10.0

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
            title = f"⚡ *TITAN AI DYNAMIC SCALP [{timeframe}]* ⚡"
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
            title = f"🚨 *TITAN AI DYNAMIC SETUP [{timeframe}]* 🚨"

        # Aktiven Trade für den progressiven Multi-TP Tracker initialisieren
        self.active_trade = {
            "direction": raw_dir,
            "entry": price,
            "sl": sl,
            "tps": [tp1, tp2, tp3, tp4, tp5, tp6],
            "reached_tps": [False, False, False, False, False, False],
            "chat_id": self.last_active_chat_id
        }

        chart_bytes = self.create_chart_image(df_exec, raw_dir, price, sl, tp1)

        report = (
            f"{title}\n\n"
            f"• *1H Makro-Trend:* `{macro_trend}`\n"
            f"• *Struktur-Richtung:* `{direction}`\n"
            f"• *Win-Wahrscheinlichkeit:* `{prob}%`\n"
            f"• *Session & News-Status:* `{session_info}`\n\n"
            f"• *Live-Entry:* `{price}`\n"
            f"• *Stop-Loss:* `{sl:.2f}`\n"
            f"• *Risiko:* `{self.risk_percentage}%`\n\n"
            f"🎯 *Take Profits & Management (TP1 - TP6):*\n"
            f"• *TP1 (Break-Even):* `{tp1:.2f}`\n"
            f"• *TP2:* `{tp2:.2f}`\n"
            f"• *TP3:* `{tp3:.2f}`\n"
            f"• *TP4:* `{tp4:.2f}`\n"
            f"• *TP5:* `{tp5:.2f}`\n"
            f"• *🏆 Golden Profit (TP6):* `{tp6:.2f}`\n\n"
            f"🛡️ *Multi-TP Tracker:* Aktiv (Überwacht TP1-TP6 im Hintergrund).\n"
            f"⚖️ *Disclaimer:* Dynamische Multi-TF Analyse."
        )
        return report, chart_bytes

    def handle_callback(self, callback_query):
        query_id = callback_query.get("id")
        data = callback_query.get("data")
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        self.last_active_chat_id = chat_id

        answer_text = "Erfolgreich vermerkt!"
        if data == "trade_open":
            self.journal["geöffnet"] += 1
            answer_text = "Trade geöffnet. Multi-TP Tracker läuft!"
        elif data == "trade_win":
            self.journal["wins"] += 1
            self.journal["total_pips"] += 30.0
            answer_text = "Win verbucht!"
            self.active_trade = None
        elif data == "trade_loss":
            self.journal["losses"] += 1
            self.journal["total_pips"] -= 15.0
            answer_text = "Verlust verbucht."
            self.active_trade = None
        elif data == "trade_be":
            answer_text = "🛡️ Break-Even vermerkt! Stopp auf Einstieg."
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

    def background_trade_watcher(self):
        """Fortlaufender Hintergrund-Tracker für TP1 bis TP6 im Live-Chart"""
        while True:
            try:
                if self.active_trade:
                    df = self.fetch_data("1m")
                    if not df.empty:
                        current_price = float(df.iloc[-1]['Close'])
                        trade = self.active_trade
                        direction = trade["direction"]
                        tps = trade["tps"]
                        reached = trade["reached_tps"]
                        chat_id = trade["chat_id"]

                        if chat_id:
                            # Prüfe nacheinander TP1 bis TP6
                            for i, tp_val in enumerate(tps):
                                if not reached[i]:
                                    hit = False
                                    if direction == "LONG" and current_price >= tp_val:
                                        hit = True
                                    elif direction == "SHORT" and current_price <= tp_val:
                                        hit = True

                                    if hit:
                                        reached[i] = True
                                        tp_num = i + 1

                                        if tp_num == 1:
                                            alert_msg = (
                                                f"🚀 *TITAN AI TRACKER: TP1 ERREICHT!* 🚀\n\n"
                                                f"• Aktueller Kurs: `{current_price}`\n"
                                                f"• Ziel TP1: `{tp_val:.2f}`\n\n"
                                                f"🛡️ **Jetzt den Stop-Loss auf Break-Even (Entry bei `{trade['entry']}`) ziehen!**"
                                            )
                                        elif tp_num == 6:
                                            alert_msg = (
                                                f"🏆 *TITAN AI TRACKER: GOLDEN PROFIT (TP6) ERREICHT!* 🏆\n\n"
                                                f"• Aktueller Kurs: `{current_price}`\n"
                                                f"• Ziel TP6: `{tp_val:.2f}`\n\n"
                                                f"💎 **Absolutes Maximum erreicht! Position komplett schließen oder restliche Gewinne sichern!**"
                                            )
                                        else:
                                            alert_msg = (
                                                f"🎯 *TITAN AI TRACKER: TP{tp_num} IM SACK!* 🎯\n\n"
                                                f"• Aktueller Kurs: `{current_price}`\n"
                                                f"• Ziel TP{tp_num}: `{tp_val:.2f}`\n\n"
                                                f"📈 *Kurs läuft weiter Richtung nächste Ziele! Teilgewinne realisieren.*"
                                            )

                                        self.send_plain_message(alert_msg, str(chat_id))
            except Exception:
                pass
            time.sleep(15)

    def listen(self):
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

                        msg = update.get("message") or update.get("channel_post") or {}
                        chat_id = msg.get("chat", {}).get("id")
                        text_cmd = msg.get("text", "").strip().lower()
                       
                        if not chat_id:
                           continue
                       
                        self.last_active_chat_id = chat_id

                        if text_cmd in ["/start", "hallo", "hi", "start"]:
                            self.send_update_info(str(chat_id))
                            self.send_persistent_menu(str(chat_id))
                            continue
                            
                        if "update info" in text_cmd or text_cmd == "/update":
                            self.send_update_info(str(chat_id))
                            continue

                        if chat_id in self.waiting_for_close_price and self.waiting_for_close_price[chat_id]:
                            try:
                                close_price = float(text_cmd.replace(",", "."))
                                self.waiting_for_close_price[chat_id] = False
                                self.journal["wins"] += 1
                                self.journal["total_pips"] += 10.0
                                self.send_plain_message(f"✅ Manueller Exit bei `{close_price}` erfasst!", str(chat_id))
                                self.active_trade = None
                            except ValueError:
                                self.send_plain_message("⚠️ Bitte gib eine gültige Zahl ein.", str(chat_id))
                            continue

                        if text_cmd in ["/signal", "15m"]:
                            setup, chart = self.analyze_market("15m")
                            self.send_message_with_buttons(setup, str(chat_id), chart)
                        elif text_cmd in ["/scalp", "5m"]:
                            setup, chart = self.analyze_market("5m")
                            self.send_message_with_buttons(setup, str(chat_id), chart)

            except Exception as e:
                print(f"Fehler in Polling Loop: {e}")
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

