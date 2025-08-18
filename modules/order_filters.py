# -*- coding: utf-8 -*-
"""
modules/order_filters.py
Project Silent Core – Emir Öncesi Piyasa/Kontrol Fonksiyonları (stateless)

Bu modül emir ATMADAN ÖNCE yapılacak ölçüm ve kontrolleri içerir:
- Anlık spread hesaplama
- Emir büyüklüğüne göre seviye-seviye VWAP ve beklenen slippage hesaplama
- Likidite/etki (impact) kontrolü: hedef notional, belirlenen etki eşiği içinde doluyor mu?
- Komisyon (taker fee) ve toplam maliyet (fee + slippage) hesaplama

Notlar:
- Bu modül STATELESS olmalı; risk/politika kararları RiskManager'da tutulur.
- Buradaki fonksiyonlar sadece ölçer ve öneri/sonuç döndürür.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Optional, Any

try:
    # Opsiyonel: ayarlardan eşik/varsayılanları al
    from config import settings
    _HAS_SETTINGS = True
except Exception:
    _HAS_SETTINGS = False


# ---- Varsayılan eşikler (settings yoksa) ----
DEFAULT_TAKER_FEE = float(getattr(settings, "DEFAULT_TAKER_FEE", 0.001)) if _HAS_SETTINGS else 0.001  # %0.1
MAX_SPREAD_PCT    = float(getattr(settings, "MAX_SPREAD_PCT", 0.003))     if _HAS_SETTINGS else 0.003 # %0.3
MAX_IMPACT_PCT    = float(getattr(settings, "MAX_IMPACT_PCT", 0.003))     if _HAS_SETTINGS else 0.003 # %0.3
SLIPPAGE_LIMIT    = float(getattr(settings, "SLIPPAGE_LIMIT", 0.005))     if _HAS_SETTINGS else 0.005 # %0.5


# ==========================
# Yardımcı: Order Book parsers
# ==========================
def _to_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def normalize_book(book: Dict[str, Any]) -> Dict[str, List[Tuple[float, float]]]:
    """
    Binance order_book formatını float'a çevirir.
    Input: {"bids": [["price","qty"],...], "asks":[["price","qty"],...]}
    Output: {"bids":[(p,q),...], "asks":[(p,q),...]}
    """
    bids = [( _to_float(p), _to_float(q) ) for p, q in (book.get("bids") or [])]
    asks = [( _to_float(p), _to_float(q) ) for p, q in (book.get("asks") or [])]
    return {"bids": bids, "asks": asks}


def best_bid_ask(book: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    b = book.get("bids") or []
    a = book.get("asks") or []
    bid = b[0][0] if b else None
    ask = a[0][0] if a else None
    return bid, ask


def spread_pct(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if bid and ask and bid > 0:
        return (ask - bid) / bid
    return None


# ==========================
# VWAP & Slippage
# ==========================
def vwap_for_notional(levels: List[Tuple[float, float]], target_usdt: float, side: str) -> Tuple[Optional[float], float, float, int]:
    """
    Hedef notional (USDT) için seviye-seviye doldurma yaparak VWAP hesaplar.
    levels: BUY için asks, SELL için bids
    target_usdt: doldurmak istenen toplam USDT
    side: "BUY" | "SELL"
    Returns:
        vwap_price (float | None)
        filled_usdt (float)
        used_qty (float)           # toplam base miktar
        levels_used (int)
    """
    if not levels or target_usdt <= 0:
        return None, 0.0, 0.0, 0

    remaining = float(target_usdt)
    sum_notional = 0.0
    sum_qty = 0.0
    used = 0

    for price, qty in levels:
        if remaining <= 0:
            break
        px = float(price); q = float(qty)
        if px <= 0.0 or q <= 0.0:
            continue

        # bu seviyeden kaç USDT'lik doldurabiliriz?
        level_notional = px * q
        take_usdt = min(remaining, level_notional)
        take_qty = take_usdt / px

        sum_notional += take_qty * px
        sum_qty += take_qty
        remaining -= take_usdt
        used += 1

    filled_usdt = target_usdt - remaining
    if sum_qty <= 0:
        return None, 0.0, 0.0, used

    vwap = sum_notional / sum_qty
    return vwap, filled_usdt, sum_qty, used


def estimate_slippage_from_book(side: str, size_usdt: float, book: Dict[str, Any]) -> Dict[str, Any]:
    """
    Emir büyüklüğüne göre anlık order book üzerinden beklenen slippage ve VWAP hesaplar.
    Returns dict:
      {
        "ok": bool,                        # hesap yapılabildi mi
        "vwap": float | None,
        "slippage_pct": float | None,      # referans en iyi fiyat ile VWAP farkı (pozitif)
        "filled_usdt": float,
        "levels_used": int,
        "insufficient_liquidity": bool,
        "ref_price": float | None          # BUY: best ask, SELL: best bid
      }
    """
    side = side.upper()
    nb = normalize_book(book)

    bids, asks = nb["bids"], nb["asks"]
    bid, ask = best_bid_ask(nb)

    if side == "BUY":
        ref = ask
        levels = asks
    else:
        side = "SELL"
        ref = bid
        levels = bids

    if ref is None or not levels:
        return {
            "ok": False, "vwap": None, "slippage_pct": None,
            "filled_usdt": 0.0, "levels_used": 0,
            "insufficient_liquidity": True, "ref_price": None
        }

    vwap, filled_usdt, used_qty, used_levels = vwap_for_notional(levels, size_usdt, side)

    if vwap is None:
        return {
            "ok": False, "vwap": None, "slippage_pct": None,
            "filled_usdt": 0.0, "levels_used": 0,
            "insufficient_liquidity": True, "ref_price": ref
        }

    # Slippage pozitif olarak raporlanır
    if side == "BUY":
        slip = max(0.0, (vwap - ref) / ref)
    else:
        slip = max(0.0, (ref - vwap) / ref)

    insufficient = filled_usdt + 1e-9 < size_usdt

    return {
        "ok": True,
        "vwap": vwap,
        "slippage_pct": slip,
        "filled_usdt": filled_usdt,
        "levels_used": used_levels,
        "insufficient_liquidity": insufficient,
        "ref_price": ref,
    }


# ==========================
# Likidite / Etki (Impact)
# ==========================
def check_liquidity_thresholds(side: str, size_usdt: float, book: Dict[str, Any], max_impact_pct: float = MAX_IMPACT_PCT) -> bool:
    """
    Hedef notional, belirlenen etki (%max_impact_pct) dahilinde dolabiliyor mu?
    BUY: fiyat best_ask * (1 + max_impact_pct) üzerine çıkmadan,
    SELL: fiyat best_bid * (1 - max_impact_pct) altına inmeden yeterli derinlik var mı?
    """
    nb = normalize_book(book)
    levels = nb["asks"] if side.upper() == "BUY" else nb["bids"]
    if not levels:
        return False

    best = levels[0][0]
    if best <= 0:
        return False

    limit_price = best * (1 + max_impact_pct) if side.upper() == "BUY" else best * (1 - max_impact_pct)

    cum_notional = 0.0
    for p, q in levels:
        if side.upper() == "BUY" and p > limit_price:
            break
        if side.upper() == "SELL" and p < limit_price:
            break
        cum_notional += p * q
        if cum_notional + 1e-9 >= size_usdt:
            return True
    return False


# ==========================
# Komisyon & Toplam Maliyet
# ==========================
def get_taker_fee_rate_from_account(account_info: Dict[str, Any]) -> Optional[float]:
    """
    Binance /api/v3/account sonucu üzerinden takerCommission (bps) -> orana çevirir.
    account_info.get('takerCommission') ör: 10 => %0.1 => 0.001
    """
    try:
        bps = account_info.get("takerCommission")
        if bps is None:
            return None
        return float(bps) / 10000.0
    except Exception:
        return None


def compute_all_in_cost(est_slippage_pct: float, taker_fee_rate: Optional[float] = None) -> Tuple[float, float]:
    """
    toplam_maliyet_pct = fee_rate + est_slippage_pct
    döner: (all_in_pct, fee_pct)
    """
    fee_pct = float(taker_fee_rate if taker_fee_rate is not None else DEFAULT_TAKER_FEE)
    all_in = fee_pct + float(est_slippage_pct)
    return all_in, fee_pct


# ==========================
# Üst seviye yardımcı
# ==========================
def estimate_effective_price_and_costs(
    side: str,
    size_usdt: float,
    book: Dict[str, Any],
    taker_fee_rate: Optional[float] = None,
    slippage_limit: float = SLIPPAGE_LIMIT,
    spread_limit: float = MAX_SPREAD_PCT,
) -> Dict[str, Any]:
    """
    Tek çağrıda tüm ana metrikleri hesaplar:
    - spread
    - VWAP & slippage
    - fee ve toplam maliyet (fee + slippage)
    - slippage/spread limitlerini sağlıyor mu?

    Returns dict:
      {
        "ok": bool,
        "spread_pct": float | None,
        "vwap": float | None,
        "slippage_pct": float | None,
        "fee_pct": float,
        "all_in_cost_pct": float,
        "pass_slippage_limit": bool | None,
        "pass_spread_limit": bool | None,
        "insufficient_liquidity": bool
      }
    """
    nb = normalize_book(book)
    bid, ask = best_bid_ask(nb)
    spr = spread_pct(bid, ask)

    slip_info = estimate_slippage_from_book(side, size_usdt, nb)
    all_in, fee_pct = compute_all_in_cost(slip_info.get("slippage_pct") or 0.0, taker_fee_rate)

    return {
        "ok": slip_info.get("ok", False),
        "spread_pct": spr,
        "vwap": slip_info.get("vwap"),
        "slippage_pct": slip_info.get("slippage_pct"),
        "fee_pct": fee_pct,
        "all_in_cost_pct": all_in,
        "pass_slippage_limit": None if slip_info.get("slippage_pct") is None else (slip_info["slippage_pct"] <= slippage_limit),
        "pass_spread_limit": None if spr is None else (spr <= spread_limit),
        "insufficient_liquidity": bool(slip_info.get("insufficient_liquidity")),
    }
