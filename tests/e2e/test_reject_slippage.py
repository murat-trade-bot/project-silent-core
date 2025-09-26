from core.types import OrderPlan
from modules.order_filters import validate_order_plan


def test_reject_when_slippage_exceeds(monkeypatch):
    monkeypatch.setenv("MAX_SLIPPAGE_PCT", "0.001")  # %0.1
    monkeypatch.setenv("USE_EXCHANGE_INFO", "false")
    plan = OrderPlan(symbol="BTCUSDT", side="BUY", qty_quote=20.0, entry_price=101.0)
    rc = validate_order_plan(plan, market_state={"last_price": 100.0})
    assert rc.ok is False
    assert any("slippage_exceeds_limit" in r for r in rc.reasons)
