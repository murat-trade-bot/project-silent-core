# tests/test_backtest.py

from backtest import run_backtest

def test_backtest_runs_and_outputs_value(capsys):
    # Hata vermeden float değer dönmeli
    val = run_backtest(symbol="BTCUSDT", interval="1h", start_str="1 day ago UTC", initial_balance=10.0)
    assert isinstance(val, float)

    # Konsolda çıktıyı doğrula
    out = capsys.readouterr().out
    assert "Final portfolio value:" in out
