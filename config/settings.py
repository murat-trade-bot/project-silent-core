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
TESTNET_MODE = _get_env("TESTNET_MODE", "True").lower() in ("true", "1", "yes")
PAPER_TRADING = _get_env("PAPER_TRADING", "True").lower() in ("true", "1", "yes")

# --- Bot Operation Parameters ---
CYCLE_INTERVAL = int(_get_env("CYCLE_INTERVAL", "10"))
CYCLE_JITTER_MIN = int(_get_env("CYCLE_JITTER_MIN", "0"))
CYCLE_JITTER_MAX = int(_get_env("CYCLE_JITTER_MAX", "5"))
MAX_RETRIES = int(_get_env("MAX_RETRIES", "5"))
RETRY_WAIT_TIME = int(_get_env("RETRY_WAIT_TIME", "5"))

# --- Stealth Mode Parameters ---
STEALTH_DROP_CHANCE = float(_get_env("STEALTH_DROP_CHANCE", "0.02"))
STEALTH_SLEEP_CHANCE = float(_get_env("STEALTH_SLEEP_CHANCE", "0.0"))
STEALTH_SLEEP_MIN = int(_get_env("STEALTH_SLEEP_MIN", "0"))
STEALTH_SLEEP_MAX = int(_get_env("STEALTH_SLEEP_MAX", "0"))
STEALTH_ORDER_SIZE_JITTER = float(_get_env("STEALTH_ORDER_SIZE_JITTER", "0.01"))

# --- Rate Limit Controls ---
MAX_TRADES_PER_HOUR = int(_get_env("MAX_TRADES_PER_HOUR", "20"))
MIN_INTERVAL_BETWEEN_TRADES = int(_get_env("MIN_INTERVAL_BETWEEN_TRADES", "60"))

# --- Position Sizing ---
POSITION_SIZE_PCT = float(_get_env("POSITION_SIZE_PCT", "0.01"))  # Base fraction per trade

# --- Phase Targets ---
PHASE_TARGETS = [
    3234.0,    # 25 Apr - 25 Jun
    38808.0,   # 26 Jun - 26 Aug
    388080.0,  # 27 Aug - 27 Oct
    900000.0,  # 28 Oct - 28 Dec
    1000000.0, # 29 Dec - 1 Feb
    1250000.0  # 2 Feb - 2 Apr
]

# --- Technical Indicator Thresholds ---
RSI_OVERSOLD = float(_get_env("RSI_OVERSOLD", "30"))    # RSI lower bound
RSI_OVERBOUGHT = float(_get_env("RSI_OVERBOUGHT", "70"))# RSI upper bound
ATR_MIN_VOL = float(_get_env("ATR_MIN_VOL", "50"))      # Minimum ATR to allow trades

# --- Decision Engine Tuning ---
SCORE_BUY_THRESHOLD = float(_get_env("SCORE_BUY_THRESHOLD", "1.5"))
TRADE_DROP_CHANCE = float(_get_env("TRADE_DROP_CHANCE", "0.02"))  # Jitter drop probability

# --- Targets & Phases ---
TARGET_USDT = float(_get_env("TARGET_USDT", "3580122"))
PHASES = int(_get_env("PHASES", "6"))

# --- Initial Balance ---
INITIAL_BALANCE = float(_get_env("INITIAL_BALANCE", "231"))

# --- Risk Management Thresholds ---
STOP_LOSS_RATIO = float(_get_env("STOP_LOSS_RATIO", "0.05"))    # 5% stop-loss
TAKE_PROFIT_RATIO = float(_get_env("TAKE_PROFIT_RATIO", "0.10"))  # 10% take-profit
MAX_DRAWDOWN_PCT = float(_get_env("MAX_DRAWDOWN_PCT", "0.30"))   # 30% max drawdown

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
API_TIMEOUT = int(_get_env("API_TIMEOUT", "10"))
PROXY_TIMEOUT = int(_get_env("PROXY_TIMEOUT", "15"))
