# -*- coding: utf-8 -*-
"""
modules/order_executor.py
Project Silent Core – Emir Yürütme Katmanı (SPOT)

Görevleri:
- Emir ATMADAN ÖNCE: order book, spread, VWAP, beklenen slippage, taker fee oranı,
  toplam maliyet (fee + slippage) ölçümü ve (varsa) RiskManager ile politika kontrolü
- Emir GÖNDERME: SPOT market/limit emirleri
- Emir SONRASI: gerçekleşen fill'lerden ortalama fiyat ve ücretlerin çıkarılması,
  (varsa) RiskManager'a işlem kaydı ve basit maruziyet (exposure) takibi

Notlar:
- Futures/hedge/leveraged/margin desteği YOK; yalnızca SPOT.
- RiskManager opsiyoneldir; verilmezse yalnızca piyasa filtreleri uygulanır.
"""

from __future__ import annotations

import time
from typing import Optional, Dict, Any, Tuple

from config import settings
from notifier import send_notification

from modules import order_filters
from modules.risk_manager import RiskManager

# Binance SPOT client
from binance.client import Client


class OrderExecutor:
    def __init__(
        self,
        client: Client,
        risk_manager: Optional[RiskManager] = None,
        notifier_enabled: Optional[bool] = None,
        order_book_depth: int = 20,
        taker_fee_cache_ttl_sec: int = 600,
    ):
        self.client = client
        self.risk: Optional[RiskManager] = risk_manager
        self.notifier_enabled = settings.NOTIFIER_ENABLED if notifier_enabled is None else bool(notifier_enabled)
        self.order_book_depth = int(order_book_depth)
        self.taker_fee_cache_ttl = int(taker_fee_cache_ttl_sec)

        # basit maruziyet takibi (USDT cinsinden)
        self._exposure_usdt_per_symbol: Dict[str, float] = {}
        self._last_taker_fee_fetch_ts: float = 0.0
        self._taker_fee_rate_cached: Optional[float] = None

    # ----------------------
    # Yardımcılar
    # ----------------------
    def set_risk_manager(self, rm: RiskManager) -> None:
        self.risk = rm

    def _get_order_book(self, symbol: str) -> Dict[str, Any]:
        return self.client.get_order_book(symbol=symbol, limit=self.order_book_depth)

    def _get_taker_fee_rate(self) -> float:
        """Hesaptan takerCommission (bps) çekip 0.xx oranına çevirir, 10 dk cache eder."""
        now = time.time()
        if self._taker_fee_rate_cached is not None and (now - self._last_taker_fee_fetch_ts) < self.taker_fee_cache_ttl:
            return self._taker_fee_rate_cached

        try:
            account = self.client.get_account()
            rate = order_filters.get_taker_fee_rate_from_account(account)
            if rate is None:
                rate = order_filters.DEFAULT_TAKER_FEE  # varsayılan: %0.1
        except Exception:
            rate = order_filters.DEFAULT_TAKER_FEE
        self._taker_fee_rate_cached = float(rate)
        self._last_taker_fee_fetch_ts = now
        return self._taker_fee_rate_cached

    def _get_ref_price(self, side: str, book: Dict[str, Any]) -> Optional[float]:
        nb = order_filters.normalize_book(book)
        bid, ask = order_filters.best_bid_ask(nb)
        return ask if side.upper() == "BUY" else bid

    def _get_equity_approx(self) -> float:
        """
        Basit equity approx: USDT free + açık maruziyet (USDT).
        Not: Tam equity için tüm varlıkların USDT karşılığı gerekir (daha ağır).
        """
        try:
            bal = self.client.get_asset_balance(asset="USDT") or {}
            usdt_free = float(bal.get("free", 0.0))
        except Exception:
            usdt_free = 0.0
        open_exposure = sum(max(v, 0.0) for v in self._exposure_usdt_per_symbol.values())
        return float(usdt_free) + float(open_exposure)

    def _update_exposure(self, symbol: str, side: str, filled_quote_usdt: float) -> None:
        cur = float(self._exposure_usdt_per_symbol.get(symbol, 0.0))
        if side.upper() == "BUY":
            cur += float(filled_quote_usdt)
        else:
            # satışta maruziyeti düşür
            cur -= float(filled_quote_usdt)
            if cur < 0:
                cur = 0.0
        self._exposure_usdt_per_symbol[symbol] = cur

    # ----------------------
    # Ön kontrol + tahmin (emir atmadan önce)
    # ----------------------
    def precheck(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Emir ATMADAN ÖNCE piyasa ve (varsa) risk kontrolleri.
        Döner: (izin, neden, metrikler)
        """
        side = side.upper()
        order_type = order_type.upper()

        # 1) order book al
        book = self._get_order_book(symbol)
        ref_price = self._get_ref_price(side, book)
        if not ref_price or ref_price <= 0:
            return False, "Referans fiyat alınamadı.", {"reason": "no_ref_price"}

        # 2) notional (USDT) yaklaşık hesap
        size_usdt = float(quantity) * float(ref_price)

        # 3) taker ücreti (oran)
        taker_fee_rate = self._get_taker_fee_rate()

        # 4) piyasa metrikleri (spread, vwap, slippage, all-in cost)
        mkt = order_filters.estimate_effective_price_and_costs(
            side=side,
            size_usdt=size_usdt,
            book=book,
            taker_fee_rate=taker_fee_rate,
        )

        if mkt["spread_pct"] is not None and mkt["pass_spread_limit"] is False:
            return False, f"Spread limit dışı ({mkt['spread_pct']*100:.2f}%).", {"metrics": mkt}

        if mkt["ok"] is False or mkt["insufficient_liquidity"]:
            return False, "Likidite yetersiz.", {"metrics": mkt}

        if mkt["pass_slippage_limit"] is False:
            return False, f"Slippage limit dışı ({(mkt['slippage_pct'] or 0)*100:.2f}%).", {"metrics": mkt}

        # 5) RiskManager (opsiyonel)
        if self.risk is not None:
            equity_usdt = self._get_equity_approx()
            total_exp = sum(max(v, 0.0) for v in self._exposure_usdt_per_symbol.values())
            sym_exp = float(self._exposure_usdt_per_symbol.get(symbol, 0.0))

            ok, reason, rm_metrics = self.risk.allow_trade(
                symbol=symbol,
                side=side,
                size_usdt=size_usdt,
                equity_usdt=equity_usdt,
                current_total_exposure_usdt=total_exp,
                symbol_exposure_usdt=sym_exp,
                est_fee_rate=float(taker_fee_rate),
                est_slippage_pct=float(mkt["slippage_pct"] or 0.0),
                book=book,
            )
            if not ok:
                return False, reason, {"metrics": mkt, "risk": rm_metrics}

        return True, "Uygun", {"metrics": mkt, "ref_price": ref_price, "taker_fee_rate": taker_fee_rate}

    # ----------------------
    # Emir Gönderme (SPOT)
    # ----------------------
    def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        allow_partial: bool = True,
        do_precheck: bool = True,
    ) -> Dict[str, Any]:
        """
        SPOT emir yürütme.
        - order_type: "MARKET" | "LIMIT"
        - quantity: BASE miktar (lot/tick uyumu çağıran tarafta sağlanmalı)
        Dönenler:
          {
            "ok": bool,
            "orderId": ...,
            "symbol": ...,
            "side": ...,
            "status": "FILLED"/"PARTIALLY_FILLED"/"NEW"/"REJECTED"/...,
            "filled_qty": float,
            "filled_quote": float,
            "avg_fill_price": float | None,
            "fee_usdt": float,
            "raw": {...}   # Binance raw response
          }
        """
        side = side.upper()
        order_type = order_type.upper()

        # Ön kontrol
        if do_precheck:
            ok, reason, info = self.precheck(symbol, side, quantity, order_type, price)
            if not ok:
                if self.notifier_enabled:
                    try:
                        send_notification(f"⛔ Emir reddedildi ({symbol} {side}): {reason}")
                    except Exception:
                        pass
                return {"ok": False, "reason": reason, "info": info}

        # RiskManager: order attempt kaydı
        if self.risk is not None:
            try:
                self.risk.register_order_attempt(symbol, now=time.time())
            except Exception:
                pass

        # Emir gönder
        try:
            if order_type == "MARKET":
                if side == "BUY":
                    resp = self.client.order_market_buy(symbol=symbol, quantity=quantity)
                else:
                    resp = self.client.order_market_sell(symbol=symbol, quantity=quantity)
            elif order_type == "LIMIT":
                if price is None:
                    return {"ok": False, "reason": "LIMIT emri için price zorunlu.", "info": {}}
                if side == "BUY":
                    resp = self.client.order_limit_buy(symbol=symbol, quantity=quantity, price=str(price), timeInForce=time_in_force)
                else:
                    resp = self.client.order_limit_sell(symbol=symbol, quantity=quantity, price=str(price), timeInForce=time_in_force)
            else:
                return {"ok": False, "reason": f"Bilinmeyen order_type: {order_type}", "info": {}}
        except Exception as e:
            if self.notifier_enabled:
                try:
                    send_notification(f"🚨 Emir gönderilemedi ({symbol} {side}): {e}")
                except Exception:
                    pass
            return {"ok": False, "reason": f"API error: {e}", "info": {}}

        # Fill bilgilerini toparla
        result = self._parse_fills(symbol, resp)

        # Maruziyeti güncelle (yalnızca gerçekleşen kısım için)
        if result["filled_quote"] > 0:
            self._update_exposure(symbol, side, result["filled_quote"])

        # RiskManager: fill kaydı (realized_pnl_usdt burada 0; PnL hesapları portföy tarafında)
        if self.risk is not None:
            try:
                self.risk.register_fill(
                    symbol=symbol,
                    side=side,
                    filled_usdt=result["filled_quote"],
                    fee_usdt=result["fee_usdt"],
                    realized_pnl_usdt=0.0,
                    now=time.time(),
                )
            except Exception:
                pass

        # Limit ve henüz NEW ise (dolmadı) kısmi/iptal mantığını istersen burada genişletebilirsin
        if (result["status"] not in ("FILLED", "PARTIALLY_FILLED")) and (not allow_partial):
            # iptal etmeyi deneyebiliriz
            try:
                self.client.cancel_open_orders(symbol=symbol)
            except Exception:
                pass

        # Bildirim (opsiyonel)
        if self.notifier_enabled:
            try:
                msg = f"🟢 {symbol} {side} {result['status']} | qty={result['filled_qty']:.6f} avg={result['avg_fill_price'] or 0:.6f} fee≈{result['fee_usdt']:.4f} USDT"
                send_notification(msg)
            except Exception:
                pass

        result["ok"] = True
        result["raw"] = resp
        return result

    # ----------------------
    # Fill parser
    # ----------------------
    def _parse_fills(self, symbol: str, resp: Dict[str, Any]) -> Dict[str, Any]:
        """
        Binance spot yanıtından doldurma metriklerini çıkarır.
        Commission USDT değilse (örn. BNB), yaklaşık USDT'e çevirme denemesi yapılır.
        """
        status = str(resp.get("status", "NEW"))
        fills = resp.get("fills", []) or []

        sum_qty = 0.0
        sum_quote = 0.0
        fee_usdt = 0.0

        # Referans fiyat (şimdiki an) ile komisyon çevirimi için
        ref_price = None
        try:
            book = self._get_order_book(symbol)
            ref_price = self._get_ref_price("BUY", book) or self._get_ref_price("SELL", book)
        except Exception:
            pass

        base_asset = symbol[:-4] if symbol.endswith("USDT") else None  # kaba çıkarım

        for f in fills:
            try:
                price = float(f.get("price", 0.0))
                qty = float(f.get("qty", 0.0))
                commission = float(f.get("commission", 0.0))
                commission_asset = f.get("commissionAsset")

                sum_qty += qty
                sum_quote += price * qty

                # komisyonu USDT'e çevirme (yaklaşık):
                if commission > 0:
                    if commission_asset == "USDT":
                        fee_usdt += commission
                    elif commission_asset == base_asset and ref_price:
                        fee_usdt += commission * ref_price
                    else:
                        # bilinmiyorsa ihmal et (istersen burada extra fiyat sorgusu ile genişlet)
                        pass
            except Exception:
                continue

        avg_price = (sum_quote / sum_qty) if sum_qty > 1e-12 else None

        return {
            "orderId": resp.get("orderId"),
            "symbol": resp.get("symbol"),
            "side": resp.get("side"),
            "status": status,
            "filled_qty": float(sum_qty),
            "filled_quote": float(sum_quote),
            "avg_fill_price": avg_price,
            "fee_usdt": float(fee_usdt),
        }
