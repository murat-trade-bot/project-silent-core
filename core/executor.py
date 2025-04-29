import time
from binance.client import Client
from config import settings
from core.paper_trade_executor import PaperTradeExecutor
from core.risk_manager import RiskManager
from core.logger import BotLogger

logger = BotLogger()

class ExecutorManager:
    def __init__(self):
        if settings.PAPER_TRADING:
            self.executor = PaperTradeExecutor(initial_balance=settings.INITIAL_BALANCE)
            self.client = None
        else:
            self.client = Client(
                settings.BINANCE_API_KEY,
                settings.BINANCE_API_SECRET,
                testnet=settings.TESTNET_MODE
            )
            if settings.TESTNET_MODE:
                self.client.API_URL = 'https://testnet.binance.vision/api'
            self.executor = None

    def get_balance(self, asset: str) -> float:
        if settings.PAPER_TRADING:
            return self.executor.get_balance(asset)
        try:
            balance_info = self.client.get_asset_balance(asset=asset)
            return float(balance_info.get('free', 0.0))
        except Exception as e:
            logger.error(f"Get balance error: {e}")
            return 0.0

    def manage_position(self, symbol: str, action: str) -> dict:
        if settings.PAPER_TRADING:
            return self.executor.manage_position(symbol, action)

        base_asset = symbol.replace('USDT', '')

        try:
            current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return {'action': 'ERROR', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        if action.upper() == 'BUY':
            usdt_balance = self.get_balance('USDT')
            trade_amount = usdt_balance * settings.POSITION_SIZE_PCT
            trade_amount = max(trade_amount, 10)

            try:
                order = self.client.create_order(
                    symbol=symbol,
                    side='BUY',
                    type='MARKET',
                    quoteOrderQty=trade_amount
                )
                executed_qty = float(order['executedQty'])
                avg_fill_price = float(order['cummulativeQuoteQty']) / executed_qty
                logger.info(f"BUY {symbol}: {executed_qty} @ {avg_fill_price}")

                rm = RiskManager(entry_price=avg_fill_price, quantity=executed_qty)
                oco_params = rm.create_oco_params()

                try:
                    self.client.create_oco_order(
                        symbol=symbol,
                        side='SELL',
                        quantity=executed_qty,
                        price=oco_params['price'],
                        stopPrice=oco_params['stopPrice'],
                        stopLimitPrice=oco_params['stopLimitPrice'],
                        stopLimitTimeInForce='GTC'
                    )
                    logger.info(f"OCO SELL set: TP={oco_params['price']} SL={oco_params['stopPrice']}")
                except Exception as e:
                    logger.error(f"OCO error: {e}")
                    self.client.create_order(
                        symbol=symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=executed_qty
                    )
                    logger.warning("Pozisyon hemen kapatıldı (OCO başarısız).")

                return {'action': 'BUY', 'quantity': executed_qty, 'price': avg_fill_price, 'pnl': 0.0}

            except Exception as e:
                logger.error(f"BUY error: {e}")
                return {'action': 'ERROR', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        elif action.upper() == 'SELL':
            asset_balance = self.get_balance(base_asset)
            if asset_balance <= 0:
                logger.warning(f"{base_asset} bakiyesi yetersiz.")
                return {'action': 'HOLD', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

            try:
                order = self.client.create_order(
                    symbol=symbol,
                    side='SELL',
                    type='MARKET',
                    quantity=asset_balance
                )
                executed_qty = float(order['executedQty'])
                avg_fill_price = float(order['cummulativeQuoteQty']) / executed_qty
                logger.info(f"SELL {symbol}: {executed_qty} @ {avg_fill_price}")

                return {'action': 'SELL', 'quantity': executed_qty, 'price': avg_fill_price, 'pnl': 0.0}

            except Exception as e:
                logger.error(f"SELL error: {e}")
                return {'action': 'ERROR', 'quantity': 0.0, 'price': 0.0, 'pnl': 0.0}

        else:
            logger.info(f"No action performed for {symbol}")
            return {'action': 'HOLD', 'quantity': 0.0, 'price': current_price, 'pnl': 0.0}
