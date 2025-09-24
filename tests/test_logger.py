def test_logger_singleton_and_handlers():
    from core.logger import get_logger, set_level
    a = get_logger()
    b = get_logger()
    assert a is b, "logger singleton olmalı"
    handler_types = [type(h) for h in a.handlers]
    # Aynı handler türü birden fazla olmamalı (console + file)
    assert len(handler_types) == len(set(handler_types)), "duplicate handler oluşmamalı"
    # Seviye ayarı çalışmalı (exception atmamalı)
    set_level("DEBUG")
    set_level("INFO")
