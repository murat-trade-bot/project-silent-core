import requests
from config import settings

def send_notification(message):
    token = settings.TELEGRAM_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        try:
            response = requests.post(url, data=data, timeout=5)
            return response.json()
        except Exception as e:
            print(f"Notifier Hatası: {e}")
            return None
    else:
        print("Telegram ayarları eksik.")
        return None 