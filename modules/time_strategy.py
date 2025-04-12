from datetime import datetime

def get_current_strategy_mode():
    now = datetime.utcnow()
    hour = now.hour
    wd = now.weekday()
    day = now.day
    if now.month == 12 and now.day == 25:
        return "auto_close"
    if 8 <= hour < 10:
        return "aggressive"
    elif 22 <= hour or hour < 2:
        return "passive"
    if wd == 0:
        return "defensive"
    elif wd == 4:
        return "volatility_focus"
    elif wd in [5, 6]:
        return "weekend_mode"
    if day <= 5:
        return "entry_focus"
    elif 25 <= day <= 31:
        return "exit_focus"
    return "neutral"
