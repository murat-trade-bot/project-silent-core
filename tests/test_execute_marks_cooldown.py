from core.types import OrderPlan
from core.pipeline import execute_with_filters
from core.cooldown import REGISTRY


def test_execute_marks_cooldown(monkeypatch):
    # Mock executor: execute_order_plan zaten mock başarı döndürüyor (executor yoksa)
    symbol = "TSTUSDT"
    plan = OrderPlan(symbol=symbol, side="BUY", qty_quote=20.0, entry_price=100.0)
    # Gerçek executor import edilirse client isteyebilir; mock'a zorla
    import core.pipeline as pipeline
    monkeypatch.setattr(pipeline, "_safe_import_executor", lambda: (None, None))
    # İşlem öncesi izin alınmalı
    import time
    ok_before, _ = REGISTRY.can_trade(symbol, time.time())
    res = execute_with_filters(plan, market_state=None, account_state={"quote_free": 1000.0})
    assert res.success is True
    # İşlem sonrası hemen tekrar izin istenirse cooldown nedeniyle reddedilmeli
    ok_after, reason = REGISTRY.can_trade(symbol, time.time())
    assert ok_after is False
    assert "cooldown" in reason
