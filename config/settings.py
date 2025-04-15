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

# --- Bot Modları ---
TESTNET_MODE = True               # Binance test ağı kullanılsın mı?
PAPER_TRADING = True              # Gerçek işlem yerine simülasyon (kağıt üzerinde işlem) yapılacak mı?
SYMBOL = "BTCUSDT"                # Varsayılan işlem çifti

# --- Döngü Ayarları ---
CYCLE_INTERVAL = 60              # Ana döngü süresi (saniye)
CYCLE_JITTER_MIN = -20           # Döngü başına minimum rastgele sapma (insan benzeri davranış için)
CYCLE_JITTER_MAX = 20            # Maksimum rastgele sapma

# --- Stealth (Gizlenme) Modu Ayarları ---
STEALTH_DROP_CHANCE = 0.1        # %10 ihtimalle isteği düşür (bot olmadığını hissettirmek için)
STEALTH_SLEEP_CHANCE = 0.05      # %5 ihtimalle uyumaya geç
STEALTH_SLEEP_MIN = 10           # Minimum uyku süresi (saniye)
STEALTH_SLEEP_MAX = 30           # Maksimum uyku süresi
STEALTH_ORDER_SIZE_JITTER = 0.05 # Emir boyutuna % jitter uygulanacak mı?

# --- Kar/Zarar Yönetimi ---
TAKE_PROFIT_RATIO = 0.02         # %2 kar hedefi
STOP_LOSS_RATIO = 0.005          # %0.5 zarar limiti

# --- ATR (Volatilite Tabanlı StopLoss) ---
USE_ATR_STOPLOSS = True
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.2

# --- Pozisyon Boyutu Ayarı ---
POSITION_SIZE_PCT = 0.005        # Bakiyenin %0.5’i ile pozisyon aç

# --- Başlangıç Bakiyesi ve Loglama ---
INITIAL_BALANCE = 10000.0
CSV_LOG_FILE = "trades_history.csv"
LOG_FILE = "bot_logs.txt"

# --- Hata Yönetimi ve Retry Mekanizması ---
MAX_RETRIES = 3
RETRY_WAIT_TIME = 10

# --- Opsiyonel Modüller (Aç/Kapa) ---
ENABLE_PERFORMANCE_ANALYZER = True
ENABLE_AUTO_STRATEGY_OPTIMIZER = True
NOTIFIER_ENABLED = True
ANTI_BINANCE_TESPIT_ENABLED = True

# --- Proxy Ayarları ---
USE_PROXY = False                      # Proxy kullanılsın mı?
PROXY_LIST_PATH = "proxy_list.txt"   # Proxy listesi buradan yüklenecek
API_TIMEOUT = 10                     # API istekleri için timeout süresi
PROXY_TIMEOUT = 15                  # Proxy kaynaklı isteklerde timeout süresi

# --- İleri Seviye Ayarlar (hazırlık) ---
# RATE_LIMIT_PER_MINUTE = 1200       # Binance’ın max istek limiti (isteğe bağlı aktif edilir)
