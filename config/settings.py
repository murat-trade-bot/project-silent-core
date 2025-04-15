import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- API Anahtarları ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Anahtar eksikse uyarı loglanabilir (gelişmiş hata kontrolü için öneri)
if not NEWS_API_KEY:
    print("[WARN] NEWS_API_KEY boş! .env dosyasına geçerli anahtar girilmelidir.")

# --- Bot Modları ---
TESTNET_MODE = True
PAPER_TRADING = True
SYMBOL = "BTCUSDT"

# --- Döngü Ayarları ---
CYCLE_INTERVAL = 60
CYCLE_JITTER_MIN = -20
CYCLE_JITTER_MAX = 20

# --- Stealth (Gizlenme) Ayarları ---
STEALTH_DROP_CHANCE = 0.1
STEALTH_SLEEP_CHANCE = 0.05
STEALTH_SLEEP_MIN = 10
STEALTH_SLEEP_MAX = 30
STEALTH_ORDER_SIZE_JITTER = 0.05

# --- Kar/Zarar Yönetimi ---
TAKE_PROFIT_RATIO = 0.02
STOP_LOSS_RATIO = 0.005

# --- ATR StopLoss ---
USE_ATR_STOPLOSS = True
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.2

# --- Pozisyon Boyutu ---
POSITION_SIZE_PCT = 0.005

# --- Loglama ---
INITIAL_BALANCE = 10000.0
CSV_LOG_FILE = "trades_history.csv"
LOG_FILE = "bot_logs.txt"

# --- Retry Mekanizması ---
MAX_RETRIES = 3
RETRY_WAIT_TIME = 10

# --- Opsiyonel Modüller ---
ENABLE_PERFORMANCE_ANALYZER = True
ENABLE_AUTO_STRATEGY_OPTIMIZER = True
NOTIFIER_ENABLED = True
ANTI_BINANCE_TESPIT_ENABLED = True

# --- Proxy Ayarları ---
USE_PROXY = False
PROXY_LIST_PATH = "proxy_list.txt"
API_TIMEOUT = 10
PROXY_TIMEOUT = 15
