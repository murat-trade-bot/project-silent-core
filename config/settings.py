import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# --- Spot İşlemler ---
# Birden fazla sembolü listelemek için:
SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT").split(",")

# --- API Anahtarları ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Bot Çalışma Parametreleri ---
# Her sembol döngü arası bekleme (sn)
CYCLE_INTERVAL = 10
CYCLE_JITTER_MIN = 0
CYCLE_JITTER_MAX = 5

# Stealth modu parametreleri
STEALTH_DROP_CHANCE = 0.02
STEALTH_SLEEP_CHANCE = 0.0  # Uyutmayı devre dışı bıraktık
STEALTH_SLEEP_MIN = 0
STEALTH_SLEEP_MAX = 0
STEALTH_ORDER_SIZE_JITTER = 0.01

# Rate‑limit ve retry
MAX_RETRIES = 5
RETRY_WAIT_TIME = 5

# --- İşlem Hacmi & Frekans ---
MAX_TRADES_PER_HOUR = 20
MIN_INTERVAL_BETWEEN_TRADES = 60  # saniye

# --- Hedef & Raporlama ---
TARGET_USDT = 3580122
PHASES = 6

# --- Log & Kayıt ---
LOG_FILE = "bot_logs.txt"
CSV_LOG_FILE = "trades_history.csv"

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
