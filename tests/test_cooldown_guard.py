from core.cooldown import REGISTRY, CFG
from core.types import OrderPlan
from modules.order_filters import validate_order_plan, mark_executed


def test_cooldown_spacing(monkeypatch):
    # spacing'i sıkılaştır (2s)
    monkeypatch.setenv("MIN_TRADE_SPACING_SEC", "2")
    # CFG'yi güncelle (yeniden import olmadan)
    CFG.min_spacing_sec = 2

    plan = OrderPlan(symbol="SUIUSDT", side="BUY", qty_quote=10.0, entry_price=1.0)

    # İlk deneme -> OK
    rc1 = validate_order_plan(plan)
    assert rc1.ok is True
    # Emir atıldı varsay -> mark_executed
    mark_executed(plan.symbol)

    # Hemen ikinci deneme -> cooldown nedeniyle RED
    rc2 = validate_order_plan(plan)
    assert rc2.ok is False
    assert any("cooldown" in r for r in rc2.reasons)
