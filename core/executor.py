import time
import math
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

from config import settings
from core.logger import BotLogger

logger = BotLogger()

class ExecutorManager:
    """
    Executes market orders on Binance Spot API, tracks open and closed positions,
    calculates PnL, and enforces order cooldowns with proper error handling and precision.
    """
    def __init__(self, client: Client, dry_run=False):
        assert hasattr(settings, 'ORDER_COOLDOWN'), "settings.ORDER_COOLDOWN must be defined"
        assert hasattr(settings, 'SYMBOLS'), "settings.SYMBOLS must be defined"

        self.client = client
        self.open_positions = {}
        self.closed_positions = []

        self.cooldown = settings.ORDER_COOLDOWN
        self.last_order_time = 0

        # Initialize symbol precision for quantity formatting
        self.precisions = {}
        for symbol in settings.SYMBOLS:
            try:
                info = self.client.get_symbol_info(symbol)
                step_size = next(f['stepSize'] for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
                precision = int(round(-math.log10(float(step_size))))
                self.precisions[symbol] = precision
            except Exception as e:
                logger.error(f"Error fetching precision for {symbol}: {e}")
                self.precisions[symbol] = getattr(settings, 'QUANTITY_DECIMALS', 8)

        self.dry_run = dry_run

    def execute(self, action: str, data: dict, stealth=True) -> bool:
        """
        Execute given action. Supports dry-run and stealth mode.
        """
        import random
        if stealth:
            delay = random.uniform(0.5, 2.5)
            time.sleep(delay)
        if self.dry_run:
            logger.info(f"[DRY-RUN] {action} {data}")
            return True

        elapsed = time.time() - self.last_order_time
        if elapsed < self.cooldown:
            time.sleep(self.cooldown - elapsed)

        logger.info(f"Executing action: {action} with data: {data}")
        self.last_order_time = time.time()
        return True

    def get_balance(self, asset: str) -> float:
        """
        Returns free balance for the specified asset using Binance API.
        """
        try:
            balance_info = self.client.get_asset_balance(asset)
            return float(balance_info.get('free', 0.0))
        except Exception as e:
            logger.error(f"Error fetching balance for {asset}: {e}")
            return 0.0

    def buy(self, symbol: str, usdt_amount: float):
        """
        Place a market buy order for a given USDT amount, record entry price and quantity.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] BUY {symbol} {usdt_amount}")
            return

        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = float(ticker.get('price', 0))
            if price <= 0:
                logger.info(f"EXECUTOR BUY {symbol}: invalid price {price}")
                return
        except BinanceAPIException as e:
            logger.info(f"EXECUTOR BUY {symbol}: ticker fetch error {e}")
            return

        precision = self.precisions.get(symbol, getattr(settings, 'QUANTITY_DECIMALS', 8))
        quantity = round(usdt_amount / price, precision)

        try:
            order = self.client.create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quantity=quantity
            )
        except BinanceAPIException as e:
            logger.info(f"EXECUTOR BUY {symbol}: order error {e}")
            return

        fills = order.get('fills')
        entry_price = float(fills[0]['price']) if fills else price

        self.open_positions[symbol] = {
            'entry_price': entry_price,
            'quantity': quantity
        }
        logger.info(f"EXECUTOR BUY {symbol}: qty={quantity}, entry={entry_price}")
        time.sleep(self.cooldown)

    def sell(self, symbol: str):
        """
        Close an existing open position with a market sell order,
        calculate PnL and record the closed position.
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] SELL {symbol}")
            return

        position = self.open_positions.get(symbol)
        if not position:
            logger.info(f"EXECUTOR SELL {symbol}: no open position to close.")
            return

        quantity = position['quantity']
        try:
            order = self.client.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity
            )
        except BinanceAPIException as e:
            logger.info(f"EXECUTOR SELL {symbol}: order error {e}")
            return

        fills = order.get('fills')
        try:
            exit_price = float(fills[0]['price']) if fills else float(
                self.client.get_symbol_ticker(symbol=symbol).get('price', 0)
            )
        except (BinanceAPIException, ValueError) as e:
            logger.info(f"EXECUTOR SELL {symbol}: exit price fetch error {e}")
            exit_price = position['entry_price']

        entry_price = position['entry_price']
        pnl = (exit_price - entry_price) * quantity

        self.closed_positions.append({
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl
        })
        self.open_positions.pop(symbol, None)

        logger.info(f"EXECUTOR SELL {symbol}: qty={quantity}, exit={exit_price}, PnL={pnl}")
        time.sleep(self.cooldown)

    def get_open_positions(self) -> dict:
        """
        Return a snapshot of current open positions.
        """
        return self.open_positions.copy()

    def get_closed_positions(self) -> list:
        """
        Return a record of closed positions with PnL details.
        """
        return list(self.closed_positions)

