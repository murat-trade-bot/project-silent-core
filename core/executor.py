import time
from datetime import datetime
from binance.client import Client
from config import settings
from core.paper_trade_executor import PaperTradeExecutor
from core.risk_manager import RiskManager
from core.logger import BotLogger

logger = BotLogger()

class ExecutorManager:
    """
    Manages order execution for both live and paper trading.
    Provides unified interface for balance inquiry and order execution.
    """
    def __init__(self):
        if settings.PAPER_TRADING:
            # Initialize paper trading executor with initial balance
            self.executor = PaperTradeExecutor(initial_balance=settings.INITIAL_BALANCE)
            self.client = None
        else:
            # Initialize Binance client for live or testnet
            self.client = Client(
                settings.BINANCE_API_KEY,
                settings.BINANCE_API_SECRET,
                testnet=settings.TESTNET_MODE
            )
            if settings.TESTNET_MODE:
                # Use testnet endpoint
                self.client.API_URL = 'https://testnet.binance.vision/api'
            self.executor = None

    def get_balance(self, asset: str) -> float:
        """
        Returns free balance for a given asset (e.g., 'USDT' or 'BTC').
        """
        if settings.PAPER_TRADING:
            return self.executor.get_balance(asset)
        balance_info = self.client.get_asset_balance(asset=asset)
        return float(balance_info.get('free', 0.0))

    def manage_position(self, symbol: str, action: str) -> dict:
        """
        Executes or simulates a market order. Returns a result dict containing:
        'action', 'quantity', 'price', 'pnl'.
        """
        # Paper trading path
        if settings.PAPER_TRADING:
            return self.executor.manage_position(symbol, action)

        # Live trading path
        if action.upper() == 'BUY':
            # Determine USD quantity for buy
            try:
                qty_usdt = settings.TRADE_USDT_AMOUNT
            except AttributeError:
                raise ValueError("TRADE_USDT_AMOUNT must be set in settings for live buy orders.")
            # Place market buy order
            order = self.client.create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quoteOrderQty=qty_usdt
            )
            # Parse fills for execution price
            fills = order.get('fills', [])
            executed_qty = float(order.get('executedQty', 0.0))
            fill_price = (float(fills[0]['price']) if fills else
                          (float(order.get('cummulativeQuoteQty', 0.0)) / executed_qty if executed_qty else 0.0))
            logger.log(f"[BINANCE] BUY executed: {executed_qty} @ {fill_price:.2f}")
            # Risk management: SL/TP via OCO
            rm = RiskManager(entry_price=fill_price, quantity=executed_qty)
            oco_params = rm.create_oco_params()
            try:
                oco_order = self.client.create_oco_order(
                    symbol=symbol,
                    side='SELL',
                    quantity=executed_qty,
                    price=oco_params['price'],
                    stopPrice=oco_params['stopPrice'],
                    stopLimitPrice=oco_params['stopLimitPrice'],
                    stopLimitTimeInForce='GTC'
                )
                logger.log(f"[BINANCE] OCO SELL set => {oco_order}")
            except Exception as e:
                logger.log(f"[BINANCE] OCO SELL error: {e}", level="ERROR")
            # Return result
            return {'action': 'BUY', 'quantity': executed_qty, 'price': fill_price, 'pnl': 0.0}

        elif action.upper() == 'SELL':
            # Sell full position
            base_asset = symbol.replace('USDT', '')
            asset_balance = self.client.get_asset_balance(asset=base_asset)
            sell_qty = float(asset_balance.get('free', 0.0))
            order = self.client.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=sell_qty
            )
            executed_qty = float(order.get('executedQty', 0.0))
            fill_price = (float(order.get('cummulativeQuoteQty', 0.0)) / executed_qty) if executed_qty else 0.0
            logger.log(f"[BINANCE] SELL executed: {executed_qty} @ {fill_price:.2f}")
            # Return result
            return {'action': 'SELL', 'quantity': executed_qty, 'price': fill_price, 'pnl': 0.0}

        else:
            # No operation
            logger.log(f"[EXECUTOR] No action for {action}")
            return {'action': action, 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}
