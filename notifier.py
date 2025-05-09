import requests
from config import settings
from core.logger import BotLogger

logger = BotLogger()

def send_notification(message: str) -> dict:
    """
    Send a notification via Telegram.
    Falls back to logging if token/chat_id missing.
    """
    token = settings.TELEGRAM_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not (token and chat_id):
        logger.warning("Telegram ayarları eksik. Bildirim gönderilemedi.")
        return {}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:
        resp = requests.post(url, data=payload, timeout=5)
        if resp.status_code != 200:
            logger.error(f"Telegram bildirim hatası: HTTP {resp.status_code} – {resp.text}")
        return resp.json()
    except Exception as e:
        logger.error(f"Notifier hatası: {e}")
        return {}
