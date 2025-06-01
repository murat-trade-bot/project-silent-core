from minimal_strategy import Strategy
from modules.period_manager import get_current_period, get_daily_target
from datetime import datetime

def test_daily_target():
    s = Strategy()
    test_cases = [
        (datetime(2024, 4, 25), 231, "1. Dönem BAŞLANGIÇ"),
        (datetime(2024, 6, 25), 3200, "1. Dönem SON"),
        (datetime(2024, 6, 26), 3234, "2. Dönem BAŞLANGIÇ"),
        (datetime(2024, 8, 26), 38000, "2. Dönem SON"),
        (datetime(2024, 8, 27), 38808, "3. Dönem BAŞLANGIÇ"),
        (datetime(2024, 10, 27), 380000, "3. Dönem SON"),
        (datetime(2024, 10, 28), 150000, "4. Dönem BAŞLANGIÇ"),
        (datetime(2024, 12, 28), 890000, "4. Dönem SON"),
        (datetime(2024, 12, 29), 200000, "5. Dönem BAŞLANGIÇ"),
        (datetime(2025, 2, 1), 990000, "5. Dönem SON"),
        (datetime(2025, 2, 2), 250000, "6. Dönem BAŞLANGIÇ"),
        (datetime(2025, 4, 2), 1240000, "6. Dönem SON"),
    ]

    for today, balance, desc in test_cases:
        period = get_current_period(s.periods, today)
        daily_target = get_daily_target(s.periods, today=today, current_balance=balance)
        if period:
            print(f"{desc} | {period['name']} ({today.date()}): Günlük hedef kâr: {daily_target:.2f} USD (Bakiye: {balance})")
        else:
            print(f"{desc} | {today.date()}: Dönem dışında")

if __name__ == "__main__":
    test_daily_target()