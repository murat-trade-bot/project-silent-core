import requests
from config import settings
from core.logger import BotLogger

logger = BotLogger()

def send_notification(message: str) -> dict:
    """
    Send a notification via Telegram.
    Falls back to logging if token/chat_id missing.
    """
    try:
        token = getattr(settings, "TELEGRAM_TOKEN", None)
        if not token:
            return  # Token yoksa sessizce çık

        chat_id = settings.TELEGRAM_CHAT_ID

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
        }

        resp = requests.post(url, data=payload, timeout=5)
        if resp.status_code != 200:
            logger.error(f"Telegram bildirim hatası: HTTP {resp.status_code} – {resp.text}")
        return resp.json()
    except Exception as e:
        logger.error(f"Notifier hatası: {e}")
        return {}
        return {}
