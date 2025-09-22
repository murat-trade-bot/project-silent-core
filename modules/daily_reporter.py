# -*- coding: utf-8 -*-
"""
modules/daily_reporter.py
Project Silent Core – Gün Sonu Otomatik Reset ve Raporlama

Ne yapar?
- Tüm gün boyunca trade metriklerini toplar (alım/satım sayıları, kâr/zarar, işlem gören coinler)
- Her döngüde 'şu an' tarihini kontrol eder; tarih değiştiyse raporu diske yazar ve günlük state'i resetler
- JSONL (detaylı günlük rapor) + CSV (özet satır) üretir
- Reset sonrası yeni günün başlangıç sermayesini 'o anki equity' olarak alır

Kullanım (özet):
    reporter = DailyReporter(report_dir="reports", basename="daily_report",
                             start_equity=settings.BAŞLANGIÇ_SERMEYESİ, logger=logger)

    # gün içinde:
    reporter.set_equity(current_equity)
    reporter.log_trade(symbol="BTCUSDT", side="BUY", qty=0.001, price=60000.0,
                       fee_usdt=0.02, notional_usdt=60.0, profit_usdt=None, success=None)
    # SELL'de profit_usdt doldur:
    reporter.log_trade(..., side="SELL", ..., profit_usdt=+1.25, success=True)

    # döngü sonunda (veya belli aralıkla):
    rolled = reporter.maybe_rollover(now=datetime.now(), total_profit_usdt=total_profit, force=False)
"""

from __future__ import annotations

import os as _os
import csv
import json
from datetime import datetime, date
from typing import Optional, Dict, Any, List

class DailyReporter:
    def __init__(
        self,
        report_dir: str = "reports",
        basename: str = "daily_report",
        start_equity: float = 0.0,
        logger: Optional[Any] = None,
    ):
        self.report_dir = report_dir
        self.basename = basename
        self.logger = logger
        _os.makedirs(self.report_dir, exist_ok=True)

        self.current_date = datetime.now().date()
        self.start_equity = float(start_equity)
        self.end_equity = float(start_equity)

        # gün içi özet metrikler
        self.summary = {
            "date": self.current_date.strftime("%Y-%m-%d"),
            "trade_count": 0,
            "buy_count": 0,
            "sell_count": 0,
            "success_trades": 0,
            "coins_traded": [],
            "daily_profit_usdt": 0.0,
        }

        # günlük detaylar (isteğe bağlı, JSONL için)
        self._events = []

        # CSV başlığı (günlük bir satır)
        self._csv_headers = [
            "date",
            "start_equity",
            "end_equity",
            "daily_profit_usdt",
            "daily_profit_pct",
            "trade_count",
            "buy_count",
            "sell_count",
            "success_trades",
            "coins_traded",
            "total_profit_usdt",
        ]

    # --------- public API ---------
    def set_equity(self, equity_usdt: float) -> None:
        """Her döngüde approximate equity ver (sim/live)."""
        self.end_equity = float(equity_usdt)
        self.summary["daily_profit_usdt"] = float(self.end_equity - self.start_equity)

    def log_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee_usdt: float,
        notional_usdt: float,
        profit_usdt: Optional[float] = None,
        success: Optional[bool] = None,
        ts: Optional[datetime] = None,
    ) -> None:
        """Her emir/işlem sonrasında çağırın."""
        side = side.upper()
        self.summary["trade_count"] += 1
        if side == "BUY":
            self.summary["buy_count"] += 1
        elif side == "SELL":
            self.summary["sell_count"] += 1

        if success is True:
            self.summary["success_trades"] += 1

        if symbol not in self.summary["coins_traded"]:
            self.summary["coins_traded"].append(symbol)

        event = {
            "ts": (ts or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "side": side,
            "qty": float(qty),
            "price": float(price),
            "fee_usdt": float(fee_usdt),
            "notional_usdt": float(notional_usdt),
        }
        if profit_usdt is not None:
            event["profit_usdt"] = float(profit_usdt)
        if success is not None:
            event["success"] = bool(success)
        self._events.append(event)

    def maybe_rollover(self, now: datetime, total_profit_usdt: float, force: bool = False) -> bool:
        """
        Tarih değiştiyse (veya force=True) günlük raporu yazar ve resetler.
        Döner: True (reset yapıldı) / False (aynı gün devam)
        """
        if not force and now.date() == self.current_date:
            return False

        self._write_reports(total_profit_usdt=total_profit_usdt)
        if self.logger:
            try:
                self.logger.info(f"Gün sonu raporu yazıldı: {self._jsonl_path(self.current_date)}")
            except Exception:
                pass

        # Yeni gün için reset: başlangıç sermayesi günün sonunda oluşan equity
        self.current_date = now.date()
        self.start_equity = float(self.end_equity)
        self.summary = {
            "date": self.current_date.strftime("%Y-%m-%d"),
            "trade_count": 0,
            "buy_count": 0,
            "sell_count": 0,
            "success_trades": 0,
            "coins_traded": [],
            "daily_profit_usdt": 0.0,
        }
        self._events = []
        return True

    # --------- private helpers ---------
    def _jsonl_path(self, d: date) -> str:
        return _os.path.join(self.report_dir, f"{self.basename}_{d:%Y%m%d}.jsonl")

    def _csv_path(self) -> str:
        return _os.path.join(self.report_dir, f"{self.basename}_summaries.csv")

    def _write_reports(self, total_profit_usdt: float) -> None:
        """JSONL (detay) + CSV (özet) dosyalarını gün sonu için yazar."""
        # JSONL (detay event'ler)
        jsonl_file = self._jsonl_path(self.current_date)
        with open(jsonl_file, "a", encoding="utf-8") as f:
            for ev in self._events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

        # CSV (özet satır)
        daily_profit = float(self.end_equity - self.start_equity)
        daily_profit_pct = (daily_profit / self.start_equity * 100.0) if self.start_equity > 0 else 0.0
        coins_str = ",".join(self.summary["coins_traded"]) if self.summary["coins_traded"] else ""

        row = {
            "date": self.current_date.strftime("%Y-%m-%d"),
            "start_equity": round(self.start_equity, 6),
            "end_equity": round(self.end_equity, 6),
            "daily_profit_usdt": round(daily_profit, 6),
            "daily_profit_pct": round(daily_profit_pct, 4),
            "trade_count": self.summary["trade_count"],
            "buy_count": self.summary["buy_count"],
            "sell_count": self.summary["sell_count"],
            "success_trades": self.summary["success_trades"],
            "coins_traded": coins_str,
            "total_profit_usdt": round(float(total_profit_usdt), 6),
        }

        csv_file = self._csv_path()
        file_exists = _os.path.exists(csv_file)
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._csv_headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
