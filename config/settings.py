import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

"""
Configuration settings for Project Silent Core.
Loads environment variables and provides typed parameters for bot operation.
"""

# --- API Keys (Yukarıda ve belirgin şekilde) ---
# Binance, Telegram, News, Twitter, Onchain gibi tüm API anahtarları burada toplanır.

# Load .env file
load_dotenv()

def _get_env(name: str, default=None, required: bool = False):
    value = os.getenv(name, default)
    if required and not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value

# --- API Credentials (required) ---
BINANCE_API_KEY    = _get_env("BINANCE_API_KEY", required=True)
BINANCE_API_SECRET = _get_env("BINANCE_API_SECRET", required=True)

# --- News & Notification API Keys ---
NEWS_API_KEY       = _get_env("NEWS_API_KEY", default="")
TELEGRAM_TOKEN     = _get_env("TELEGRAM_TOKEN", default="")
TELEGRAM_CHAT_ID   = _get_env("TELEGRAM_CHAT_ID", default="")

# --- Twitter API Keys (Sentiment için) ---
TWITTER_API_KEY            = _get_env("TWITTER_API_KEY", default="")
TWITTER_API_SECRET         = _get_env("TWITTER_API_SECRET", default="")
TWITTER_ACCESS_TOKEN       = _get_env("TWITTER_ACCESS_TOKEN", default="")
TWITTER_ACCESS_TOKEN_SECRET= _get_env("TWITTER_ACCESS_TOKEN_SECRET", default="")

# --- Onchain API Key ---
ONCHAIN_API_KEY = _get_env("ONCHAIN_API_KEY", default="")

# --- Dynamic Altcoin Selection Flag ---
USE_DYNAMIC_SYMBOL_SELECTION = _get_env("USE_DYNAMIC_SYMBOL_SELECTION", "True").lower() in ("true","1","yes")

# --- Spot Trading Symbols ---
SYMBOLS = []
if USE_DYNAMIC_SYMBOL_SELECTION:
    try:
        from binance.client import Client
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        exchange_info = client.get_exchange_info()
        SYMBOLS = [
            s['symbol']
            for s in exchange_info['symbols']
            if s['status'] == 'TRADING' and s['symbol'].endswith('USDT')
        ]
    except Exception as e:
        print(f"[settings] Binance API'dan sembol çekilemedi: {e}")
        SYMBOLS = [
            s.strip()
            for s in _get_env("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT").split(",")
            if s.strip()
        ]
else:
    SYMBOLS = [
        s.strip()
        for s in _get_env("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT").split(",")
        if s.strip()
    ]

# --- Trading Mode Flags (Test & Live) ---
TESTNET_MODE  = _get_env("TESTNET_MODE", "True").lower() in ("true","1","yes")
PAPER_TRADING = _get_env("PAPER_TRADING", "True").lower() in ("true","1","yes")

# --- Bot Operation Parameters ---
CYCLE_INTERVAL     = int(_get_env("CYCLE_INTERVAL", "1"))  # Döngü aralığı (dk)
CYCLE_JITTER_MIN   = int(_get_env("CYCLE_JITTER_MIN", "0"))
CYCLE_JITTER_MAX   = int(_get_env("CYCLE_JITTER_MAX", "0"))
HEARTBEAT_INTERVAL = int(_get_env("HEARTBEAT_INTERVAL", "3600"))

MAX_RETRIES        = int(_get_env("MAX_RETRIES", "5"))
RETRY_WAIT_TIME    = int(_get_env("RETRY_WAIT_TIME", "5"))

# --- Stealth Mode Parameters (disabled by default) ---
STEALTH_DROP_CHANCE       = float(_get_env("STEALTH_DROP_CHANCE", "0.0"))
STEALTH_SLEEP_CHANCE      = float(_get_env("STEALTH_SLEEP_CHANCE", "0.0"))
STEALTH_SLEEP_MIN         = int(_get_env("STEALTH_SLEEP_MIN", "0"))
STEALTH_SLEEP_MAX         = int(_get_env("STEALTH_SLEEP_MAX", "0"))
STEALTH_ORDER_SIZE_JITTER = float(_get_env("STEALTH_ORDER_SIZE_JITTER", "0.2"))

# --- Rate Limit Controls ---
MAX_TRADES_PER_HOUR         = int(_get_env("MAX_TRADES_PER_HOUR", "20"))
MIN_INTERVAL_BETWEEN_TRADES = int(_get_env("MIN_INTERVAL_BETWEEN_TRADES", "0"))
ORDER_COOLDOWN              = int(_get_env("ORDER_COOLDOWN", "1"))

# --- Growth Factor for Trading Periods ---
GROWTH_FACTOR = float(_get_env("GROWTH_FACTOR", "1.0"))

# --- Position Sizing ---
POSITION_SIZE_PCT = float(_get_env("POSITION_SIZE_PCT", "0.01"))

# --- Technical Thresholds ---
RSI_OVERSOLD   = float(_get_env("RSI_OVERSOLD", "30"))
RSI_OVERBOUGHT = float(_get_env("RSI_OVERBOUGHT", "70"))
ATR_MIN_VOL    = float(_get_env("ATR_MIN_VOL", "50"))
ATR_RATIO      = float(_get_env("ATR_RATIO", "0.02"))  # volatility-based sizing ratio

# --- Decision Tuning ---
SCORE_BUY_THRESHOLD = float(_get_env("SCORE_BUY_THRESHOLD", "1.5"))
TRADE_DROP_CHANCE   = float(_get_env("TRADE_DROP_CHANCE", "0.02"))

# --- Risk & Trade Parameters ---
STOP_LOSS_RATIO     = float(_get_env("STOP_LOSS_RATIO", "0.05"))
TAKE_PROFIT_RATIO   = float(_get_env("TAKE_PROFIT_RATIO", "0.10"))
MAX_DRAWDOWN_PCT    = float(_get_env("MAX_DRAWDOWN_PCT", "0.20"))
TRADE_USDT_AMOUNT   = float(_get_env("TRADE_USDT_AMOUNT", "20"))

# --- Logging & Persistence ---
LOG_FILE     = _get_env("LOG_FILE", "bot_logs.txt")
CSV_LOG_FILE = _get_env("CSV_LOG_FILE", "trades_history.csv")

# --- Optional Features ---
ENABLE_AUTO_STRATEGY_OPTIMIZER = _get_env("ENABLE_AUTO_STRATEGY_OPTIMIZER", "True").lower() in ("true","1","yes")
NOTIFIER_ENABLED               = _get_env("NOTIFIER_ENABLED", "True").lower() in ("true","1","yes")
ANTIBINANCE_TESPIT_ENABLED     = _get_env("ANTIBINANCE_TESPIT_ENABLED", "True").lower() in ("true","1","yes")

# --- Proxy Settings ---
USE_PROXY       = _get_env("USE_PROXY", "False").lower() in ("true","1","yes")
PROXY_LIST_PATH = _get_env("PROXY_LIST_PATH", "proxy_list.txt")
API_TIMEOUT     = int(_get_env("API_TIMEOUT", "10"))
PROXY_TIMEOUT   = int(_get_env("PROXY_TIMEOUT", "15"))

# --- Validation (Ekstra Güvenlik) ---
assert 0 < STOP_LOSS_RATIO < 1, "STOP_LOSS_RATIO 0 ile 1 arasında olmalı!"
assert 0 < TAKE_PROFIT_RATIO < 1, "TAKE_PROFIT_RATIO 0 ile 1 arasında olmalı!"
assert 0 < POSITION_SIZE_PCT < 1, "POSITION_SIZE_PCT 0 ile 1 arasında olmalı!"
