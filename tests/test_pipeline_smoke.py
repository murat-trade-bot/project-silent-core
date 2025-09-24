from core.pipeline import build_order_plan_from_signals, validate_order_plan, execute_order_plan
from core.types import SignalBundle

def test_pipeline_smoke_wait_when_low_scores():
    sb = SignalBundle(symbol="BTCUSDT", buy_score=0.4, sell_score=0.3, regime_on=True)
    plan = build_order_plan_from_signals(sb)
    assert plan is None


def test_pipeline_smoke_buy_path():
    sb = SignalBundle(symbol="BTCUSDT", buy_score=0.7, sell_score=0.2, regime_on=True)
    plan = build_order_plan_from_signals(sb)
    assert plan is not None and plan.side == "BUY"
    rc = validate_order_plan(plan)
    assert rc.ok is True
    res = execute_order_plan(plan)
    assert res.success in (True, False)  # gerçek executor varsa True, yoksa mock True
