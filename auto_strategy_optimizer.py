import csv

def optimize_strategy(trade_history_file):
    best_params = {}
    best_roi = -float("inf")
    for sl in [0.005, 0.01, 0.015]:
        for tp in [0.01, 0.02, 0.03]:
            roi = simulate_roi(trade_history_file, sl, tp)
            if roi > best_roi:
                best_roi = roi
                best_params = {"STOP_LOSS_RATIO": sl, "TAKE_PROFIT_RATIO": tp}
    return {"optimal_params": best_params, "ROI": best_roi}

def simulate_roi(trade_history_file, sl, tp):
    total = 0
    count = 0
    with open(trade_history_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            price = float(row["price"])
            total += (tp - sl) * price * 0.0001
            count += 1
    return total / count if count else 0 