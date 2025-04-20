import time
from datetime import datetime
from binance.client import Client
from config import settings
from core.paper_trade_executor import PaperTradeExecutor

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
        else:
            balance_info = self.client.get_asset_balance(asset=asset)
            return float(balance_info.get('free', 0.0))

    def manage_position(self, symbol: str, action: str) -> dict:
        """
        Executes or simulates a market order. Returns a result dict containing:
        'action', 'quantity', 'price', 'pnl'.
        """
        if settings.PAPER_TRADING:
            return self.executor.manage_position(symbol, action)

        # Live trading path
        # Determine market order parameters
        if action.upper() == 'BUY':
            # Place market buy for a fixed USDT amount from settings, if defined
            try:
                qty_usdt = settings.TRADE_USDT_AMOUNT
            except AttributeError:
                qty_usdt = None

            if qty_usdt:
                order = self.client.create_order(
                    symbol=symbol,
                    side='BUY',
                    type='MARKET',
                    quoteOrderQty=qty_usdt
                )
            else:
                raise ValueError("TRADE_USDT_AMOUNT must be set in settings for live buy orders.")

        elif action.upper() == 'SELL':
            base_asset = symbol.replace('USDT', '')
            asset_balance = self.client.get_asset_balance(asset=base_asset)
            qty = float(asset_balance.get('free', 0.0))
            order = self.client.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=qty
            )
        else:
            # No operation
            return {'action': action, 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        # Parse execution details
        executed_qty = float(order.get('executedQty', 0.0))
        cummulative_quote = float(order.get('cummulativeQuoteQty', 0.0))
        avg_price = (cummulative_quote / executed_qty) if executed_qty else 0.0

        # Live PnL tracking not implemented here
        pnl = 0.0
        return {
            'action': action,
            'quantity': executed_qty,
            'price': avg_price,
            'pnl': pnl
        }
