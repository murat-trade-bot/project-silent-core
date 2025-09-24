from modules.order_filters import validate_order_plan
import os


def test_slippage_guard_rejects_when_exceeds(monkeypatch):
    # %0.5 limit
    monkeypatch.setenv("MAX_SLIPPAGE_PCT", "0.005")

    plan = dict(symbol="BTCUSDT", side="BUY", qty_quote=20.0, entry_price=101.0)
    market_state = {"last_price": 100.0}
    from core.types import OrderPlan
    rc = validate_order_plan(OrderPlan(**plan), market_state=market_state)
    assert rc.ok is False
    reasons = " ".join(rc.reasons)
    assert "slippage_exceeds_limit" in reasons


def test_slippage_guard_allows_within_limit(monkeypatch):
    monkeypatch.setenv("MAX_SLIPPAGE_PCT", "0.01")  # %1
    from core.types import OrderPlan
    market_state = {"last_price": 100.0}
    os.environ["TEST_SKIP_COOLDOWN"] = "1"
    rc = validate_order_plan(OrderPlan(symbol="BTCUSDT", side="BUY", qty_quote=20.0, entry_price=100.4), market_state=market_state)
    assert rc.ok is True
