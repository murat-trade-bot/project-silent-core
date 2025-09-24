from __future__ import annotations
import os
import time
from typing import Optional, Dict
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, start_http_server


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


# Modül içi kayıt
_REG = CollectorRegistry()
STARTED = False

# Metrikler
ORDERS_TOTAL = Counter(
    "orders_total", "Orders by symbol/side/status",
    labelnames=("symbol", "side", "status"), registry=_REG
)
REJECTIONS_TOTAL = Counter(
    "order_rejections_total", "Rejections by reason",
    labelnames=("reason",), registry=_REG
)
EXCEPTIONS_TOTAL = Counter(
    "exceptions_total", "Unhandled exceptions by type",
    labelnames=("type",), registry=_REG
)
EXEC_LATENCY = Histogram(
    "order_execution_seconds", "Execution latency (seconds)",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10), registry=_REG
)


def start_metrics_server_if_enabled() -> None:
    global STARTED
    if STARTED:
        return
    if _bool_env("METRICS_ENABLED", False):
        port = _int_env("METRICS_PORT", 9108)
        start_http_server(port, registry=_REG)
    STARTED = True


def inc_order(symbol: str, side: str, status: str) -> None:
    try:
        ORDERS_TOTAL.labels(symbol=symbol, side=side, status=status).inc()
    except Exception:
        pass


def inc_reject(reason: str) -> None:
    try:
        REJECTIONS_TOTAL.labels(reason=reason).inc()
    except Exception:
        pass


def inc_exc(cls_name: str) -> None:
    try:
        EXCEPTIONS_TOTAL.labels(type=cls_name).inc()
    except Exception:
        pass


def observe_exec(seconds: float) -> None:
    try:
        EXEC_LATENCY.observe(seconds)
    except Exception:
        pass


# Test yardımcıları
def _generate_latest_text() -> str:
    return generate_latest(_REG).decode("utf-8")


def _reset_for_tests() -> None:
    global _REG, STARTED, ORDERS_TOTAL, REJECTIONS_TOTAL, EXCEPTIONS_TOTAL, EXEC_LATENCY
    _REG = CollectorRegistry()
    STARTED = False
    ORDERS_TOTAL = Counter("orders_total", "", ("symbol", "side", "status"), registry=_REG)
    REJECTIONS_TOTAL = Counter("order_rejections_total", "", ("reason",), registry=_REG)
    EXCEPTIONS_TOTAL = Counter("exceptions_total", "", ("type",), registry=_REG)
    EXEC_LATENCY = Histogram("order_execution_seconds", "", registry=_REG)
# core/metrics.py

import time
from datetime import timedelta
from core.logger import BotLogger
from prometheus_client import start_http_server, Gauge

logger = BotLogger()

class MetricsPrinter:
    """
    Records trade-level metrics and periodically prints balance/PnL/drawdown stats.
    Optionally exposes Prometheus metrics.
    """
    def __init__(self, executor, base_amount: float, settings, prometheus_port: int = None):
        self.executor = executor
        self.base_amount = base_amount
        self.settings = settings
        self.start_time = time.time()
        try:
            self.start_balance = float(self.executor.client.get_asset_balance('USDT')['free'])
        except Exception:
            self.start_balance = self.executor.get_balance('USDT')
        if not self.start_balance:
            logger.warning("MetricsPrinter: Başlangıç bakiyesi 0! Metrikler hatalı olabilir.")
        self.peak_balance = self.start_balance
        self.max_drawdown = 0.0
        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0
        self.trade_durations = []
        self.error_trades = 0  # Hatalı trade sayısı (örnek)

        # Prometheus entegrasyonu
        self.prom_metrics = None
        if prometheus_port is not None:
            try:
                self.prom_metrics = Metrics(port=prometheus_port)
            except Exception as e:
                logger.warning(f"Prometheus başlatılamadı: {e}")

    def record(self, trade: dict) -> None:
        """
        Update metrics after each closed trade.
        Expects trade dict to have 'pnl' and optionally 'duration'.
        """
        self.total_trades += 1
        pnl = trade.get('pnl', 0)
        if pnl >= 0:
            self.win_trades += 1
        else:
            self.loss_trades += 1
        self.trade_durations.append(trade.get('duration', 0))
        # Hatalı trade örneği (isteğe bağlı): trade dict'inde 'error' varsa
        if trade.get('error'):
            self.error_trades += 1

    def heartbeat(self, elapsed: float) -> None:
        """
        Print periodic heartbeat stats and update Prometheus metrics if available.
        """
        # Current balance
        try:
            curr_balance = float(self.executor.client.get_asset_balance('USDT')['free'])
        except Exception:
            curr_balance = self.executor.get_balance('USDT')

        # Update drawdown
        self.peak_balance = max(self.peak_balance, curr_balance)
        drawdown = self.peak_balance - curr_balance
        self.max_drawdown = max(self.max_drawdown, drawdown)

        # Compute stats
        pnl_pct = (curr_balance - self.start_balance) / self.start_balance * 100 if self.start_balance else 0
        avg_dur = sum(self.trade_durations) / len(self.trade_durations) if self.trade_durations else 0
        win_rate = (self.win_trades / self.total_trades) * 100 if self.total_trades else 0
        error_rate = (self.error_trades / self.total_trades) * 100 if self.total_trades else 0
        uptime = timedelta(seconds=int(elapsed))

        # Log
        logger.info(
            f"[HEARTBEAT] Uptime: {uptime} | Balance: {curr_balance:.2f} USDT | "
            f"PnL%: {pnl_pct:+.2f}%"
        )
        logger.info(
            f"Trades: {self.total_trades} | Wins: {self.win_trades} ({win_rate:.1f}%) | "
            f"Max Drawdown: {self.max_drawdown:.2f} | Avg Dur: {avg_dur:.1f}s | Error Rate: {error_rate:.2f}%"
        )
        # Prometheus metrikleri güncelle
        if self.prom_metrics:
            self.prom_metrics.update(self.max_drawdown, error_rate, 0)  # latency ölçülmüyorsa 0

class Metrics:
    def __init__(self, port=8000):
        self.drawdown_gauge = Gauge('drawdown', 'Current drawdown')
        self.error_rate_gauge = Gauge('error_rate', 'Current error rate')
        self.latency_gauge = Gauge('latency', 'API latency')
        try:
            start_http_server(port)
        except Exception as e:
            logger.warning(f"Prometheus HTTP server başlatılamadı: {e}")

    def update(self, drawdown, error_rate, latency):
        self.drawdown_gauge.set(drawdown)
        self.error_rate_gauge.set(error_rate)
        self.latency_gauge.set(latency)
