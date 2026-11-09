import os
import time
import datetime
import requests
import pandas as pd
import yfinance as yf

# Umgebungsvariablen aus Render laden
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class TitanAI_Analyst:
    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0

    def send_message(self, text, target_chat_id=None):
        if not target_chat_id:
            target_chat_id = self.chat_id
        if not target_chat_id or not self.token:
            print("Telegram Token oder Chat ID fehlt.")
            return
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Fehler beim Senden: {e}")

    def send_message_with_buttons(self, text, target_chat_id=None):
        if not target_chat_id:
            target_chat_id = self.chat_id
        if not target_chat_id or not self.token:
            print("Telegram Token oder Chat ID fehlt.")
            return

        url = f"{self.base_url}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🟢 Trade geöffnet", "callback_data": "trade_open"},
                    {"text": "🎯 TP / Win erreicht", "callback_data": "trade_win"}
                ],
                [
                    {"text": "🛡 Break Even gezogen", "callback_data": "trade_be"}
                ],
                [
                    {"text": "🔴 Stop-Loss / Loss", "callback_data": "trade_loss"},
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
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Fehler beim Senden mit Buttons: {e}")

    def get_market_session(self):
        now_utc = datetime.datetime.now(datetime.timezone.utc).hour
        if 7 <= now_utc < 12:
            return "London Session 🇬🇧"
        elif 12 <= now_utc < 17:
            return "New York / London Überschneidung 🇺🇸"
        elif 17 <= now_utc < 21:
            return "New York Nachmittag 🌆"
        else:
            return "Asien Session 🌙 (Ruhig)"

    def fetch_data(self, interval="15m"):
        df = pd.DataFrame()
        for symbol in ["GC=F", "XAUUSD=X"]:
            for _ in range(2):
                try:
                    df = yf.download(symbol, interval=interval, period="5d", progress=False)
                    if not df.empty:
                        break
                except Exception:
                    pass
            if not df.empty:
                break
        return df

    def analyze_market(self):
        df = self.fetch_data(interval="15m")
        session = self.get_market_session()
        
        if df.empty:
            return f"📊 *Titan AI Markt-Analyse*\n🌍 *Session:* {session}\n⚠️ Keine Live-Marktdaten verfügbar."

        last_price = df["Close"].iloc[-1]
        if isinstance(last_price, pd.Series):
            last_price = last_price.iloc[0]

        analysis = (
            f"📊 *Titan AI Markt-Analyse*\n"
            f"🌍 *Session:* {session}\n"
            f"💰 *Aktueller XAU/USD Kurs:* ${last_price:.2f}\n"
            f"⚡ *Status:* Bot aktiv & betriebsbereit."
        )
        return analysis

    def handle_updates(self):
        if not self.token:
            return
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 5}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    self.last_update_id = update["update_id"]

                    # Button-Klicks verarbeiten
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_data = cb.get("data")
                        cb_chat_id = cb["message"]["chat"]["id"]

                        responses = {
                            "trade_open": "🟢 Trade wurde im Journal registriert!",
                            "trade_win": "🎯 TP/Win wurde vermerkt. Glückwunsch!",
                            "trade_be": "🛡 Trade auf Break-Even gesetzt.",
                            "trade_loss": "🔴 Stop-Loss im Journal eingetragen.",
                            "trade_manual": "✍️ Manuelle Schließung vermerkt.",
                            "show_stats": "📊 *Statistik:* Trade Journal aktiv."
                        }
                        reply_text = responses.get(cb_data, "Aktion ausgeführt.")
                        self.send_message(reply_text, target_chat_id=cb_chat_id)

                    # Textnachrichten verarbeiten
                    elif "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "")

                        if text == "/start" or text == "/help":
                            welcome = (
                                "👋 *Willkommen beim Titan AI Bot!*\n\n"
                                "Befehle:\n"
                                "• `/analyse` - Aktuelle Marktanalyse anfordern\n"
                                "• `/signal` - Signal mit Interaktions-Buttons senden"
                            )
                            self.send_message(welcome,chat_id)
                        elif text == "/analyse":
                            report = self.analyze_market()
                            self.send_message(report,chat_id)
                        elif text == "/signal":
                            report = self.analyze_market()
                            self.send_message_with_buttons(report, chat_id)

        except Exception as e:
            print(f"Fehler in Polling Loop: {e}")

    def run(self):
        print("Titan AI Bot gestartet und einsatzbereit...")
        if self.chat_id:
            self.send_message_with_buttons("🚀 Titan AI Bot ist jetzt LIVE & online!", self.chat_id)

        while True:
            try:
                self.handle_updates()
            except Exception as e:
                print(f"Worker-Fehler: {e}")
            time.sleep(2)


if __name__ == "__main__":
    bot = TitanAI_Analyst()
    bot.run()
