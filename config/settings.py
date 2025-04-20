import os
from dotenv import load_dotenv

"""
Configuration settings for Project Silent Core.
Loads environment variables and provides typed parameters for bot operation.
"""
# Load .env file
load_dotenv()

def _get_env(name: str, default=None, required: bool = False) -> str:
    """
    Helper to fetch environment variable, with optional default and requirement enforcement.
    """
    value = os.getenv(name, default)
    if required and not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value

# --- Spot Trading Symbols ---
SYMBOLS = [s.strip() for s in _get_env("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT").split(",") if s.strip()]

# --- API Credentials (required) ---
BINANCE_API_KEY = _get_env("BINANCE_API_KEY", required=True)
BINANCE_API_SECRET = _get_env("BINANCE_API_SECRET", required=True)

NEWS_API_KEY = _get_env("NEWS_API_KEY", default="")
TELEGRAM_TOKEN = _get_env("TELEGRAM_TOKEN", default="")
TELEGRAM_CHAT_ID = _get_env("TELEGRAM_CHAT_ID", default="")

# --- Trading Mode Flags (Test & Live) ---
# Enable Binance testnet for safe testing (True/False)
TESTNET_MODE = _get_env("TESTNET_MODE", "True").lower() in ("true", "1", "yes")
# Enable paper trading (simulation) (True/False)
PAPER_TRADING = _get_env("PAPER_TRADING", "True").lower() in ("true", "1", "yes")

# --- Bot Operation Parameters ---
CYCLE_INTERVAL = int(_get_env("CYCLE_INTERVAL", "10"))  # Base wait time between symbol loops (seconds)
CYCLE_JITTER_MIN = int(_get_env("CYCLE_JITTER_MIN", "0"))  # Minimum random jitter
CYCLE_JITTER_MAX = int(_get_env("CYCLE_JITTER_MAX", "5"))  # Maximum random jitter
MAX_RETRIES = int(_get_env("MAX_RETRIES", "5"))  # Max attempts on errors
RETRY_WAIT_TIME = int(_get_env("RETRY_WAIT_TIME", "5"))  # Wait time between retries (seconds)

# --- Stealth Mode Parameters ---
STEALTH_DROP_CHANCE = float(_get_env("STEALTH_DROP_CHANCE", "0.02"))  # Probability to skip an order
STEALTH_SLEEP_CHANCE = float(_get_env("STEALTH_SLEEP_CHANCE", "0.0"))  # Probability to pause
STEALTH_SLEEP_MIN = int(_get_env("STEALTH_SLEEP_MIN", "0"))  # Min sleep duration (seconds)
STEALTH_SLEEP_MAX = int(_get_env("STEALTH_SLEEP_MAX", "0"))  # Max sleep duration (seconds)
STEALTH_ORDER_SIZE_JITTER = float(_get_env("STEALTH_ORDER_SIZE_JITTER", "0.01"))  # Order size variance

# --- Rate Limit Controls ---
MAX_TRADES_PER_HOUR = int(_get_env("MAX_TRADES_PER_HOUR", "20"))  # Caps hourly trades
MIN_INTERVAL_BETWEEN_TRADES = int(_get_env("MIN_INTERVAL_BETWEEN_TRADES", "60"))  # Min seconds between trades

# --- Targets & Phases ---
TARGET_USDT = float(_get_env("TARGET_USDT", "3580122"))  # One-year profit goal
PHASES = int(_get_env("PHASES", "6"))  # Chart/reporting phases

# --- Initial Balance ---
# Starting capital for paper trading or performance calculations
INITIAL_BALANCE = float(_get_env("INITIAL_BALANCE", "231"))

# --- Logging & Persistence ---
LOG_FILE = _get_env("LOG_FILE", "bot_logs.txt")
CSV_LOG_FILE = _get_env("CSV_LOG_FILE", "trades_history.csv")

# --- Optional Feature Flags ---
ENABLE_PERFORMANCE_ANALYZER = _get_env("ENABLE_PERFORMANCE_ANALYZER", "True").lower() in ("true", "1", "yes")
ENABLE_AUTO_STRATEGY_OPTIMIZER = _get_env("ENABLE_AUTO_STRATEGY_OPTIMIZER", "True").lower() in ("true", "1", "yes")
NOTIFIER_ENABLED = _get_env("NOTIFIER_ENABLED", "True").lower() in ("true", "1", "yes")
ANTI_BINANCE_TESPIT_ENABLED = _get_env("ANTI_BINANCE_TESPIT_ENABLED", "True").lower() in ("true", "1", "yes")

# --- Proxy Settings ---
USE_PROXY = _get_env("USE_PROXY", "False").lower() in ("true", "1", "yes")
PROXY_LIST_PATH = _get_env("PROXY_LIST_PATH", "proxy_list.txt")
API_TIMEOUT = int(_get_env("API_TIMEOUT", "10"))  # Seconds
PROXY_TIMEOUT = int(_get_env("PROXY_TIMEOUT", "15"))  # Seconds
