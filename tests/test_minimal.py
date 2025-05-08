import pytest
from minimal_main import start_bot

def test_start_bot_smoke(capsys):
    # Fonksiyon True dönmeli
    assert start_bot() is True

    # Konsolda "Bot Başlatıldı" çıktısı olmalı
    captured = capsys.readouterr()
    assert "Bot Başlatıldı" in captured.out
