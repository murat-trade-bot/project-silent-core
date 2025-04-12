def detect_domino_effect(prices):
    if len(prices) < 10:
        return False
    change = prices[-1] - prices[-10]
    if change < -50 or change > 50:
        return True
    return False 