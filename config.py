import os

class Settings:
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    TESTNET_MODE = os.getenv("TESTNET_MODE", "False") == "True"
    NOTIFIER_ENABLED = os.getenv("NOTIFIER_ENABLED", "False") == "True"
    LOG_FILE = os.getenv("LOG_FILE", "bot.log")  # <-- Eksik olan satır eklendi

settings = Settings()

BAŞLANGIÇ_SERMEYESİ = 252.0
IŞLEM_MIKTARI = 20.0
TRADE_INTERVAL = 30
MIN_BAKIYE = 10.0
STOP_LOSS_RATIO = float(os.getenv("STOP_LOSS_RATIO", "0.05"))
TAKE_PROFIT_RATIO = float(os.getenv("TAKE_PROFIT_RATIO", "0.10"))
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.001"))  # Komisyon oranı (varsayılan 0.1%)
LIMIT_ORDER_RATIO = float(os.getenv("LIMIT_ORDER_RATIO", "0.7"))  # Limit dilimleme yöntemi olasılığı

# ...diğer ayar ve sabitler...