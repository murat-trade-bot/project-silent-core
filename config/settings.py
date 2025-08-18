# -*- coding: utf-8 -*-
"""
Project Silent Core - settings.py (v2.2)
- .env tabanlı, tip güvenli konfig
- SIM/LIVE yürütme modu
- Testnet desteği
- main.py ile birebir uyumlu alias'lar (BAŞLANGIÇ_SERMEYESİ, IŞLEM_MIKTARI, MIN_BAKIYE, TRADE_INTERVAL)
"""

from __future__ import annotations
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# Yardımcılar
# -----------------------------
def _as_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> str | None:
    val = os.getenv(name, default)
    if required and (val is None or str(val).strip() == ""):
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return val

def _get_float(name: str, default: float, required: bool = False) -> float:
    v = _get_env(name, None, required)
    return float(v) if v is not None else float(default)

def _get_int(name: str, default: int, required: bool = False) -> int:
    v = _get_env(name, None, required)
    return int(v) if v is not None else int(default)

# -----------------------------
# Yürütme Modları
# -----------------------------
EXECUTION_MODE = (_get_env("EXECUTION_MODE", "SIM") or "SIM").upper()  # SIM | LIVE
TESTNET_MODE   = _as_bool(_get_env("TESTNET_MODE", "True"), default=True)
PAPER_TRADING  = _as_bool(_get_env("PAPER_TRADING", "True"), default=True)

# PAPER_TRADING açıksa, zorunlu olarak SIM çalıştır
if PAPER_TRADING and EXECUTION_MODE != "SIM":
    EXECUTION_MODE = "SIM"

# API anahtarlarını ne zaman zorunlu kılsın?
# - LIVE modda kesinlikle gerekli
# - TESTNET modda da gerekli (testnet'e bağlanmak için)
_required_keys = (EXECUTION_MODE == "LIVE") or TESTNET_MODE

# -----------------------------
# API Anahtarları
# -----------------------------
BINANCE_API_KEY    = _get_env("BINANCE_API_KEY", required=_required_keys)
BINANCE_API_SECRET = _get_env("BINANCE_API_SECRET", required=_required_keys)

# Bildirim/opsiyonel servisler
NOTIFIER_ENABLED   = _as_bool(_get_env("NOTIFIER_ENABLED", "True"), default=True)
TELEGRAM_TOKEN     = _get_env("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID   = _get_env("TELEGRAM_CHAT_ID", "")
NEWS_API_KEY       = _get_env("NEWS_API_KEY", "")

# Twitter / X (sentiment için, opsiyonel)
TWITTER_API_KEY             = _get_env("TWITTER_API_KEY", "")
TWITTER_API_SECRET          = _get_env("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN        = _get_env("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = _get_env("TWITTER_ACCESS_TOKEN_SECRET", "")

# -----------------------------
# Sembol Seçimi
# -----------------------------
USE_DYNAMIC_SYMBOL_SELECTION = _as_bool(_get_env("USE_DYNAMIC_SYMBOL_SELECTION", "True"), default=True)
USDT_ONLY                    = _as_bool(_get_env("USDT_ONLY", "True"), default=True)
SYMBOLS_MAX                  = _get_int("SYMBOLS_MAX", 12)

# Fallback / manuel semboller
FALLBACK_SYMBOLS: List[str] = [
    s.strip() for s in (_get_env("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT") or "").split(",") if s.strip()
]

def _make_client_for_symbols():
    """Dinamik semboller çekilirken testnet URL'ini uygula."""
    from binance.client import Client as _C
    _cli = _C(BINANCE_API_KEY, BINANCE_API_SECRET)
    if TESTNET_MODE:
        _cli.API_URL = 'https://testnet.binance.vision/api'
    return _cli

def _get_dynamic_symbols() -> List[str]:
    if not USE_DYNAMIC_SYMBOL_SELECTION:
        return FALLBACK_SYMBOLS[:SYMBOLS_MAX]

    try:
        cli = _make_client_for_symbols()
        ex = cli.get_exchange_info()
        symbols = []
        for s in ex.get("symbols", []):
            if s.get("status") != "TRADING":
                continue
            sym = s.get("symbol", "")
            if USDT_ONLY and not sym.endswith("USDT"):
                continue
            symbols.append(sym)
        # Çok uzun listeleri kıs
        if SYMBOLS_MAX and len(symbols) > SYMBOLS_MAX:
            symbols = symbols[:SYMBOLS_MAX]
        return symbols or FALLBACK_SYMBOLS[:SYMBOLS_MAX]
    except Exception as e:
        print(f"[settings] Dynamic symbol fetch failed: {e}")
        return FALLBACK_SYMBOLS[:SYMBOLS_MAX]

SYMBOLS: List[str] = _get_dynamic_symbols()

# -----------------------------
# Döngü / Zamanlama
# -----------------------------
# Not: main.py şu an TRADE_INTERVAL'ü doğrudan kullanmıyor ama alias sağlıyoruz.
CYCLE_INTERVAL   = _get_int("CYCLE_INTERVAL", 1)    # dakika
CYCLE_JITTER_MIN = _get_int("CYCLE_JITTER_MIN", 0)
CYCLE_JITTER_MAX = _get_int("CYCLE_JITTER_MAX", 0)
HEARTBEAT_INTERVAL = _get_int("HEARTBEAT_INTERVAL", 3600)

# main.py uyumluluk alias
TRADE_INTERVAL = CYCLE_INTERVAL

# -----------------------------
# Risk / Trade Parametreleri
# -----------------------------
STOP_LOSS_RATIO   = _get_float("STOP_LOSS_RATIO", 0.05)   # %5
TAKE_PROFIT_RATIO = _get_float("TAKE_PROFIT_RATIO", 0.10) # %10
MAX_DRAWDOWN_PCT  = _get_float("MAX_DRAWDOWN_PCT", 0.20)  # %20 (kullanılabilir)

# İşlem büyüklüğü (USDT). main.py IŞLEM_MIKTARI olarak bekler.
TRADE_USDT_AMOUNT = _get_float("TRADE_USDT_AMOUNT", 20.0)
IŞLEM_MIKTARI     = TRADE_USDT_AMOUNT  # alias (USDT)

# Simülasyon muhasebesi için başlangıç ve emniyet eşiği
BAŞLANGIÇ_SERMEYESİ = _get_float("STARTING_BALANCE", 252.0)
MIN_BAKIYE          = _get_float("MIN_BALANCE", 10.0)

# -----------------------------
# Teknik Eşikler (main.py ile uyumlu varsayılanlar)
# -----------------------------
# Volatilite & hacim eşikleri (main.py içinde sabit; istersen buradan da kullanabilirsin)
VOLATILITY_THRESHOLD_1M = _get_float("VOLATILITY_THRESHOLD_1M", 0.001)  # %0.1
VOLATILITY_THRESHOLD_5M = _get_float("VOLATILITY_THRESHOLD_5M", 0.002)  # %0.2

# Not: main.py hacmi 24h quoteVolume ve 1m/5m base volume'den hesaplıyor.
VOLUME_THRESHOLD_1M = _get_float("VOLUME_THRESHOLD_1M", 5000.0)   # yaklaşık
VOLUME_THRESHOLD_5M = _get_float("VOLUME_THRESHOLD_5M", 20000.0)  # yaklaşık

# -----------------------------
# Rate Limit / Sipariş Aralığı (opsiyonel; ileride main'de kullanılabilir)
# -----------------------------
MAX_TRADES_PER_HOUR         = _get_int("MAX_TRADES_PER_HOUR", 20)
MIN_INTERVAL_BETWEEN_TRADES = _get_int("MIN_INTERVAL_BETWEEN_TRADES", 0)  # saniye
ORDER_COOLDOWN              = _get_int("ORDER_COOLDOWN", 1)               # saniye

# -----------------------------
# Proxy / Network (opsiyonel)
# -----------------------------
USE_PROXY       = _as_bool(_get_env("USE_PROXY", "False"), default=False)
PROXY_LIST_PATH = _get_env("PROXY_LIST_PATH", "proxy_list.txt")
API_TIMEOUT     = _get_int("API_TIMEOUT", 10)
PROXY_TIMEOUT   = _get_int("PROXY_TIMEOUT", 15)

# -----------------------------
# Logging
# -----------------------------
LOG_FILE   = _get_env("LOG_FILE", "bot_logs.txt")
LOG_LEVEL  = (_get_env("LOG_LEVEL", "INFO") or "INFO").upper()
CSV_LOG_FILE = _get_env("CSV_LOG_FILE", "trades_history.csv")

# -----------------------------
# Validasyon
# -----------------------------
assert 0 < STOP_LOSS_RATIO < 1, "STOP_LOSS_RATIO 0 ile 1 arasında olmalı!"
assert 0 < TAKE_PROFIT_RATIO < 1, "TAKE_PROFIT_RATIO 0 ile 1 arasında olmalı!"