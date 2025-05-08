# tests/test_minimal_strategy.py

from minimal_strategy import Strategy

def test_strategy_always_hold():
    s = Strategy()
    assert s.get_action({}) == "HOLD"
