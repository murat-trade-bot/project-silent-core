from core.types import OrderPlan
from modules.order_filters import validate_order_plan, mark_executed


def test_cooldown_enforced(monkeypatch):
    monkeypatch.setenv("MIN_TRADE_SPACING_SEC", "3")
    from core.cooldown import CFG
    CFG.min_spacing_sec = 3

    plan = OrderPlan(symbol="ADAUSDT", side="BUY", qty_quote=10.0, entry_price=1.0)

    rc1 = validate_order_plan(plan, market_state={"last_price": 1.0}, account_state={"quote_free": 100.0})
    assert rc1.ok is True
    mark_executed(plan.symbol)

    rc2 = validate_order_plan(plan, market_state={"last_price": 1.0}, account_state={"quote_free": 100.0})
    assert rc2.ok is False and any("cooldown" in r for r in rc2.reasons)
