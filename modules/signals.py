# signals.py
# Strateji sinyal fonksiyonları

from utils.signal_utils import calculate_rsi, calculate_ema

# 1. Al sinyali: 3 yeşil mum ve hacim artışı
def detect_buy_signal(candles_1m, candles_3m, volumes):
    if all(candle['close'] > candle['open'] for candle in candles_1m[-3:]):
        if volumes[-1] > volumes[-2] > volumes[-3]:
            return True
    return False

# 2. Sat sinyali: 3 kırmızı mum ve hacim düşüşü
def detect_sell_signal(candles_1m, candles_3m, volumes):
    if all(candle['close'] < candle['open'] for candle in candles_1m[-3:]):
        if volumes[-1] < volumes[-2] < volumes[-3]:
            return True
    return False

# 3. Trend dönüşü ve güçlü sat sinyali
def detect_trend_reversal_sell(candles_1m, rsi_values, ema_9, ema_21):
    if candles_1m[-4]['close'] > candles_1m[-4]['open'] and candles_1m[-3]['close'] > candles_1m[-3]['open']:
        if candles_1m[-1]['close'] < candles_1m[-1]['open']:
            if rsi_values[-1] < rsi_values[-2] and rsi_values[-2] < rsi_values[-3]:
                if ema_9[-1] < ema_21[-1]:
                    return True
    return False
