from __future__ import annotations
import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


@dataclass
class ExecPrefs:
    order_type: str = "LIMIT"   # LIMIT | MARKET
    time_in_force: str = "GTC"  # GTC | IOC
    post_only: bool = False
    max_slippage_pct: float = 0.0  # 0 => kapalı


def load_prefs() -> ExecPrefs:
    return ExecPrefs(
        order_type=os.getenv("ORDER_TYPE", "LIMIT").upper(),
        time_in_force=os.getenv("TIME_IN_FORCE", "GTC").upper(),
        post_only=_bool_env("POST_ONLY", False),
        max_slippage_pct=_float_env("MAX_SLIPPAGE_PCT", 0.0),
    )
