# -*- coding: utf-8 -*-
"""
modules/playbook.py
%3.13 Günlük Hedef playbook için rejim filtresi, sinyal ve pozisyon boyutlandırma yardımcıları.
"""
from __future__ import annotations

import os as _os
from typing import Dict, Any, List, Tuple, Optional

from modules.technical_analysis import calculate_ema, calculate_atr, calculate_bbands, calculate_vwap, calculate_adx


def regime_on(ohlcv_15m: List[Tuple[float, float, float, float, float, float]], adx_min: float = None) -> bool:
    """EMA20>EMA50 ve ADX14>threshold -> trend ON."""
    adx_thr = float(_os.getenv("TREND_ADX_MIN", "18")) if adx_min is None else float(adx_min)
    closes = [c[4] for c in ohlcv_15m]
    ema20 = calculate_ema(closes, 20) or []
    ema50 = calculate_ema(closes, 50) or []
    if not ema20 or not ema50:
        return False
    on = (ema20[-1] > ema50[-1])
    adx = calculate_adx(ohlcv_15m, period=14)
    if adx is None:
        return False
    return bool(on and (adx >= adx_thr))


def bb_squeeze_breakout_signal(ohlcv_1m: List[Tuple[float, float, float, float, float, float]], vol_mult: float = 2.0) -> bool:
    """BB daralma (bant genişliği düşüklüğü) sonrası üst bant kırılımı ve fiyat VWAP üstünde ise True."""
    closes = [c[4] for c in ohlcv_1m]
    mids, uppers, lowers = calculate_bbands(closes, period=20, std_mult=vol_mult)
    if not uppers:
        return False
    bw = (uppers[-1] - lowers[-1]) / mids[-1] if mids[-1] else 0.0
    # Daralma eşiği: son 50 barın alt %20 genişliği gibi basit bir koşul
    widths = []
    for i in range(len(mids)):
        if mids[i]:
            widths.append((uppers[i] - lowers[i]) / mids[i])
    if not widths:
        return False
    thresh = sorted(widths)[max(0, int(len(widths) * 0.2) - 1)]
    # Breakout: son close üst bandın hafif üstünde
    breakout = closes[-1] > uppers[-1] * 1.0005
    vwap = calculate_vwap(ohlcv_1m, lookback=50) or 0
    above_vwap = closes[-1] >= vwap
    return bool(bw <= thresh and breakout and above_vwap)


def pullback_signal(ohlcv_1m: List[Tuple[float, float, float, float, float, float]]) -> bool:
    """EMA20 pullback + RSI(2)<=10 ve geri dönüş mumu."""
    closes = [c[4] for c in ohlcv_1m]
    ema20 = calculate_ema(closes, 20)
    if not ema20:
        return False
    try:
        # RSI(2)
        from utils.signal_utils import calculate_rsi
        rsi2_list = calculate_rsi(closes, period=2)
        rsi2 = rsi2_list[-1] if rsi2_list else 50
    except Exception:
        rsi2 = 50
    # Geri dönüş mumu: son bar yeşil ve önceki kırmızıya karşı dönüş
    last_green = closes[-1] > ohlcv_1m[-1][1]
    touched_ema = closes[-1] >= ema20[-1] * 0.998 and closes[-2] <= ema20[-2] * 1.002
    return bool(last_green and rsi2 <= 10 and touched_ema)


def orderbook_imbalance_ok(book: Dict[str, Any], min_ratio: float = None) -> bool:
    """Basit LOB dengesizliği: toplam bid_qty / (bid_qty+ask_qty) >= threshold."""
    thr = float(_os.getenv("ORDERBOOK_IMBALANCE_MIN", "0.55")) if min_ratio is None else float(min_ratio)
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    def _sum_qty(levels, n=5):
        s = 0.0
        for i, x in enumerate(levels[:n]):
            try:
                s += float(x[1])
            except Exception:
                try:
                    s += float(x[1])
                except Exception:
                    pass
        return s
    bsum = _sum_qty(bids, 5)
    asum = _sum_qty(asks, 5)
    if bsum + asum <= 0:
        return False
    ratio = bsum / (bsum + asum)
    return bool(ratio >= thr)

from typing import Tuple as _Tuple  # local alias (mevcut global import zaten var)

def _calc_atr14(ohlcv, period=14) -> float | None:
    try:
        if not ohlcv or len(ohlcv) < period + 1:
            return None
        trs = []
        for i in range(1, len(ohlcv)):
            h1, l1, c0 = float(ohlcv[i][2]), float(ohlcv[i][3]), float(ohlcv[i-1][4])
            tr = max(h1 - l1, abs(h1 - c0), abs(l1 - c0))
            trs.append(tr)
        if len(trs) < period:
            return None
        return sum(trs[-period:]) / period
    except Exception:
        return None

def compute_stop_and_size(entry_price: float,
                          ohlcv_1m,
                          equity: float,
                          risk_pct: float = 0.008,
                          atr_period: int = 14,
                          atr_mult: float = 1.8) -> _Tuple[float | None, float]:
    """
    entry_price: anlık fiyat, equity: USDT, risk_pct: işlem başına risk yüzdesi
    Dönüş: (stop_price, qty_base)
    """
    try:
        entry = float(entry_price)
        eq = float(equity or 0.0)
        if entry <= 0.0 or eq <= 0.0 or risk_pct <= 0.0:
            return (None, 0.0)

        atr = _calc_atr14(ohlcv_1m, period=atr_period)
        stop_distance = (atr_mult * atr) if atr and atr > 0 else max(entry * 0.004, 0.002 * entry)
        stop_price = max(0.0, entry - stop_distance)

        risk_amount = eq * float(risk_pct)
        denom = max(entry - stop_price, entry * 0.002)
        qty = risk_amount / denom
        return (stop_price, max(0.0, qty))
    except Exception:
        return (None, 0.0)
