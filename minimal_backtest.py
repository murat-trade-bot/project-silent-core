# minimal_backtest.py

from minimal_strategy import Strategy
from minimal_executor import Executor

def run_backtest() -> float:
    """
    Basit bir backtest simülasyonu:
      1. İki fiyat barından geçerek stratejiyi uygular
      2. Executor ile her adımı loglar
      3. Son portföy değerini hesaplayıp döner
    """
    cash = 100.0
    position = 0.0
    prices = [10.0, 12.0]

    strat = Strategy()
    execr = Executor()

    for price in prices:
        action = strat.get_action({'price': price})
        if action == 'BUY' and cash > 0:
            position = cash / price
            cash = 0.0
        elif action == 'SELL' and position > 0:
            cash = position * price
            position = 0.0
        execr.execute(action, {'price': price, 'cash': cash, 'position': position})

    final_value = cash if cash > 0 else position * prices[-1]
    print(f"Final portfolio value: {final_value}")
    return final_value

if __name__ == "__main__":
    run_backtest()
