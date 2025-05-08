# tests/test_minimal_executor.py

from minimal_executor import Executor

def test_executor_execute_logs_and_returns_true(capsys):
    exec = Executor()
    result = exec.execute("BUY", {"symbol": "BTCUSDT", "qty": 0.1})
    assert result is True

    captured = capsys.readouterr().out
    assert "Executing action: BUY with data: {'symbol': 'BTCUSDT', 'qty': 0.1}" in captured
