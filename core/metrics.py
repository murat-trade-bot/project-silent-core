# core/metrics.py

import time
from datetime import timedelta
from core.logger import BotLogger

logger = BotLogger()

class MetricsPrinter:
    """
    Records trade-level metrics and periodically prints balance/PnL/drawdown stats.
    """
    def __init__(self, executor, base_amount: float, settings):
        self.executor = executor
        self.base_amount = base_amount
        self.settings = settings
        self.start_time = time.time()
        try:
            # Initial USDT balance
            self.start_balance = float(self.executor.client.get_asset_balance('USDT')['free'])
        except Exception:
            self.start_balance = self.executor.get_balance('USDT')
        self.peak_balance = self.start_balance
        self.max_drawdown = 0.0
        self.total_trades = 0
        self.win_trades = 0
        self.loss_trades = 0
        self.trade_durations = []

    def record(self, trade: dict) -> None:
        """
        Update metrics after each closed trade.
        Expects trade dict to have 'pnl' and 'duration'.
        """
        self.total_trades += 1
        if trade['pnl'] >= 0:
            self.win_trades += 1
        else:
            self.loss_trades += 1
        self.trade_durations.append(trade.get('duration', 0))

    def heartbeat(self, elapsed: float) -> None:
        """
        Print periodic heartbeat stats.
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
        progress_pct = (curr_balance / self.settings.TARGET_USDT) * 100 if self.settings.TARGET_USDT else 0
        avg_dur = sum(self.trade_durations) / len(self.trade_durations) if self.trade_durations else 0
        win_rate = (self.win_trades / self.total_trades) * 100 if self.total_trades else 0
        uptime = timedelta(seconds=int(elapsed))

        # Log
        logger.info(
            f"[HEARTBEAT] Uptime: {uptime} | Balance: {curr_balance:.2f} USDT | "
            f"PnL%: {pnl_pct:+.2f}% | Progress%: {progress_pct:.2f}%"
        )
        logger.info(
            f"Trades: {self.total_trades} | Wins: {self.win_trades} ({win_rate:.1f}%) | "
            f"Max Drawdown: {self.max_drawdown:.2f} | Avg Dur: {avg_dur:.1f}s"
        )
