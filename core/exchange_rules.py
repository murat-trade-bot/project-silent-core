from __future__ import annotations
from dataclasses import dataclass
import os
from typing import Optional, Dict, Any
import json
import time
import urllib.request


@dataclass
class SymbolRules:
    symbol: str
    tick_size: float = 0.0001       # price increment
    step_size: float = 0.0001       # qty increment
    min_notional_usdt: float = 5.0  # min order notional (fallback)
    quote: str = "USDT"


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


USE_EXCHANGE_INFO = _bool_env("USE_EXCHANGE_INFO", False)


def _load_from_modules(symbol: str) -> Optional[SymbolRules]:
    """
    Opsiyonel exchange info sağlayıcıdan kuralları çekmeyi dener.
    Beklenen arayüz:
      modules.exchange_info.get_symbol_rules(symbol) -> dict
      { 'tickSize': 0.01, 'stepSize': 0.001, 'minNotional': 5, 'quote': 'USDT' }
    """
    try:
        from modules.exchange_info import get_symbol_rules  # type: ignore
        d: Dict[str, Any] = get_symbol_rules(symbol)
        return SymbolRules(
            symbol=symbol,
            tick_size=float(d.get("tickSize", 0.0001)),
            step_size=float(d.get("stepSize", 0.0001)),
            min_notional_usdt=float(d.get("minNotional", 5.0)),
            quote=str(d.get("quote", "USDT")),
        )
    except Exception:
        return None


def load_rules_for_symbol(symbol: str) -> SymbolRules:
    """
    Önce opsiyonel exchange_info modülünü dener, yoksa ENV fallback ile döner.
    ENV fallback:
      DEFAULT_TICK_SIZE, DEFAULT_STEP_SIZE, DEFAULT_MIN_NOTIONAL_USDT
    """
    if USE_EXCHANGE_INFO:
        # 1) Modül sağlayıcısı
        r = _load_from_modules(symbol)
        if r:
            return r
        # 2) REST fallback (Binance spot exchangeInfo) - testnet/prod autodetect
        #    Çok sık çağrılmaması önerilir; basit cache eklemek isterseniz genişletilebilir.
        base = os.getenv("BINANCE_EXCHANGEINFO_BASE", "https://testnet.binance.vision")
        url = f"{base}/api/v3/exchangeInfo?symbol={symbol}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # nosec - controlled URL
                data = json.loads(resp.read().decode("utf-8"))
            symbols = data.get("symbols") or []
            if symbols:
                sdef = symbols[0]
                filters = {f["filterType"]: f for f in sdef.get("filters", [])}
                tick = float(filters.get("PRICE_FILTER", {}).get("tickSize", 0.0001))
                step = float(filters.get("LOT_SIZE", {}).get("stepSize", 0.0001))
                min_notional = float(
                    filters.get("NOTIONAL", {}).get("minNotional")
                    or filters.get("MIN_NOTIONAL", {}).get("minNotional")
                    or 5.0
                )
                return SymbolRules(symbol=symbol, tick_size=tick, step_size=step, min_notional_usdt=min_notional, quote="USDT")
        except Exception:
            pass
    return SymbolRules(
        symbol=symbol,
        tick_size=float(os.getenv("DEFAULT_TICK_SIZE", 0.0001)),
        step_size=float(os.getenv("DEFAULT_STEP_SIZE", 0.0001)),
        min_notional_usdt=float(os.getenv("DEFAULT_MIN_NOTIONAL_USDT", 5.0)),
        quote="USDT"
    )
