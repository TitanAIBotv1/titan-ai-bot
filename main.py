import os
import time
import requests

class TitanAI_Analyst:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        print(f"Bot initialisiert mit Chat-ID: {self.chat_id}")

    def send_message(self, text, chat_id=None):
        target = chat_id or self.chat_id
        if not target or not self.token:
            print("Fehler: TELEGRAM_TOKEN oder TELEGRAM_CHAT_ID fehlt!")
            return
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Fehler beim Senden der Nachricht: {e}")

    def send_message_with_buttons(self, text, chat_id=None):
        target = chat_id or self.chat_id
        if not target or not self.token:
            print("Fehler: TELEGRAM_TOKEN oder TELEGRAM_CHAT_ID fehlt!")
            return
        url = f"{self.api_url}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📊 Analyse", "callback_data": "analyse"},
                    {"text": "⚡ Signal", "callback_data": "signal"}
                ]
            ]
        }
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        try:
            res = requests.post(url, json=payload, timeout=10)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Fehler beim Senden der Buttons: {e}")

    def analyze_market(self):
        return (
            "📈 <b>XAU/USD Markt-Analyse</b>\n\n"
            "• <b>Trend:</b> Bullisch\n"
            "• <b>Support:</b> 2650.00\n"
            "• <b>Resistance:</b> 2685.00\n\n"
            "💡 <i>Titan AI Signal: Buy Signal bestätigt auf H1 TF.</i>"
        )

    def handle_updates(self):
        url = f"{self.api_url}/getUpdates"
        params = {"offset": self.offset, "timeout": 5}
        try:
            res = requests.get(url, params=params, timeout=10)
            if res.status_code != 200:
                print(f"getUpdates Status: {res.status_code}")
                return
            data = res.json()
            if not data.get("ok"):
                return
            
            for update in data.get("result", []):
                self.offset = update["update_id"] + 1
                
                # Befehle auswerten
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "").strip()
                    
                    if text in ["/start", "/help"]:
                        welcome = (
                            "👋 <b>Willkommen beim Titan AI Bot!</b>\n\n"
                            "Befehle:\n"
                            "• <code>/analyse</code> - Aktuelle Marktanalyse anfordern\n"
                            "• <code>/signal</code> - Signal mit Buttons senden"
                        )
                        self.send_message(welcome, chat_id)
                    elif text == "/analyse":
                        report = self.analyze_market()
                        self.send_message(report, chat_id)
                    elif text == "/signal":
                        report = self.analyze_market()
                        self.send_message_with_buttons(report, chat_id)

                # Button-Klicks auswerten
                elif "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb["id"]
                    chat_id = cb["message"]["chat"]["id"]
                    cb_data = cb.get("data")
                    
                    requests.post(f"{self.api_url}/answerCallbackQuery", json={"callback_query_id": cb_id})
                    
                    if cb_data == "analyse":
                        report = self.analyze_market()
                        self.send_message(report, chat_id)
                    elif cb_data == "signal":
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

