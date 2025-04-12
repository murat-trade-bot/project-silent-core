import csv

def analyze_performance(trade_history_file):
    trades = []
    with open(trade_history_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
    if not trades:
        return {}
    initial_balance = float(trades[0]["balance"])
    final_balance = float(trades[-1]["balance"])
    ROI = (final_balance - initial_balance) / initial_balance * 100
    win_trades = 0
    total_trades = 0
    balance_history = []
    for row in trades:
        total_trades += 1
        balance_history.append(float(row["balance"]))
        if row["action"] == "SELL" and float(row["price"]) > 0:
            win_trades += 1
    WinRate = (win_trades / total_trades) * 100 if total_trades else 0
    max_drawdown = 0
    peak = balance_history[0]
    for b in balance_history:
        if b > peak:
            peak = b
        drawdown = (peak - b) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return {
        "ROI": round(ROI, 2),
        "WinRate": round(WinRate, 2),
        "MaxDrawdown": round(max_drawdown, 2)
    } 