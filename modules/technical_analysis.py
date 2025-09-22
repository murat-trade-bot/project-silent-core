"""
Module: technical_analysis.py
Provides functions to fetch market data (OHLCV) and compute technical indicators: RSI, MACD, ATR, momentum.
Includes robust error handling and logging.
"""
import requests
import random
import time
from typing import List, Tuple, Optional

from core.logger import BotLogger

logger = BotLogger()

def fetch_ohlcv_from_binance(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 100
) -> List[Tuple[float, float, float, float, float, float]]:
    """
    Binance Spot OHLCV verisi çeker. Rastgele gecikme ve hata toleransı ile stealth modda çalışır.
    User-Agent başlığı ve rate limit toleransı eklenmiştir.
    """
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +https://github.com/yourproject)"
    }
    try:
        # Rastgele gecikme ile bot davranışını gizle
        time.sleep(random.uniform(0.2, 1.2))
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 429:
            logger.warning("fetch_ohlcv_from_binance: Binance rate limit aşıldı (429). Kısa süre bekleniyor.")
            time.sleep(2)
            return []
        response.raise_for_status()
        data = response.json()
        # Veri formatı: [timestamp, open, high, low, close, volume, ...]
        ohlcv = [
            (
                float(item[0]), float(item[1]), float(item[2]),
                float(item[3]), float(item[4]), float(item[5])
            ) for item in data
        ]
        logger.info(f"Fetched {len(ohlcv)} OHLCV bars for {symbol}")
        return ohlcv
    except Exception as e:
        logger.error(f"fetch_ohlcv_from_binance error: {e}")
        return []

def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    RSI hesaplar. Hatalara karşı güvenli, minimum veri kontrolü içerir.
    """
    if len(prices) < period + 1:
        logger.warning("RSI: Yetersiz veri.")
        return []
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [max(delta, 0) for delta in deltas]
    losses = [abs(min(delta, 0)) for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi: List[float] = []
    for i in range(period, len(prices)-1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi.append(100 - (100 / (1 + rs)))
    # Warmup döneminde eksik değerler için None bırakmayı tercih edebiliriz;
    # burada basitçe hesaplananları döndürüyoruz, signals tarafı None filtreleyecek.
    return rsi

def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    EMA hesaplar. Hatalara karşı güvenli.
    """
    if not prices or period <= 0 or len(prices) < period:
        logger.warning("EMA: Yetersiz veri veya yanlış parametre.")
        return []
    ema = [sum(prices[:period]) / period]
    k = 2 / (period + 1)
    for price in prices[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[float], List[float], List[float]]:
    """
    MACD ve sinyal çizgisi hesaplar. Hatalara karşı güvenli.
    """
    if len(prices) < slow_period + signal_period:
        logger.warning("MACD: Yetersiz veri.")
        return [], [], []
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    min_len = min(len(ema_fast), len(ema_slow))
    macd_line = [f - s for f, s in zip(ema_fast[-min_len:], ema_slow[-min_len:])]
    signal_line = calculate_ema(macd_line, signal_period)
    # macd, macd_signal hesaplanıyor
    macd_hist = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, macd_hist

def calculate_atr(
    ohlcv: List[Tuple[float, float, float, float, float, float]],
    period: int = 14
) -> Optional[float]:
    """
    ATR hesaplar. Hatalara karşı güvenli.
    """
    if len(ohlcv) < period + 1:
        logger.warning("ATR: Yetersiz veri.")
        return None
    trs = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]
        prev_close = ohlcv[i-1][4]
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else None

def calculate_momentum(prices: List[float], period: int = 10) -> List[float]:
    """
    Momentum hesaplar. Hatalara karşı güvenli.
    """
    if len(prices) < period + 1:
        logger.warning("Momentum: Yetersiz veri.")
        return []
    return [prices[i] - prices[i - period] for i in range(period, len(prices))]

def calculate_bbands(prices: List[float], period: int = 20, std_mult: float = 2.0) -> Tuple[List[float], List[float], List[float]]:
    """Basit Bollinger Bantları (SMA±std*mult)."""
    if len(prices) < period:
        logger.warning("BBANDS: Yetersiz veri.")
        return [], [], []
    mids, uppers, lowers = [], [], []
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        mid = sum(window) / period
        var = sum((p - mid) ** 2 for p in window) / period
        std = var ** 0.5
        mids.append(mid)
        uppers.append(mid + std_mult * std)
        lowers.append(mid - std_mult * std)
    return mids, uppers, lowers

def calculate_vwap(ohlcv: List[Tuple[float, float, float, float, float, float]], lookback: int = 50) -> Optional[float]:
    """VWAP ~ sum(price*volume)/sum(volume) son lookback bar için."""
    if not ohlcv:
        return None
    data = ohlcv[-lookback:] if len(ohlcv) >= lookback else ohlcv
    sum_pv = 0.0
    sum_v = 0.0
    for _, _o, _h, _l, c, v in data:
        p = float(c)
        vol = float(v)
        sum_pv += p * vol
        sum_v += vol
    if sum_v <= 0:
        return None
    return sum_pv / sum_v

def calculate_adx(ohlcv: List[Tuple[float, float, float, float, float, float]], period: int = 14) -> Optional[float]:
    """Wilder ADX(14) basit uygulama, son değeri döndürür."""
    if len(ohlcv) < period + 1:
        logger.warning("ADX: Yetersiz veri.")
        return None
    highs = [x[2] for x in ohlcv]
    lows = [x[3] for x in ohlcv]
    closes = [x[4] for x in ohlcv]

    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, len(ohlcv)):
        high, low, prev_close = highs[i], lows[i], closes[i - 1]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)

    def wilder_smooth(vals: List[float], p: int) -> List[float]:
        if len(vals) < p:
            return []
        smoothed = [sum(vals[:p])]
        for v in vals[p:]:
            smoothed.append(smoothed[-1] - (smoothed[-1] / p) + v)
        return smoothed

    trn = wilder_smooth(trs, period)
    pDM = wilder_smooth(plus_dm, period)
    mDM = wilder_smooth(minus_dm, period)
    if not trn or not pDM or not mDM:
        return None
    di_plus = [100 * (p / t) if t else 0.0 for p, t in zip(pDM, trn)]
    di_minus = [100 * (m / t) if t else 0.0 for m, t in zip(mDM, trn)]
    dx = [100 * (abs(dp - dm) / (dp + dm)) if (dp + dm) else 0.0 for dp, dm in zip(di_plus, di_minus)]
    adx_series = wilder_smooth(dx, period)
    if not adx_series:
        return None
    return adx_series[-1] / period  # wilder smoothing scale back
