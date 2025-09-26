import os
import core.pipeline as p
from core.types import OrderPlan, OrderResult


class StubExec:
    """Deterministik, spot-only mock executor."""
    def place_order(self, plan: OrderPlan):  # type: ignore
        return {
            "ok": True,
            "orderId": "E2E-MOCK",
            "filledQty": plan.qty_base or plan.qty_quote,
            "avgPrice": plan.entry_price,
        }


def _stub_import():
    return ("executor-mock", StubExec)


def test_buy_market_ok(monkeypatch):
    # Test profili
    monkeypatch.setenv("ORDER_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("ORDER_PIPELINE_IGNORE_REGIME", "true")
    monkeypatch.setenv("TEST_SKIP_COOLDOWN", "1")
    monkeypatch.setenv("ORDER_TYPE", "MARKET")
    monkeypatch.setenv("ALLOW_MIN_NOTIONAL_AUTOSCALE", "true")
    monkeypatch.setenv("MAX_SLIPPAGE_PCT", "0")
    monkeypatch.setenv("USE_EXCHANGE_INFO", "false")
    monkeypatch.setenv("DEFAULT_MIN_NOTIONAL_USDT", "5")
    monkeypatch.setenv("DEFAULT_TICK_SIZE", "0.0001")
    monkeypatch.setenv("DEFAULT_STEP_SIZE", "0.0001")

    # Executor mock
    monkeypatch.setattr(p, "_safe_import_executor", lambda: _stub_import())

    plan = OrderPlan(symbol="SUIUSDT", side="BUY", qty_quote=10.0, entry_price=1.0)
    res: OrderResult = p.execute_with_filters(
        plan,
        market_state={"last_price": 1.0},
        account_state={"quote_free": 250.0},
    )
    assert res.success is True and (res.status in ("ok", "mock-ok"))
