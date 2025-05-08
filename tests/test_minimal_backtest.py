# tests/test_minimal_backtest.py

from minimal_backtest import run_backtest

def test_run_backtest_outputs_value(capsys):
    # Fonksiyon float tipinde değer döndürmeli
    val = run_backtest()
    assert isinstance(val, float)

    # Konsolda 'Final portfolio value:' çıktısı olmalı
    out = capsys.readouterr().out
    assert "Final portfolio value:" in out
