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


TELEGRAM_TOKEN = "8878607953:AAGkBw5ENjKg27oewJI_IgtEzxu2giGav2s"

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
        requests.post(url, json=payload)

    def send_message_with_buttons(self, text: str, target_chat_id: str):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Trade geöffnet", "callback_data": "trade_open"},
                {"text": "🎯 TP / Win erreicht", "callback_data": "trade_win"}
            ],
            [
                {"text": "🛡️ Break Even gezogen", "callback_data": "trade_be"}
            ],
            [
                {"text": "❌ Stop-Loss / Loss", "callback_data": "trade_loss"},
                {"text": "✍️ Manuell geschlossen", "callback_data": "trade_manual"}
            ],
            [
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
    requests.post(url, json=payload)

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
            for _ in range(2):
                try:
                    df = yf.download(symbol, interval=interval, period="5d", progress=False)
                    if not df.empty:
                        break
                except Exception:
                    pass
                time.sleep(1)
            if not df.empty:
                break
        return df

    def analyze_market(self, timeframe="15m"):
        df = self.fetch_data(timeframe)
        if df.empty: 
            return None

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
        
        current = df.iloc[-2]
        
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
            f"⚖️ *Disclaimer:* Dies ist eine rein algorithmische Marktanalyse und keine Anlageberatung oder Handelsempfehlung."
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
        elif data == "trade_manual":
            self.waiting_for_close_price[chat_id] = True
            answer_text = "Bitte antworte jetzt im Chat mit deinem geschlossenen Exit-Preis (z.B. 4102.50)."
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
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": chat_id, "text": stats_msg, "parse_mode": "Markdown"})

    def check_xauusd_milestones(self, current_price, trade):
        # 1. Warnung kurz vor TP1 (bei 95% des Weges)
        distance_to_tp1 = trade["tp1"] - trade["entry_price"]
        current_progress = current_price - trade["entry_price"]

        if not trade.get("be_warned", False) and current_progress >= (distance_to_tp1 * 0.95):
            self.send_telegram_message(
                f"⚠️ **XAUUSD (Gold) - TP1 steht kurz bevor!** Kurs ist bei {current_price}. Bitte ziehe deinen Stop-Loss jetzt auf **Break-Even**!"
            )
            trade["be_warned"] = True

        # 2. Prüfen, ob TP1 gehittet wurde
        if not trade.get("tp1_hit", False) and current_price >= trade["tp1"]:
            self.send_telegram_message(
                f"🎯 **XAUUSD: TP1 erfolgreich gehittet!** Kurs hat {trade['tp1']} erreicht. Siehe bitte Break-Even."
            )
            trade["tp1_hit"] = True

        # 3. Prüfen, ob TP2 gehittet wurde
        if not trade.get("tp2_hit", False) and current_price >= trade["tp2"]:
            self.send_telegram_message(
                f"🚀 **XAUUSD: TP2 erfolgreich gehittet!** Kurs hat {trade['tp2']} erreicht."
            )
            trade["tp2_hit"] = True

        # 4. Prüfen, ob Golden Profit gehittet wurde
        if not trade.get("golden_hit", False) and current_price >= trade["golden_profit"]:
            self.send_telegram_message(
                f"🏆 **XAUUSD: GOLDEN PROFIT ERREICHT!** Unglaubliche Performance bei {trade['golden_profit']}!"
            )
            trade["golden_hit"] = True

    def listen(self):
        print("Titan AI (inkl. automatischer Update-Nachricht) gestartet...")
        
        # Optional: Falls du eine feste Chat-ID hast, in die die Update-Info direkt beim Start gehen soll,
        # kannst du sie hier eintragen (z.B. self.last_active_chat_id = "DEINE_CHAT_ID").
        # Ansonsten wartet er kurz, bis der erste Befehl reinkommt, oder schickt es an den letzten aktiven Chat.
        
        startup_notified = False

        while True:
            try:
                now = datetime.datetime.utcnow()
                current_week = now.isocalendar()[1]

                # Automatische Update-Info beim ersten aktiven Chat senden nach dem Start
                if not startup_notified and self.last_active_chat_id:
                    update_announcement = (
                        "🚀 *TITAN AI – UPDATE ONLINE!* 🚀\n\n"
                        "Moin Leute! Es wurde soeben ein neues, fettes Update eingespielt:\n"
                        "• ✨ **Trend-Status integriert** (Direkte Anzeige, ob der Kurs über/unter dem EMA läuft)\n"
                        "• 🎛️ **Permanentes Steuerungs-Menü** unten im Chat\n"
                        "• 📊 **Optimiertes Journal & Wochenrückblick** (Freitags 18 Uhr)\n\n"
                        "Tippt einfach einmal auf **`/start`** unten im Chat, um die neuen Steuerungs-Buttons zu aktivieren und loszulegen!"
                    )
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                  json={"chat_id": self.last_active_chat_id, "text": update_announcement, "parse_mode": "Markdown"})
                    startup_notified = True

                if now.hour >= 22 and self.journal["last_summary_date"] != now.day and self.journal["geöffnet"] > 0:
                    self.journal["last_summary_date"] = now.day
                    if self.last_active_chat_id:
                        print("22 Uhr erreicht: Sende automatischen Tagesabschluss...")
                        self.send_stats_report(self.last_active_chat_id, title="🌙 *Titan AI Tagesabschluss (22 Uhr)*")

                if now.weekday() == 4 and now.hour >= 18 and self.journal["last_weekly_week"] != current_week:
                    self.journal["last_weekly_week"] = current_week
                    if self.last_active_chat_id:
                        print("Freitag 18 Uhr erreicht: Sende Wochenrückblick...")
                        self.send_stats_report(self.last_active_chat_id, title="🏁 *Titan AI Wochenrückblick (Freitag 18 Uhr)*")

                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={self.last_update_id + 1}&timeout=30"
                res = requests.get(url).json()
                
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

                        if text_cmd in ["/start", "hallo", "hi"]:
                            self.send_persistent_menu(str(chat_id))
                            continue

                        if chat_id in self.waiting_for_close_price and self.waiting_for_close_price[chat_id]:
                            try:
                                close_price = float(text_cmd.replace(",", "."))
                                self.waiting_for_close_price[chat_id] = False
                                
                                self.journal["wins"] += 1
                                self.journal["total_pips"] += 10.0
                                
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                              json={"chat_id": chat_id, "text": f"✅ Manueller Exit bei `{close_price}` erfasst und ins Journal geschrieben!", "parse_mode": "Markdown"})
                            except ValueError:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                              json={"chat_id": chat_id, "text": "⚠️ Bitte gib eine gültige Zahl als Preis ein (z.B. 4102.50)."})
                            continue

                        if text_cmd in ["/signal", "15m"]:
                            print("15m Signal angefordert...")
                            setup = self.analyze_market("15m")
                            if setup:
                                self.send_message_with_buttons(setup, str(chat_id))
                        elif text_cmd in ["/scalp", "5m"]:
                            print("5m Scalp angefordert...")
                            setup = self.analyze_market("5m")
                            if setup:
                                self.send_message_with_buttons(setup, str(chat_id))
            except Exception as e:
                pass
            time.sleep(2)


if __name__ == "__main__":
  # Startet den Webserver im Hintergrund für Render
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()
  print("Flask Keep-Alive Server läuft im Hintergrund...")

  # Startet deinen Bot
  TitanAI_Analyst().listen()
    
