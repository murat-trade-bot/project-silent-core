# tests/test_full_integration.py

from minimal_main import start_bot

def test_full_integration_flow(capsys):
    # start_bot() hem başlatma, hem strategy, hem executor çıktısını vermeli
    assert start_bot() is True
    out = capsys.readouterr().out
    assert "Bot Başlatıldı" in out
    assert "Aksiyon: HOLD" in out
    assert "Executing action: HOLD with data: {}" in out
