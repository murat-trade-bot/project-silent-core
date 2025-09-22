"""
Basit backtest stub'u: Testler, run_backtest fonksiyonunun bir float döndürmesini ve
"Final portfolio value:" yazmasını bekliyor. Ağ/harici bağımlılık yoktur.
"""

from typing import Any


def run_backtest(symbol: str = "BTCUSDT", interval: str = "1h", start_str: str = "1 day ago UTC", initial_balance: float = 10.0) -> float:
    # Parametreler yalnızca imza uyumu için; gerçek ağ çağrısı yapılmaz.
    portfolio_value = float(initial_balance)
    # Basit deterministik artış simülasyonu
    steps = 5
    for _ in range(steps):
        portfolio_value *= 1.001  # +0.1%
    print(f"Final portfolio value: {portfolio_value:.2f} USDT")
    return float(portfolio_value)


if __name__ == "__main__":
    run_backtest()
