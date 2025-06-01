import time
import random
from datetime import datetime

from binance.exceptions import BinanceAPIException
from requests.exceptions import RequestException

from core.logger import BotLogger
from core.csv_logger import log_trade_csv
from core.metrics import MetricsPrinter
from core.strategy import Strategy
from core.executor import ExecutorManager
from modules.dynamic_position import get_dynamic_position_size
from modules.multi_asset_selector import select_coins
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
                # 1) Sembol seçimi
                symbols = select_coins() or settings.SYMBOLS if settings.USE_DYNAMIC_SYMBOL_SELECTION else settings.SYMBOLS

                # 2) Her sembol için trade döngüsü
                for symbol in symbols:
                    try:
                        action = self.strategy.decide(symbol)
                        amount = settings.TRADE_USDT_AMOUNT
                        if getattr(settings, 'USE_DYNAMIC_POSITION', False):
                            atr = self.strategy._get_signals(symbol).get('atr')
                            dyn_amount = get_dynamic_position_size(atr, amount)
                            amount = dyn_amount if dyn_amount is not None else amount

                        if action == 'BUY':
                            self.executor.buy(symbol, amount)
                        elif action == 'SELL':
                            self.executor.sell(symbol)

                        closed = self.executor.get_closed_positions()
                        if closed:
                            for trade in closed:
                                trade_row = {
                                    'symbol':   trade.get('symbol', symbol),
                                    'action':   trade.get('action', action),
                                    'quantity': trade.get('quantity', amount),
                                    'price':    trade.get('exit_price', trade.get('price', 0)),
                                    'pnl':      trade.get('pnl', 0)
                                }
                                log_trade_csv(trade_row)
                                if settings.NOTIFIER_ENABLED:
                                    send_notification(
                                        f"Trade {trade_row['action']} {trade_row['symbol']} PnL {trade_row['pnl']:+.2f}"
                                    )
                                self.metrics.record(trade_row)

                    except BinanceAPIException as e:
                        logger.error(f"Binance API error for {symbol}: {e}")
                        if settings.NOTIFIER_ENABLED:
                            send_notification(f"[ERROR] Binance API error for {symbol}: {e}")
                        time.sleep(getattr(settings, 'RETRY_WAIT_TIME', 3))

                    except (ConnectionError, RequestException) as e:
                        logger.error(f"Connection error for {symbol}: {e}")
                        if settings.NOTIFIER_ENABLED:
                            send_notification(f"[ERROR] Connection issue for {symbol}: {e}")
                        time.sleep(getattr(settings, 'RETRY_WAIT_TIME', 5))

                    except Exception as e:
                        logger.exception(f"Unexpected error in trade cycle for {symbol}: {e}")
                        if settings.NOTIFIER_ENABLED:
                            send_notification(f"[CRITICAL] Unexpected error for {symbol}: {e}")
                        time.sleep(getattr(settings, 'RETRY_WAIT_TIME', 10))

                    # Döngü gecikmesi
                    jitter_min = getattr(settings, 'CYCLE_JITTER_MIN', 0)
                    jitter_max = getattr(settings, 'CYCLE_JITTER_MAX', 0)
                    if jitter_max > jitter_min:
                        jitter = random.randint(jitter_min, jitter_max)
                    else:
                        jitter = 0
                    time.sleep(settings.CYCLE_INTERVAL + jitter)

                # 3) Heartbeat
                if time.time() - last_heartbeat >= settings.HEARTBEAT_INTERVAL:
                    self.metrics.heartbeat(time.time() - last_heartbeat)
                    last_heartbeat = time.time()

            except Exception as e:
                logger.exception(f"Main loop error: {e}")
                if settings.NOTIFIER_ENABLED:
                    send_notification(f"[CRITICAL] Main loop error: {e}")
                time.sleep(10)
