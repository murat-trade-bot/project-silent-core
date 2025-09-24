from __future__ import annotations
from typing import Optional, Dict, Any
from core.types import OrderPlan, OrderResult
from core.pipeline import execute_with_filters


def place_order(plan: OrderPlan,
                market_state: Optional[Dict[str, Any]] = None,
                account_state: Optional[Dict[str, Any]] = None) -> OrderResult:
    """
    Tek giriş noktası: validate -> execute -> cooldown işaretleme.
    """
    return execute_with_filters(plan, market_state, account_state)
