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

def detect_buy_signal(candles: List[dict], volumes: List[float],
                      rsi: Optional[List[float]] = None, ema9: Optional[List[float]] = None, ema21: Optional[List[float]] = None,
                      period: int = 1, position_open: bool = False) -> bool:
    now = time.time()
    if position_open or now - _last_signal_time['buy'] < _DEBOUNCE_SEC:
        return False
    if len(candles) < 3 or len(volumes) < 3:
        return False
    # Periyot desteği: 1m, 3m, 5m
    if period > 1:
        candles = candles[-3*period:][::period]
        volumes = volumes[-3*period:][::period]
    if all(c['close'] > c['open'] for c in candles[-3:]) and _vol_filter(volumes, 'up'):
        # Opsiyonel RSI/EMA filtresi
        if rsi and len(rsi) >= 3 and not (rsi[-1] > 70):
            pass
        if ema9 and ema21 and ema9[-1] > ema21[-1]:
            pass
        _last_signal_time['buy'] = now
        return True
    return False

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
    ]
    volumes = [100, 120, 150]
    assert detect_buy_signal(candles, volumes, period=1, position_open=False) == True
    assert detect_buy_signal(candles, [100, 100, 100], period=1, position_open=False) == False
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
