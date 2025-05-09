import time
import random
from datetime import datetime

from binance.exceptions import BinanceAPIException

from core.logger import BotLogger
from core.csv_logger import log_trade_csv
from core.metrics import MetricsPrinter
from core.strategy import Strategy
from core.executor import ExecutorManager
from modules.dynamic_position import get_dynamic_position_size
from modules.multi_asset_selector import select_coins
from modules.period_manager import (
    update_settings_for_period,
    compute_daily_shortfall
)
from notifier import send_notification
from config import settings

logger = BotLogger()

class BotEngine:
    def __init__(self, client):
        self.client = client
        self.strategy = Strategy()
        self.executor = ExecutorManager(client)
        self.base_amount = settings.TRADE_USDT_AMOUNT
        self.metrics = MetricsPrinter(self.executor, self.base_amount, settings)

    def run(self):
        last_heartbeat = time.time()

        while True:
            try:
                # 1) Periyot güncelle
                period = update_settings_for_period()
                extra = compute_daily_shortfall(self.client)
                settings.TRADE_USDT_AMOUNT = self.base_amount + extra

                # 2) Sembol seçimi
                if settings.USE_DYNAMIC_SYMBOL_SELECTION:
                    symbols = select_coins() or settings.SYMBOLS
                else:
                    symbols = settings.SYMBOLS

                # 3) Her sembol için trade döngüsü
                for symbol in symbols:
                    cycle_start = time.time()
                    try:
                        action = self.strategy.decide(symbol)
                        amount = settings.TRADE_USDT_AMOUNT
                        if getattr(settings, 'USE_DYNAMIC_POSITION', False):
                            atr = self.strategy._get_signals(symbol).get('atr')
                            amount = get_dynamic_position_size(atr, amount)

                        if action == 'BUY':
                            self.executor.buy(symbol, amount)
                        elif action == 'SELL':
                            self.executor.sell(symbol)

                        closed = self.executor.get_closed_positions()
                        if closed:
                            trade = closed[-1]
                            trade['timestamp'] = datetime.utcnow()
                            trade['duration'] = time.time() - cycle_start

                            log_trade_csv(trade)
                            if getattr(settings, 'NOTIFIER_ENABLED', False):
                                send_notification(
                                    f"Trade {trade['action']} {symbol} PnL {trade['pnl']:+.2f}"
                                )
                            self.metrics.record(trade)

                    except BinanceAPIException as e:
                        logger.error(f"Binance API error for {symbol}: {e}")
                        time.sleep(3)
                    except Exception as e:
                        logger.exception(f"Unexpected error in trade cycle for {symbol}: {e}")
                        time.sleep(2)

                    time.sleep(
                        settings.CYCLE_INTERVAL + random.randint(
                            settings.CYCLE_JITTER_MIN,
                            settings.CYCLE_JITTER_MAX
                        )
                    )

                # 4) Heartbeat
                if time.time() - last_heartbeat >= settings.HEARTBEAT_INTERVAL:
                    self.metrics.heartbeat(time.time() - last_heartbeat)
                    last_heartbeat = time.time()

            except Exception as e:
                logger.exception(f"Main loop error: {e}")
                time.sleep(10)
