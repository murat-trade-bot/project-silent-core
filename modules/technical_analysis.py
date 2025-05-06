"""
Module: technical_analysis.py
Provides functions to fetch market data (OHLCV) and compute technical indicators: RSI, MACD, ATR, momentum.
Includes robust error handling and logging.
"""
import requests
import math
from typing import List, Tuple, Optional

from core.logger import BotLogger

logger = BotLogger()


def fetch_ohlcv_from_binance(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 100
) -> List[Tuple[float, float, float, float, float, float]]:
    """
    Fetch OHLCV data from Binance REST API.
    Returns list of tuples: (open_time_ms, open, high, low, close, volume).
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ohlcv = []
        for c in data:
            ohlcv.append((
                float(c[0]),  # open time
                float(c[1]),  # open price
                float(c[2]),  # high price
                float(c[3]),  # low price
                float(c[4]),  # close price
                float(c[5])   # volume
            ))
        return ohlcv
    except requests.RequestException as e:
        logger.error(f"[TA] fetch_ohlcv error for {symbol}/{interval}: {e}")
        return []
    except (ValueError, KeyError) as e:
        logger.error(f"[TA] fetch_ohlcv parsing error for {symbol}/{interval}: {e}")
        return []


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index (RSI) for a list of prices.
    Returns list of RSI values corresponding to each period window.
    """
    if not prices or len(prices) <= period:
        return []
    gains = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
    losses = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]

    # First average gain/loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values: List[float] = []
    # First RSI value
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    rsi_values.append(rsi)

    # Subsequent RSI values
    for i in range(period, len(prices)-1):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)

    return rsi_values


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average (EMA) for a list of prices.
    Returns EMA list aligned with input data from index 'period'-1 onwards.
    """
    if not prices or len(prices) < period:
        return []
    sma = sum(prices[:period]) / period
    ema_vals = [sma]
    multiplier = 2 / (period + 1)
    for price in prices[period:]:
        ema_vals.append((price - ema_vals[-1]) * multiplier + ema_vals[-1])
    return ema_vals


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[float], List[float]]:
    """
    Calculate MACD line and signal line. Returns (macd_line, signal_line).
    """
    if not prices or len(prices) < slow_period:
        return [], []
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    # Align lengths
    length = min(len(fast_ema), len(slow_ema))
    fast_ema = fast_ema[-length:]
    slow_ema = slow_ema[-length:]
    macd_line = [fast_ema[i] - slow_ema[i] for i in range(length)]
    signal_line = calculate_ema(macd_line, signal_period)
    # Align MACD to signal
    length2 = min(len(macd_line), len(signal_line))
    return macd_line[-length2:], signal_line[-length2:]


def calculate_atr(
    ohlcv: List[Tuple[float, float, float, float, float, float]],
    period: int = 14
) -> Optional[float]:
    """
    Calculate Average True Range (ATR) for given OHLCV data.
    Returns the ATR value for the most recent period.
    """
    if not ohlcv or len(ohlcv) < period + 1:
        return None
    trs: List[float] = []
    for i in range(1, len(ohlcv)):
        _, high, low, prev_close, _, _ = ohlcv[i][0], ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4], ohlcv[i][4], ohlcv[i][5]
        # Note: indices: ohlcv[i] = (timestamp, open, high, low, close, volume)
        high_price = ohlcv[i][2]
        low_price = ohlcv[i][3]
        prev_close_price = ohlcv[i-1][4]
        tr = max(
            high_price - low_price,
            abs(high_price - prev_close_price),
            abs(low_price - prev_close_price)
        )
        trs.append(tr)
    # First ATR
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def calculate_momentum(prices: List[float], period: int = 10) -> Optional[float]:
    """
    Calculate momentum as difference between current and 'period' bars ago price.
    """
    if not prices or len(prices) < period + 1:
        return None
    return prices[-1] - prices[-period-1]
