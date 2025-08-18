# -*- coding: utf-8 -*-
"""
modules/risk_manager.py
Project Silent Core – Risk Yönetimi

Bu modül; günlük zarar limiti, maruziyet (exposure) limitleri, işlem sıklığı (rate-limit),
cooldown, komisyon/sluippage toplam maliyet eşiği ve likiditeye bağlı basit kontrolleri
tek bir kapıda toplar. Emir atılmadan önce OrderExecutor bu sınıfın allow_trade() metodunu
çağırır; emirden sonra register_* metodlarıyla durum güncellenir.

Kullanım (özet):
    rm = RiskManager(day_start_equity_usdt=252.0)
    ok, reason, m = rm.allow_trade(
        symbol="BTCUSDT",
        side="BUY",
        size_usdt=20.0,
        equity_usdt=mevcut_bakiye,
        current_total_exposure_usdt=toplam_açık_pozisyon_usdt,
        symbol_exposure_usdt=symb_açık_pozisyon_usdt,
        est_fee_rate=0.001,           # taker ~%0.1
        est_slippage_pct=0.003,       # ~%0.3 beklenen
        book=order_book_snapshot      # {"bids":[[p, q], ...], "asks":[[p, q], ...]}
    )
    if ok:
        # emir gönder
        ...
        rm.register_order_attempt("BTCUSDT", now=time.time())
        # fill sonrası:
        rm.register_fill("BTCUSDT", side="BUY", filled_usdt=19.998, fee_usdt=0.02,
                         realized_pnl_usdt=0.0, now=time.time())

Notlar:
- Likidite kontrolü basitçe “belirli bir etki eşiği içinde bu notional doldurulabilir mi?”
  yaklaşımıyla yapılır (MAX_IMPACT_PCT içinde kümülatif derinlik).
- Günlük PnL takibi için day_start_equity_usdt zorunludur. equity_usdt parametresi
  allow_trade çağrısında güncel olarak verilir.
"""

from __future__ import annotations

import time
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple, Any, Optional

try:
    # Ayarlar opsiyonel; yoksa makul varsayılanlar kullanılır
    from config import settings
    _HAS_SETTINGS = True
except Exception:
    _HAS_SETTINGS = False


@dataclass
class RiskLimits:
    # Günlük risk
    daily_loss_limit_pct: float = 0.06       # Günlük maksimum zarar oranı (örn. %6)
    profit_lock_pct: float = 0.06            # Günlük kâr kilidi (örn. %6) – bilgi amaçlı

    # Maruziyet limitleri
    max_total_exposure_pct: float = 0.50     # Toplam açık pozisyon / equity üst sınırı
    max_symbol_exposure_pct: float = 0.25    # Sembol başı açık pozisyon / equity üst sınırı

    # İşlem sıklığı
    max_trades_per_hour: int = 20
    order_cooldown_sec: int = 1              # Emirler arası global bekleme
    min_interval_between_trades_sec: int = 0 # (Opsiyonel) ek bekleme

    # Maliyet/likidite
    max_all_in_cost_pct: float = 0.003       # fee + beklenen slippage toplamı üst sınır (örn. %0.30)
    max_spread_pct: float = 0.003            # anlık spread üst sınırı (örn. %0.30)
    max_impact_pct: float = 0.003            # gerekli notional, bu etki içinde dolmalı (örn. %0.30)

    # Güvenlik bayrakları
    hard_stop_after_breach: bool = True      # günlük zarar aşılırsa kilitlen


def _limits_from_settings() -> RiskLimits:
    if not _HAS_SETTINGS:
        return RiskLimits()
    return RiskLimits(
        daily_loss_limit_pct = float(getattr(settings, "DAILY_LOSS_LIMIT_PCT", 0.06)),
        profit_lock_pct      = float(getattr(settings, "DAILY_PROFIT_LOCK_PCT", 0.06)),
        max_total_exposure_pct  = float(getattr(settings, "MAX_TOTAL_EXPOSURE_PCT", 0.50)),
        max_symbol_exposure_pct = float(getattr(settings, "MAX_SYMBOL_EXPOSURE_PCT", 0.25)),
        max_trades_per_hour      = int(getattr(settings, "MAX_TRADES_PER_HOUR", 20)),
        order_cooldown_sec       = int(getattr(settings, "ORDER_COOLDOWN", 1)),
        min_interval_between_trades_sec = int(getattr(settings, "MIN_INTERVAL_BETWEEN_TRADES", 0)),
        max_all_in_cost_pct = float(getattr(settings, "MAX_ALL_IN_COST_PCT", 0.003)),
        max_spread_pct      = float(getattr(settings, "MAX_SPREAD_PCT", 0.003)),
        max_impact_pct      = float(getattr(settings, "MAX_IMPACT_PCT", 0.003)),
        hard_stop_after_breach = bool(getattr(settings, "HARD_STOP_AFTER_BREACH", True)),
    )


class RiskManager:
    def __init__(self, day_start_equity_usdt: float, limits: Optional[RiskLimits] = None):
        self.limits = limits or _limits_from_settings()
        self.day_start_equity = float(day_start_equity_usdt)

        # Durum
        self.hard_stop_hit = False
        self.trade_times_last_hour = deque()   # global işlem zamanları (epoch s)
        self.last_trade_time_global = 0.0
        self.last_trade_time_per_symbol = defaultdict(float)

        # İstatistik
        self.daily_realized_pnl = 0.0

    # ---------- Yardımcılar ----------
    def _prune_old_trades(self, now: float) -> None:
        one_hour_ago = now - 3600.0
        while self.trade_times_last_hour and self.trade_times_last_hour[0] < one_hour_ago:
            self.trade_times_last_hour.popleft()

    @staticmethod
    def _best_bid_ask(book: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
        if not book:
            return None, None
        try:
            bid = float(book["bids"][0][0]) if book.get("bids") else None
            ask = float(book["asks"][0][0]) if book.get("asks") else None
            return bid, ask
        except Exception:
            return None, None

    @staticmethod
    def _spread_pct(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
        if bid and ask and bid > 0.0:
            return (ask - bid) / bid
        return None

    @staticmethod
    def _is_fillable_within_impact(side: str, size_usdt: float, book: Dict[str, Any], max_impact_pct: float) -> bool:
        """
        Market etkileşimi basit kontrol: BUY için 'asks', SELL için 'bids' kümülatif notional,
        fiyat (best)*(1+/-max_impact_pct) sınırı içinde yeterli mi?
        """
        if not book or size_usdt <= 0:
            return False
        try:
            levels = book["asks"] if side.upper() == "BUY" else book["bids"]
            best = float(levels[0][0])
            limit_price = best * (1 + max_impact_pct) if side.upper() == "BUY" else best * (1 - max_impact_pct)

            cum_notional = 0.0
            for px, qty in levels:
                p = float(px); q = float(qty)
                # BUY: fiyat limit_price'ın ÜZERİNE çıkmamalı
                # SELL: fiyat limit_price'ın ALTINA inmemeli
                if side.upper() == "BUY" and p > limit_price:
                    break
                if side.upper() == "SELL" and p < limit_price:
                    break
                cum_notional += p * q
                if cum_notional >= size_usdt:
                    return True
            return False
        except Exception:
            return False

    # ---------- Dış arayüz ----------
    def allow_trade(
        self,
        symbol: str,
        side: str,
        size_usdt: float,
        equity_usdt: float,
        current_total_exposure_usdt: float,
        symbol_exposure_usdt: float,
        est_fee_rate: float,
        est_slippage_pct: float,
        book: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Emir öncesi risk ve piyasa koşulları kontrolü.
        Döndürür: (izin, neden, metrikler)
        """
        t = now or time.time()
        side = side.upper()

        # 1) Günlük zarar limiti (equity bazlı)
        if self.hard_stop_hit and self.limits.hard_stop_after_breach:
            return False, "Günlük zarar limiti aşıldı: hard stop aktif.", {"reason": "hard_stop"}

        if self.day_start_equity > 0:
            drawdown_pct = (equity_usdt - self.day_start_equity) / self.day_start_equity
            if drawdown_pct <= -self.limits.daily_loss_limit_pct:
                self.hard_stop_hit = True
                return False, f"Günlük zarar limiti aşıldı ({drawdown_pct*100:.2f}%).", {"drawdown_pct": drawdown_pct}

        # 2) İşlem sıklığı/rate-limit
        self._prune_old_trades(t)
        if len(self.trade_times_last_hour) >= self.limits.max_trades_per_hour:
            return False, "Saatlik işlem limiti aşıldı.", {"trades_last_hour": len(self.trade_times_last_hour)}

        if self.limits.order_cooldown_sec > 0 and (t - self.last_trade_time_global) < self.limits.order_cooldown_sec:
            return False, f"Global cooldown aktif ({self.limits.order_cooldown_sec}s).", {
                "since_last": t - self.last_trade_time_global
            }

        last_sym_t = self.last_trade_time_per_symbol[symbol]
        if self.limits.min_interval_between_trades_sec > 0 and (t - last_sym_t) < self.limits.min_interval_between_trades_sec:
            return False, f"{symbol} için cooldown aktif.", {"since_last_symbol": t - last_sym_t}

        # 3) Maruziyet limitleri (yeni emir dahil edilerek)
        new_total_exposure = current_total_exposure_usdt + (size_usdt if side == "BUY" else 0.0)
        new_symbol_exposure = symbol_exposure_usdt + (size_usdt if side == "BUY" else 0.0)

        if equity_usdt > 0:
            total_exp_pct = new_total_exposure / equity_usdt
            sym_exp_pct = new_symbol_exposure / equity_usdt
            if total_exp_pct > self.limits.max_total_exposure_pct:
                return False, f"Toplam maruziyet limiti aşılıyor ({total_exp_pct*100:.2f}%).", {
                    "total_exposure_pct": total_exp_pct
                }
            if sym_exp_pct > self.limits.max_symbol_exposure_pct:
                return False, f"{symbol} maruziyet limiti aşılıyor ({sym_exp_pct*100:.2f}%).", {
                    "symbol_exposure_pct": sym_exp_pct
                }

        # 4) Spread & likidite & etki (market etkisi)
        bid, ask = self._best_bid_ask(book)
        spr = self._spread_pct(bid, ask)
        if spr is not None and spr > self.limits.max_spread_pct:
            return False, f"Spread çok geniş ({spr*100:.2f}%).", {"spread_pct": spr}

        if book is not None:
            if not self._is_fillable_within_impact(side, size_usdt, book, self.limits.max_impact_pct):
                return False, f"Likidite yetersiz (>{self.limits.max_impact_pct*100:.2f}% etki).", {
                    "max_impact_pct": self.limits.max_impact_pct
                }

        # 5) Komisyon + beklenen slippage toplam maliyet
        all_in_cost = float(est_fee_rate) + float(est_slippage_pct)
        if all_in_cost > self.limits.max_all_in_cost_pct:
            return False, f"Maliyet yüksek (fee+slip={all_in_cost*100:.2f}%).", {"all_in_cost_pct": all_in_cost}

        # Geçti
        metrics = {
            "all_in_cost_pct": all_in_cost,
            "spread_pct": spr,
            "total_exposure_pct": (new_total_exposure / equity_usdt) if equity_usdt > 0 else None,
            "symbol_exposure_pct": (new_symbol_exposure / equity_usdt) if equity_usdt > 0 else None,
        }
        return True, "Uygun", metrics

    # ---------- Emir sonrası güncellemeler ----------
    def register_order_attempt(self, symbol: str, now: Optional[float] = None) -> None:
        t = now or time.time()
        self.trade_times_last_hour.append(t)
        self.last_trade_time_global = t
        self.last_trade_time_per_symbol[symbol] = t

    def register_fill(
        self,
        symbol: str,
        side: str,
        filled_usdt: float,
        fee_usdt: float,
        realized_pnl_usdt: float,
        now: Optional[float] = None,
    ) -> None:
        """
        Emir gerçekleştikten sonra çağrılır. realized_pnl_usdt, satışlarda (+/-) kâr/zararı temsil eder.
        Alımda genelde 0 yazılır (kapanışta realize olur).
        """
        _ = symbol, side  # ileride sembol-bazlı metrikler eklenebilir
        self.daily_realized_pnl += float(realized_pnl_usdt) - float(fee_usdt)
        # saatlik sayaçlar zaten order_attempt ile tutuluyor

    # ---------- Bilgi ----------
    def get_daily_pnl(self) -> float:
        return self.daily_realized_pnl

    def is_hard_stopped(self) -> bool:
        return self.hard_stop_hit
