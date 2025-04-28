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
    Tracks USDT balance, positions (with SL/TP), and computes realistic PnL with Binance fee.
    """
    MIN_TRADE_AMOUNT_USDT = 10   # Minimum trade amount to avoid small trades
    COMMISSION_RATE       = 0.001  # Binance Spot commission rate (0.1%)

    def __init__(self, initial_balance: float = None):
        self.balance_usdt = initial_balance if initial_balance is not None else settings.INITIAL_BALANCE
        # positions maps asset -> dict with keys: quantity, avg_price, stop_loss, take_profit
        self.positions = {}
        csv_file = settings.CSV_LOG_FILE
        if not os.path.isfile(csv_file):
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'symbol', 'action', 'quantity', 'price', 'pnl'])

    def get_balance(self, asset: str) -> float:
        if asset.upper() == 'USDT':
            return self.balance_usdt
        info = self.positions.get(asset.upper())
        return info.get("quantity", 0.0) if isinstance(info, dict) else 0.0

    def manage_position(self, symbol: str, action: str) -> dict:
        base_asset = symbol.replace('USDT', '')
        price = self._get_mock_price(symbol)

        # --- SL/TP Kontrolü ---
        pos_info = self.positions.get(base_asset)
        if isinstance(pos_info, dict) and pos_info.get("quantity", 0) > 0:
            if price <= pos_info["stop_loss"]:
                action = "SELL"
                logger.log(f"[PAPER] STOP LOSS triggered for {symbol} @ {price:.2f}", level="WARNING")
            elif price >= pos_info["take_profit"]:
                action = "SELL"
                logger.log(f"[PAPER] TAKE PROFIT triggered for {symbol} @ {price:.2f}", level="INFO")

        # --- İşlem Tutarı ---
        trade_usdt = max(self.balance_usdt * settings.POSITION_SIZE_PCT, self.MIN_TRADE_AMOUNT_USDT)
        trade_usdt = stealth.apply_order_size_jitter(trade_usdt)

        # --- BUY İşlemi ---
        if action.upper() == 'BUY':
            qty = trade_usdt / price if price else 0.0
            cost = qty * price
            cost_with_fee = cost * (1 + self.COMMISSION_RATE)
            if cost_with_fee > self.balance_usdt:
                cost_with_fee = self.balance_usdt
                qty = cost_with_fee / (price * (1 + self.COMMISSION_RATE))

            # Ortalama maliyeti güncelle
            prev = self.positions.get(base_asset, {"quantity": 0.0, "avg_price": 0.0})
            prev_qty = prev["quantity"]
            prev_avg = prev["avg_price"]
            new_qty = prev_qty + qty
            new_avg = ((prev_qty * prev_avg) + cost) / new_qty if new_qty else 0.0

            # USDT bakiyesinden düş
            self.balance_usdt -= cost_with_fee

            # Yeni pozisyonu kaydet (SL/TP seviyeleriyle)
            self.positions[base_asset] = {
                "quantity":   new_qty,
                "avg_price":  new_avg,
                "stop_loss":  new_avg * (1 - settings.STOP_LOSS_RATIO),
                "take_profit": new_avg * (1 + settings.TAKE_PROFIT_RATIO)
            }

            pnl = -cost * self.COMMISSION_RATE

        # --- SELL İşlemi ---
        elif action.upper() == 'SELL':
            pos_info = self.positions.get(base_asset, {})
            held_qty = pos_info.get("quantity", 0.0)
            entry_price = pos_info.get("avg_price", price)
            if held_qty == 0:
                return {'action': action, 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

            revenue = held_qty * price
            revenue_after_fee = revenue * (1 - self.COMMISSION_RATE)
            pnl = revenue_after_fee - (held_qty * entry_price)

            # Bakiyeye ekle, pozisyonu temizle
            self.balance_usdt += revenue_after_fee
            self.positions[base_asset] = {
                "quantity":  0.0,
                "avg_price": 0.0,
                "stop_loss": 0.0,
                "take_profit": 0.0
            }

            qty = held_qty

        # --- HOLD veya diğer ---
        else:
            return {'action': action, 'quantity': 0.0, 'price': price, 'pnl': 0.0}

        # --- Kayıt & Loglama ---
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        with open(settings.CSV_LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                symbol,
                action,
                round(qty, 6),
                round(price, 2),
                round(pnl, 2)
            ])

        logger.log(f"[PAPER] {action} {qty:.6f} {base_asset} @ {price:.2f}, PnL: {pnl:.2f}")
        return {'action': action, 'quantity': qty, 'price': price, 'pnl': round(pnl, 2)}

    def _get_mock_price(self, symbol: str) -> float:
        base = float(settings.MOCK_BASE_PRICE) if hasattr(settings, 'MOCK_BASE_PRICE') else 30000
        amplitude = getattr(settings, 'MOCK_PRICE_AMPLITUDE', 1000)
        return base + amplitude * math.sin(time.time() / 60)
