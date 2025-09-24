from core.pipeline import execute_with_filters
from core.types import OrderPlan, OrderResult


def test_error_classification_network(monkeypatch):
    # _safe_import_executor'ı stubla
    class StubExec:
        def place_order(self, plan):
            raise TimeoutError("deadline exceeded")

    def stub_import():
        return ("executor", StubExec)

    monkeypatch.setenv("ORDER_PIPELINE_ENABLED", "true")
    import core.pipeline as p
    monkeypatch.setattr(p, "_safe_import_executor", lambda: stub_import())

    res: OrderResult = execute_with_filters(OrderPlan(symbol="BTCUSDT", side="BUY", qty_quote=20.0, entry_price=100.0))
    assert res.success is False and res.status == "network-error"
