from __future__ import annotations
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import time


class Decision(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"   # pozisyonu koru (no new order)
    WAIT = "WAIT"   # hiçbir işlem yok


@dataclass
class SignalBundle:
    symbol: str
    ts: float = field(default_factory=lambda: time.time())
    buy_score: float = 0.0
    sell_score: float = 0.0
    regime_on: bool = True
    volatility: float = 0.0
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderPlan:
    symbol: str
    side: str                 # "BUY" | "SELL"
    qty_base: Optional[float] = None   # miktar (base)
    qty_quote: Optional[float] = None  # alternatif: USDT bazlı
    entry_price: Optional[float] = None
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    time_in_force: str = "GTC"
    reason: str = ""
    confidence: float = 0.0
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskCheckResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    adjusted_qty: Optional[float] = None
    adjusted_entry: Optional[float] = None
    adjusted_sl: Optional[float] = None
    adjusted_tp: Optional[float] = None
    risk_score: float = 0.0
    cooldown_seconds: int = 0


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    filled_qty: Optional[float] = None
    avg_price: Optional[float] = None
    status: str = ""
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


def to_json(obj: Any) -> str:
    try:
        return json.dumps(asdict(obj), ensure_ascii=False)
    except Exception:
        return str(obj)
