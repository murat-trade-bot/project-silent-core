import os
from dotenv import load_dotenv
from binance.client import Client

def start_bot() -> bool:
    load_dotenv()
    api_key    = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
    print("Bot Başlatıldı")
    return True

if __name__ == "__main__":
    start_bot()





