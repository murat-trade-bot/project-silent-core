from core.types import Decision, SignalBundle, OrderPlan, RiskCheckResult, OrderResult, to_json

def test_types_basic():
    sb = SignalBundle(symbol="BTCUSDT", buy_score=0.7, sell_score=0.2, regime_on=True)
    assert sb.symbol == "BTCUSDT"
    plan = OrderPlan(symbol="BTCUSDT", side="BUY", qty_base=0.01, entry_price=100.0, sl_price=98.0, tp_price=105.0)
    rc = RiskCheckResult(ok=True, adjusted_qty=0.01)
    orr = OrderResult(success=True, order_id="X1", filled_qty=0.01, avg_price=100.1, status="ok")
    assert isinstance(to_json(plan), str)
    assert isinstance(to_json(rc), str)
    assert isinstance(to_json(orr), str)
