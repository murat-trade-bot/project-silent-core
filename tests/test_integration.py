# tests/test_integration.py

from minimal_main import start_bot

def test_integration_start_and_strategy(capsys):
    # start_bot() hem başlatma mesajını hem de strategy aksiyonunu yazmalı
    assert start_bot() is True
    out = capsys.readouterr().out
    assert "Bot Başlatıldı" in out
    assert "Aksiyon: HOLD" in out
