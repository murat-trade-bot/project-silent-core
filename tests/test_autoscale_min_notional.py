import os
from core.types import OrderPlan
from modules.order_filters import validate_order_plan


def test_autoscale_min_notional_buy_with_quote_balance(monkeypatch):
    # Autoscale açık
    monkeypatch.setenv("ALLOW_MIN_NOTIONAL_AUTOSCALE", "1")
    plan = OrderPlan(symbol="BTCUSDT", side="BUY", qty_quote=1.0, entry_price=100.0)
    # Account'ta yeterli USDT olsun
    account_state = {"quote_free": 1000.0}
    rc = validate_order_plan(plan, market_state=None, account_state=account_state)
    assert rc.ok is True
    assert rc.adjusted_qty is not None and rc.adjusted_qty > 0
