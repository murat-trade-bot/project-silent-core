import os
import time
import random
import csv

from datetime import datetime, timedelta
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException


from config import settings from core.logger import BotLogger from core.strategy import Strategy from core.executor import ExecutorManager from modules.dynamic_position import get_dynamic_position_size from modules.strategy_optimizer import optimize_strategy_parameters from modules.multi_asset_selector import select_coins from modules.period_manager import ( start_period, update_settings_for_period, compute_daily_shortfall, perform_period_withdrawal ) from notifier import send_notification

logger = BotLogger()

Load environment variables

load_dotenv() API_KEY = os.getenv('BINANCE_API_KEY', '') API_SECRET = os.getenv('BINANCE_API_SECRET', '')

Initialize Binance Client

client = Client(API_KEY, API_SECRET) if settings.TESTNET_MODE: client.API_URL = 'https://testnet.binance.vision/api' logger.info('Testnet mode enabled') else: logger.info('Live mode enabled')

Initialize period state and core components

start_period(client) optimize_strategy_parameters() period = update_settings_for_period() logger.info( f"[PERIOD] Active period: {period['name']} | " f"Target={period['target_balance']:.2f} USDT | " f"Duration={period.get('duration_days', 0)}d | " f"Growth={settings.GROWTH_FACTOR}" )

strategy = Strategy() executor = ExecutorManager(client)

Capture base trade amount

base_trade_amount = settings.TRADE_USDT_AMOUNT

Initial balance metrics

try: usdt_bal = float(executor.client.get_asset_balance('USDT')['free']) except Exception: usdt_bal = executor.get_balance('USDT') start_balance = usdt_bal peak_balance = start_balance max_drawdown = 0.0

total_trades = 0 win_trades = 0 loss_trades = 0 trade_durations = []

logger.info(f"Bot started at {datetime.utcnow()} UTC | Start balance: {start_balance:.2f} USDT")

CSV logger

def log_trade_csv(trade): fieldnames = ['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl'] exists = os.path.isfile(settings.CSV_LOG_FILE) with open(settings.CSV_LOG_FILE, 'a', newline='') as f: writer = csv.DictWriter(f, fieldnames=fieldnames) if not exists: writer.writeheader() writer.writerow({ 'timestamp': trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 'symbol':    trade['symbol'], 'action':    trade['action'], 'quantity':  trade['quantity'], 'price':     trade.get('exit_price', trade.get('price')), 'pnl':       trade['pnl'] })

Metrics printer

def print_metrics(): global peak_balance, max_drawdown try: curr_balance = float(executor.client.get_asset_balance('USDT')['free']) except Exception: curr_balance = executor.get_balance('USDT') peak_balance = max(peak_balance, curr_balance) drawdown = peak_balance - curr_balance max_drawdown = max(max_drawdown, drawdown) pnl_pct = (curr_balance - start_balance)/start_balance*100 if start_balance else 0 progress_pct = (curr_balance/settings.TARGET_USDT)100 if settings.TARGET_USDT else 0 avg_dur = (sum(trade_durations)/len(trade_durations)) if trade_durations else 0 win_rate = (win_trades/total_trades100) if total_trades else 0 print( f"Balance: {curr_balance:.2f} USDT | PnL%: {pnl_pct:+.2f}% | " f"Progress%: {progress_pct:.2f}%" ) print( f"Trades: {total_trades} | Wins: {win_trades} ({win_rate:.1f}%) | " f"Max Drawdown: {max_drawdown:.2f} | Avg Dur: {avg_dur:.1f}s" )

if name == 'main': last_heartbeat = time.time() while True: # Refresh period settings period = update_settings_for_period()

# Compute daily shortfall and adjust trade size
    extra = compute_daily_shortfall(client)
    settings.TRADE_USDT_AMOUNT = base_trade_amount + extra

    # Dynamic symbol selection or fallback
    symbols = select_coins() if getattr(settings, 'USE_DYNAMIC_SYMBOL_SELECTION', False) else settings.SYMBOLS
    if not symbols:
        symbols = settings.SYMBOLS

    for symbol in symbols:
        cycle_start = time.time()
        try:
            action = strategy.decide(symbol)
            trade_amount = settings.TRADE_USDT_AMOUNT
            if getattr(settings, 'USE_DYNAMIC_POSITION', False):
                trade_amount = get_dynamic_position_size(symbol, trade_amount)

            if action == 'BUY':
                executor.buy(symbol, trade_amount)
            elif action == 'SELL':
                executor.sell(symbol)
            # HOLD → no action

            # If a position closed, log and notify
            closed = executor.get_closed_positions()
            if closed:
                trade = closed[-1]
                trade['timestamp'] = datetime.utcnow()
                trade['duration'] = time.time() - cycle_start
                total_trades += 1
                if trade['pnl'] >= 0:
                    win_trades += 1
                else:
                    loss_trades += 1
                log_trade_csv(trade)
                print(
                    f"{trade['timestamp']} | {trade['symbol']} {trade['action']} "
                    f"{trade['quantity']} @ {trade['exit_price']:.2f} | "
                    f"PnL {trade['pnl']:+.2f}"
                )
                if getattr(settings, 'NOTIFIER_ENABLED', False):
                    send_notification(
                        f"Trade {trade['action']} {trade['symbol']} PnL {trade['pnl']:+.2f}"
                    )
                trade_durations.append(trade['duration'])
                print_metrics()

        except BinanceAPIException as e:
            logger.info(f"API error in cycle {symbol}: {e}")
        except Exception as e:
            logger.info(f"Error in cycle {symbol}: {e}")

        time.sleep(
            settings.CYCLE_INTERVAL + random.randint(
                settings.CYCLE_JITTER_MIN,
                settings.CYCLE_JITTER_MAX
            )
        )

    # Heartbeat log
    if time.time() - last_heartbeat >= settings.HEARTBEAT_INTERVAL:
        uptime = timedelta(seconds=int(time.time() - last_heartbeat))
        logger.info(f"[HEARTBEAT] Uptime: {uptime}")
        last_heartbeat = time.time()

