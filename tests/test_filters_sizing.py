from core.types import OrderPlan
from modules.order_filters import validate_order_plan
import os

def test_validate_order_plan_basic_buy():
    os.environ["TEST_SKIP_COOLDOWN"] = "1"
    plan = OrderPlan(symbol="BTCUSDT", side="BUY", qty_quote=20.0, entry_price=100.0)
    rc = validate_order_plan(plan, market_state=None, account_state=None)
    assert rc.ok is True
    assert rc.adjusted_qty is not None
    assert rc.adjusted_entry is not None


def test_validate_order_plan_fails_min_notional():
    plan = OrderPlan(symbol="BTCUSDT", side="BUY", qty_quote=1.0, entry_price=100.0)
    rc = validate_order_plan(plan)
    assert rc.ok is False
    assert any("min_notional" in r for r in rc.reasons)
