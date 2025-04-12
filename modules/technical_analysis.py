import requests
import numpy as np

def fetch_ohlcv_from_binance(symbol="BTCUSDT", interval="1h", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        ohlcv = []
        for c in data:
            ohlcv.append((
                float(c[0]),
                float(c[1]),
                float(c[2]),
                float(c[3]),
                float(c[4]),
                float(c[5])
            ))
        return ohlcv
    except Exception as e:
        print("[TA] Veri çekilemedi:", e)
        return []

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return []
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi_list = [100 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))]
    for i in range(period, len(prices) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_list.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi_list.append(100 - (100 / (1 + rs)))
    return rsi_list

def calculate_ema(prices, period):
    if len(prices) < period:
        return []
    sma = sum(prices[:period]) / period
    ema_vals = [sma]
    multiplier = 2 / (period + 1)
    for i in range(period, len(prices)):
        ema_vals.append((prices[i] - ema_vals[-1]) * multiplier + ema_vals[-1])
    return ema_vals

def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    if len(prices) < slow_period:
        return [], []
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    if len(fast_ema) > len(slow_ema):
        fast_ema = fast_ema[-len(slow_ema):]
    elif len(slow_ema) > len(fast_ema):
        slow_ema = slow_ema[-len(fast_ema):]
    macd_line = np.subtract(fast_ema, slow_ema)
    signal_line = calculate_ema(macd_line, signal_period)
    if len(signal_line) < len(macd_line):
        macd_line = macd_line[-len(signal_line):]
    return macd_line, signal_line

def calculate_atr(ohlcv, period=14):
    if len(ohlcv) < period + 1:
        return None
    trs = []
    for i in range(1, len(ohlcv)):
        prev = ohlcv[i - 1]
        curr = ohlcv[i]
        high, low, prev_close = curr[2], curr[3], prev[4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    atr = sum(trs[:period]) / period
    atr_values = [atr]
    for i in range(period, len(trs)):
        atr_values.append((atr_values[-1] * (period - 1) + trs[i]) / period)
    return atr_values[-1] if atr_values else None

def calculate_momentum(prices, period=10):
    if len(prices) < period + 1:
        return None
    return prices[-1] - prices[-period - 1] 