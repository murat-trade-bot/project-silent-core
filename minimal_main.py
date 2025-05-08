import os
from dotenv import load_dotenv
from binance.client import Client
from minimal_strategy import Strategy

def start_bot() -> bool:
    """
    Botu başlatır:
      1. .env'den API anahtarlarını okur
      2. Binance Client'ı oluşturur
      3. Konsola 'Bot Başlatıldı' yazar
      4. Strategy stub'unu çağırıp aksiyonu yazar
    """
    load_dotenv()
    api_key    = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)

    # Başlatma mesajı
    print("Bot Başlatıldı")
    # Strategy stub'u ile aksiyon al ve yazdır
    action = Strategy().get_action({})
    print(f"Aksiyon: {action}")

    return True

if __name__ == "__main__":
    start_bot()
