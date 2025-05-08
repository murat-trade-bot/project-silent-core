# tests/test_real_executor.py

from minimal_main import start_bot

def test_real_executor_integration(capsys):
    """
    start_bot():
      – Başlatma mesajı atar
      – Strategy aksiyonunu yazdırır
      – ExecutorManager.execute() çağrısını yapar ve log üretir
    """
    assert start_bot() is True
    out = capsys.readouterr().out

    assert "Bot Başlatıldı" in out
    assert "Aksiyon:" in out
    # ExecutorManager.log'unu kontrol ediyoruz
    assert "Executing action:" in out
