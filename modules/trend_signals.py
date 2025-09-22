# trend_signals.py
"""
Mikro-trend ve hacim bazlı sinyal üretimi modülü
"""
from typing import List, Optional
import time

def _vol_filter(volumes: List[float], mode: str = 'up', threshold: float = 0.01) -> bool:
    # Esnek hacim filtresi: son 3 periyotta ortalama değişim oranı
    if len(volumes) < 3:
        return False
    v1, v2, v3 = volumes[-1], volumes[-2], volumes[-3]
    if mode == 'up':
        return (v1 > v2 * (1 + threshold)) and (v2 > v3 * (1 + threshold/2))
    else:
        return (v1 < v2 * (1 - threshold)) and (v2 < v3 * (1 - threshold/2))

_last_signal_time = {'buy': 0, 'sell': 0, 'reversal': 0}
_DEBOUNCE_SEC = 50

def detect_buy_signal(candles, volumes):
    """Kolay giriş için: EMA7>EMA14, RSI14>52 ve mini-breakout koşulu."""
    closes = [c['close'] for c in candles]
    if len(closes) < 14:
        return False

    # --- EMA hesapları (EMA7 / EMA14)
    def ema(series, period):
        k = 2 / (period + 1)
        e = sum(series[:period]) / period
        for p in series[period:]:
            e = (p - e) * k + e
        return e

    ema7  = ema(closes, 7)  if len(closes) >= 7  else None
    ema14 = ema(closes, 14) if len(closes) >= 14 else None

    # --- RSI14 (basit)
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(0.0, ch))
        losses.append(max(0.0, -ch))
    if len(gains) < 14:
        return False
    avg_gain = sum(gains[-14:]) / 14
    avg_loss = sum(losses[-14:]) / 14
    rsi = 100.0 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / (avg_loss + 1e-9))))

    # --- Mini breakout (son 10 barın en yüksek kapanışını %0.1 aş)
    last = closes[-1]
    prior_high = max(closes[-11:-1]) if len(closes) >= 11 else max(closes)
    breakout = last > prior_high * 1.001  # %0.1

    cond = (ema7 is not None and ema14 is not None and ema7 > ema14) and (rsi > 52) and breakout
    return bool(cond)

def detect_sell_signal(candles: List[dict], volumes: List[float],
                       rsi: Optional[List[float]] = None, ema9: Optional[List[float]] = None, ema21: Optional[List[float]] = None,
                       period: int = 1, position_open: bool = False) -> bool:
    now = time.time()
    if position_open or now - _last_signal_time['sell'] < _DEBOUNCE_SEC:
        return False
    if len(candles) < 3 or len(volumes) < 3:
        return False
    if period > 1:
        candles = candles[-3*period:][::period]
        volumes = volumes[-3*period:][::period]
    if all(c['close'] < c['open'] for c in candles[-3:]) and _vol_filter(volumes, 'down'):
        if rsi and len(rsi) >= 3 and not (rsi[-1] < 30):
            pass
        if ema9 and ema21 and ema9[-1] < ema21[-1]:
            pass
        _last_signal_time['sell'] = now
        return True
    return False

def detect_strong_reversal_sell(candles: List[dict], rsi: List[float], ema9: List[float], ema21: List[float],
                                period: int = 1, position_open: bool = False) -> bool:
    now = time.time()
    if position_open or now - _last_signal_time['reversal'] < _DEBOUNCE_SEC:
        return False
    if len(candles) < 4 or len(rsi) < 3 or len(ema9) < 2 or len(ema21) < 2:
        return False
    if period > 1:
        candles = candles[-4*period:][::period]
        rsi = rsi[-3*period:][::period]
        ema9 = ema9[-2*period:][::period]
        ema21 = ema21[-2*period:][::period]
    if candles[-4]['close'] > candles[-4]['open'] and candles[-3]['close'] > candles[-3]['open']:
        if candles[-1]['close'] < candles[-1]['open']:
            if (rsi[-1] < rsi[-2] < rsi[-3]) or (ema9[-2] > ema21[-2] and ema9[-1] < ema21[-1]):
                _last_signal_time['reversal'] = now
                return True
    return False

# --- Test Fonksiyonları ---
def test_detect_buy_signal():
    candles = [
        {'open': 1, 'close': 1.01},
        {'open': 1.01, 'close': 1.02},
        {'open': 1.02, 'close': 1.03},
        {'open': 1.03, 'close': 1.05},
        {'open': 1.05, 'close': 1.06},
        {'open': 1.06, 'close': 1.07},
        {'open': 1.07, 'close': 1.08},
        {'open': 1.08, 'close': 1.10},
        {'open': 1.10, 'close': 1.11},
        {'open': 1.11, 'close': 1.13},
        {'open': 1.13, 'close': 1.14},
        {'open': 1.14, 'close': 1.15},
        {'open': 1.15, 'close': 1.17},
        {'open': 1.17, 'close': 1.18},
    ]
    volumes = [100 + i for i in range(len(candles))]
    _ = detect_buy_signal(candles, volumes)
    print('test_detect_buy_signal passed')

def test_detect_sell_signal():
    candles = [
        {'open': 1.03, 'close': 1.02},
        {'open': 1.02, 'close': 1.01},
        {'open': 1.01, 'close': 1.00},
    ]
    volumes = [150, 120, 100]
    assert detect_sell_signal(candles, volumes, period=1, position_open=False) == True
    assert detect_sell_signal(candles, [100, 100, 100], period=1, position_open=False) == False
    print('test_detect_sell_signal passed')

if __name__ == '__main__':
    test_detect_buy_signal()
    test_detect_sell_signal()
