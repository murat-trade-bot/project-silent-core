import os
import csv
import time
import math
from datetime import datetime

from config import settings
from security.stealth_mode import stealth
from core.logger import BotLogger

logger = BotLogger()

class PaperTradeExecutor:
    """
    Simulates trading for paper trading mode.
    Tracks USDT balance, positions, and computes pseudo-PnL.
    """
    def __init__(self, initial_balance: float = None):
        # Starting USDT balance for simulation
        self.balance_usdt = initial_balance if initial_balance is not None else settings.INITIAL_BALANCE
        # Positions: {'BTC': amount, ...}
        self.positions = {}
        # Average entry prices: {'BTC': price, ...}
        self.avg_prices = {}
        # Ensure CSV log file exists with correct headers
        csv_file = settings.CSV_LOG_FILE
        if not os.path.isfile(csv_file):
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp','symbol','action','quantity','price','pnl'])

    def get_balance(self, asset: str) -> float:
        # Return free balance for USDT or asset
        if asset.upper() == 'USDT':
            return self.balance_usdt
        return self.positions.get(asset.upper(), 0.0)

    def manage_position(self, symbol: str, action: str) -> dict:
        """
        Simulates BUY or SELL for given symbol.
        Returns dict with keys: action, quantity, price, pnl
        """
        base_asset = symbol.replace('USDT', '')
        price = self._get_mock_price(symbol)
        # Determine amount in USDT to trade
        trade_usdt = self.balance_usdt * settings.POSITION_SIZE_PCT
        trade_usdt = stealth.apply_order_size_jitter(trade_usdt)
        if action.upper() == 'BUY':
            qty = trade_usdt / price if price else 0.0
            cost = qty * price
            if cost > self.balance_usdt:
                cost = self.balance_usdt
                qty = cost / price
            # Update balances and positions
            self.balance_usdt -= cost
            prev_qty = self.positions.get(base_asset, 0.0)
            prev_avg = self.avg_prices.get(base_asset, 0.0)
            new_total = prev_qty * prev_avg + cost
            new_qty = prev_qty + qty
            self.positions[base_asset] = new_qty
            self.avg_prices[base_asset] = new_total / new_qty if new_qty else 0.0
            pnl = 0.0
        elif action.upper() == 'SELL':
            held_qty = self.positions.get(base_asset, 0.0)
            qty = held_qty
            revenue = qty * price
            self.balance_usdt += revenue
            self.positions[base_asset] = 0.0
            entry_price = self.avg_prices.get(base_asset, price)
            pnl = revenue - (qty * entry_price)
            self.avg_prices[base_asset] = 0.0
        else:
            return {'action':action,'quantity':0.0,'price':0.0,'pnl':0.0}

        # Log to CSV
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        with open(settings.CSV_LOG_FILE,'a',newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp,symbol,action,round(qty,6),round(price,2),round(pnl,2)])

        # Log to console
        logger.log(f"[PAPER] {action} {qty:.6f} {base_asset} @ {price:.2f}, PnL: {pnl:.2f}")
        return {'action':action,'quantity':qty,'price':price,'pnl':round(pnl,2)}

    def _get_mock_price(self, symbol: str) -> float:
        """
        Returns a mock price based on time or environment.
        """
        base = float(settings.MOCK_BASE_PRICE) if hasattr(settings,'MOCK_BASE_PRICE') else 30000
        amplitude = getattr(settings,'MOCK_PRICE_AMPLITUDE',1000)
        return base + amplitude * math.sin(time.time()/60)
