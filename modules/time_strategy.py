from datetime import datetime

def get_current_strategy_mode():
    now = datetime.utcnow()
    hour = now.hour
    if 8 <= hour < 10:
        return "aggressive"
    elif 22 <= hour or hour < 2:
        return "passive"
    return "neutral"
