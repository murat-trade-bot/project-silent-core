from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GuardConfig:
    min_spacing_sec: int = 45
    max_trades_per_day: int = 12
    tz_offset_sec: int = 0


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


CFG = GuardConfig(
    min_spacing_sec=_int_env("MIN_TRADE_SPACING_SEC", 45),
    max_trades_per_day=_int_env("MAX_TRADES_PER_DAY", 12),
)


@dataclass
class SymbolState:
    last_ts: float = 0.0
    day_start: int = 0
    trades_today: int = 0


class CooldownRegistry:
    """In-memory cooldown/overtrade guard."""
    def __init__(self):
        self._state: Dict[str, SymbolState] = {}

    def _day_bucket(self, now: float) -> int:
        return int((now + 0) // 86400)

    def can_trade(self, symbol: str, now: float) -> (bool, str):
        st = self._state.get(symbol, SymbolState())
        day = self._day_bucket(now)
        if st.day_start != day:
            st.day_start = day
            st.trades_today = 0
        if (now - st.last_ts) < CFG.min_spacing_sec:
            return (False, f"cooldown: wait {int(CFG.min_spacing_sec - (now - st.last_ts))}s")
        if st.trades_today >= CFG.max_trades_per_day:
            return (False, "daily-trade-limit")
        return (True, "ok")

    def mark_trade(self, symbol: str, now: float) -> None:
        st = self._state.get(symbol, SymbolState())
        day = self._day_bucket(now)
        if st.day_start != day:
            st.day_start = day
            st.trades_today = 0
        st.trades_today += 1
        st.last_ts = now
        self._state[symbol] = st


REGISTRY = CooldownRegistry()
