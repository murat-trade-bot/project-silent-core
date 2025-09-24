import re
from core.metrics import _reset_for_tests, inc_order, inc_reject, inc_exc, observe_exec, _generate_latest_text


def test_metrics_counters_and_export_text():
    _reset_for_tests()
    inc_order("BTCUSDT", "BUY", "ok")
    inc_order("BTCUSDT", "BUY", "ok")
    inc_order("BTCUSDT", "SELL", "err")
    inc_reject("cooldown")
    inc_reject("minNotional")
    inc_exc("TimeoutError")
    observe_exec(0.123)

    txt = _generate_latest_text()
    assert "orders_total" in txt
    assert "order_rejections_total" in txt
    assert "exceptions_total" in txt
    assert "order_execution_seconds" in txt
    # iki buy-ok emri sayılmış olmalı (label sırası garanti edilmez, regex kullan)
    pattern = r"orders_total\{(?=[^}]*symbol=\"BTCUSDT\")(?=[^}]*side=\"BUY\")(?=[^}]*status=\"ok\")[^}]*\}\s+2(\.0)?\b"
    assert re.search(pattern, txt) is not None
