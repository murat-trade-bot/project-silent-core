# signals.py
# Strateji sinyal fonksiyonları

from utils.signal_utils import calculate_rsi, calculate_ema
import os


# None güvenli son N float değerini alma yardımcı fonksiyonu
def _last_n_floats(seq, n):
    if not seq:
        return []
    cleaned = [float(x) for x in seq if x is not None]
    return cleaned[-n:]

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
    # Guard: RSI None olabilir
    if rsi_values is None:
        return False
    rsi = _last_n_floats(rsi_values, 3)
    if len(rsi) < 3:
        return False

    # EMA girişleri dizi/tekil olabilir; son değeri çek ve None’a karşı koru
    if ema_9 is None or ema_21 is None:
        return False
    ema9 = ema_9[-1] if isinstance(ema_9, (list, tuple)) else ema_9
    ema21 = ema_21[-1] if isinstance(ema_21, (list, tuple)) else ema_21
    if ema9 is None or ema21 is None:
        return False

    if candles_1m[-4]['close'] > candles_1m[-4]['open'] and candles_1m[-3]['close'] > candles_1m[-3]['open']:
        if candles_1m[-1]['close'] < candles_1m[-1]['open']:
            # RSI düşüş momentumu ve kısa EMA uzun EMA altında
            return (rsi[-1] < rsi[-2] < rsi[-3]) and (float(ema9) < float(ema21))
    return False


def safe_exit_signal(candles_1m=None, rsi_values=None, ema_9=None, ema_21=None):
    """
    None/ısınma dönemlerinde patlamadan 'sat' sinyali üret; yoksa False.
    """
    try:
        # RSI güvenli al
        def _last_n_floats(seq, n):
            if not seq:
                return []
            cleaned = [float(x) for x in seq if x is not None]
            return cleaned[-n:]

        rsi = _last_n_floats(rsi_values, 3)
        if len(rsi) < 3:
            return False

        e9 = ema_9[-1] if isinstance(ema_9, (list, tuple)) else ema_9
        e21 = ema_21[-1] if isinstance(ema_21, (list, tuple)) else ema_21
        if e9 is None or e21 is None:
            return False

        # Mevcut fonksiyon varsa onu kullan; yoksa basit kural uygula
        try:
            from .signals import detect_trend_reversal_sell as _impl  # self import safe
            return bool(_impl(candles_1m, rsi_values, ema_9, ema_21))
        except Exception:
            # Basit "sat" mantığı: RSI düşüş momentumu + kısa EMA uzun EMA altında
            return (rsi[-1] < rsi[-2] < rsi[-3]) and (float(e9) < float(e21))
    except Exception:
        return False


def micro_entry_signal(ohlcv_1m=None, vwap=None, volatility=None):
    """
    Çok basit ve hızlı bir entry: 
    - Son kapanış > önceki kapanış
    - VWAP eğimi pozitif (son > önce)
    - 1m volatility >= MICRO_ENTRY_MIN_VOLATILITY
    """
    try:
        if not ohlcv_1m or len(ohlcv_1m) < 3:
            return False
        close = [c[4] for c in ohlcv_1m if c and len(c) >= 5]
        if len(close) < 3:
            return False
        last_up = close[-1] > close[-2]
        vwap_ok = False
        if isinstance(vwap, (list, tuple)) and len(vwap) >= 2:
            vwap_ok = (vwap[-1] is not None and vwap[-2] is not None and vwap[-1] > vwap[-2])
        elif isinstance(vwap, (int, float)):
            vwap_ok = True
        vol_ok = (volatility or 0.0) >= float(os.getenv("MICRO_ENTRY_MIN_VOLATILITY", "0.0009"))
        return bool(last_up and vwap_ok and vol_ok)
    except Exception:
        return False
