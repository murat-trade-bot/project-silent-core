# tests/test_real_strategy.py

from minimal_main import start_bot

def test_real_strategy_integration(capsys):
    """
    start_bot() çalıştığında:
     - Temel başlatma mesajı atılmalı.
     - 'Aksiyon: ' satırı ile gerçek strategy çıktısı gelmeli.
    """
    assert start_bot() is True
    out = capsys.readouterr().out
    assert "Bot Başlatıldı" in out
    assert "Aksiyon:" in out
