# core/executor.py

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
            # Paper trading executor
            self.executor = PaperTradeExecutor(initial_balance=settings.INITIAL_BALANCE)
            self.client = None
        else:
            # Live or testnet Binance client
            self.client = Client(
                settings.BINANCE_API_KEY,
                settings.BINANCE_API_SECRET,
                testnet=settings.TESTNET_MODE
            )
            if settings.TESTNET_MODE:
                self.client.API_URL = 'https://testnet.binance.vision/api'
            self.executor = None

    def get_balance(self, asset: str) -> float:
        """
        Returns free balance for a given asset.
        """
        if settings.PAPER_TRADING:
            return self.executor.get_balance(asset)
        try:
            bal_info = self.client.get_asset_balance(asset=asset)
            return float(bal_info.get('free', 0.0))
        except Exception as e:
            logger.log(f"[EXECUTOR] Get balance error: {e}", level="ERROR")
            return 0.0

    def manage_position(self, symbol: str, action: str) -> dict:
        """
        Executes or simulates a market order. Returns a result dict containing:
        'action', 'quantity', 'price', 'pnl'.
        """

        # --- Paper trading path ---
        if settings.PAPER_TRADING:
            return self.executor.manage_position(symbol, action)

        # --- Live trading path ---
        base_asset = symbol.replace('USDT', '')

        # Fetch current price safely
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol) or {}
            current_price = float(ticker.get('price', 0.0))
        except Exception as e:
            logger.log(f"[EXECUTOR] Price fetch error: {e}", level="ERROR")
            return {'action': 'ERROR', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        # If BUY requested but position already open, skip
        if action.upper() == 'BUY':
            if self.get_balance(base_asset) > 0:
                logger.log(f"[EXECUTOR] {symbol} pozisyonu zaten açık, BUY atlandı.", level="INFO")
                return {'action': 'HOLD', 'quantity': 0.0, 'price': current_price, 'pnl': 0.0}

        # --- BUY logic ---
        if action.upper() == 'BUY':
            usdt_bal = self.get_balance('USDT')
            trade_amount = usdt_bal * settings.POSITION_SIZE_PCT
            trade_amount = max(trade_amount, 10)  # enforce a minimum trade size

            try:
                order = self.client.create_order(
                    symbol=symbol,
                    side='BUY',
                    type='MARKET',
                    quoteOrderQty=trade_amount
                ) or {}
                executed_qty = float(order.get('executedQty', 0.0))
                cum_quote   = float(order.get('cummulativeQuoteQty', 0.0))
                avg_fill    = cum_quote / executed_qty if executed_qty else current_price
                logger.log(f"[EXECUTOR] BUY {symbol}: {executed_qty} @ {avg_fill:.2f}", level="INFO")

                # Set up SL/TP via OCO
                rm = RiskManager(entry_price=avg_fill, quantity=executed_qty)
                oco = rm.create_oco_params()
                try:
                    self.client.create_oco_order(
                        symbol=symbol,
                        side='SELL',
                        quantity=executed_qty,
                        price=oco['price'],
                        stopPrice=oco['stopPrice'],
                        stopLimitPrice=oco['stopLimitPrice'],
                        stopLimitTimeInForce='GTC'
                    )
                    logger.log(f"[EXECUTOR] OCO SELL set: TP={oco['price']} SL={oco['stopPrice']}", level="INFO")
                except Exception as e:
                    logger.log(f"[EXECUTOR] OCO error: {e}", level="ERROR")
                    # If OCO fails, immediately close position
                    self.client.create_order(
                        symbol=symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=executed_qty
                    )
                    logger.log("[EXECUTOR] Pozisyon hemen kapatıldı (OCO başarısız).", level="WARNING")

                return {'action': 'BUY', 'quantity': executed_qty, 'price': avg_fill, 'pnl': 0.0}

            except Exception as e:
                logger.log(f"[EXECUTOR] BUY error: {e}", level="ERROR")
                return {'action': 'ERROR', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        # --- SELL logic ---
        elif action.upper() == 'SELL':
            asset_bal = self.get_balance(base_asset)
            if asset_bal <= 0:
                logger.log(f"[EXECUTOR] {base_asset} bakiyesi yetersiz, SELL atlandı.", level="WARNING")
                return {'action': 'HOLD', 'quantity': 0.0, 'price': current_price, 'pnl': 0.0}

            try:
                order = self.client.create_order(
                    symbol=symbol,
                    side='SELL',
                    type='MARKET',
                    quantity=asset_bal
                ) or {}
                executed_qty = float(order.get('executedQty', 0.0))
                cum_quote   = float(order.get('cummulativeQuoteQty', 0.0))
                avg_fill    = cum_quote / executed_qty if executed_qty else current_price
                logger.log(f"[EXECUTOR] SELL {symbol}: {executed_qty} @ {avg_fill:.2f}", level="INFO")
                return {'action': 'SELL', 'quantity': executed_qty, 'price': avg_fill, 'pnl': 0.0}

            except Exception as e:
                logger.log(f"[EXECUTOR] SELL error: {e}", level="ERROR")
                return {'action': 'ERROR', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        # --- HOLD / NO-OP ---
        else:
            logger.log(f"[EXECUTOR] No action for {symbol}", level="INFO")
            return {'action': 'HOLD', 'quantity': 0.0, 'price': current_price, 'pnl': 0.0}
