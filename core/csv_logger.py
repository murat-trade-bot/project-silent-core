# core/csv_logger.py

import os
import csv
from config import settings
from core.logger import BotLogger

logger = BotLogger()

def log_trade_csv(trade: dict) -> None:
    """
    Logs a single trade to the CSV log file defined in settings.CSV_LOG_FILE.
    Creates the file with header if it doesn't exist.
    Expects trade dict to have keys:
      'symbol', 'action', 'quantity', 'exit_price' or 'price', 'pnl'
    """
    fieldnames = ['symbol', 'action', 'quantity', 'price', 'pnl']
    exists = os.path.isfile(settings.CSV_LOG_FILE)
    try:
        with open(settings.CSV_LOG_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            row = {
                'symbol':    trade.get('symbol', ''),
                'action':    trade.get('action', ''),
                'quantity':  trade.get('quantity', 0),
                'price':     trade.get('exit_price', trade.get('price', 0)),
                'pnl':       trade.get('pnl', 0)
            }
            writer.writerow(row)
        logger.info(f"CSVLogger: İşlem kaydedildi: {row}")
    except Exception as e:
        logger.error(f"CSVLogger: Kayıt hatası: {e} | Trade: {trade}")
