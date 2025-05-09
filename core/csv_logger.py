# core/csv_logger.py

import os
import csv
from config import settings

def log_trade_csv(trade: dict) -> None:
    """
    Logs a single trade to the CSV log file defined in settings.CSV_LOG_FILE.
    Creates the file with header if it doesn't exist.
    Expects trade dict to have keys:
      'timestamp', 'symbol', 'action', 'quantity', 'exit_price' or 'price', 'pnl'
    """
    fieldnames = ['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl']
    exists = os.path.isfile(settings.CSV_LOG_FILE)
    with open(settings.CSV_LOG_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            'timestamp': trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'symbol':    trade['symbol'],
            'action':    trade['action'],
            'quantity':  trade['quantity'],
            'price':     trade.get('exit_price', trade.get('price')),
            'pnl':       trade['pnl']
        })
