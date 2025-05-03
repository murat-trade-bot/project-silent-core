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
        # Paper‐trading modunda delegasyon
        if settings.PAPER_TRADING:
            result = self.executor.manage_position(symbol, action)
            # fallback: paper da None dönmesin
            return result or {
                'action': 'HOLD',
                'quantity': 0.0,
                'price': 0.0,
                'pnl': 0.0
            }

        # Live trading
        base_asset = symbol.replace('USDT', '')

        # (0) Fiyatı alalım
        try:
            current_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            return {
                'action': 'ERROR',
                'quantity': 0.0,
                'price': 0.0,
                'pnl': 0.0
            }

        # (1) BUY işlemi
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
                logger.info(f"[BINANCE] BUY executed: {executed_qty} @ {avg_fill_price:.2f}")

                # SL/TP ayarla
                rm = RiskManager(entry_price=avg_fill_price, quantity=executed_qty)
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
                    logger.info(f"[BINANCE] OCO SELL set => {oco_order}")
                except Exception as e:
                    logger.error(f"[BINANCE] OCO SELL error: {e}")
                    # OCO başarısızsa hemen market sell
                    self.client.create_order(
                        symbol=symbol,
                        side='SELL',
                        type='MARKET',
                        quantity=executed_qty
                    )
                    logger.warning("[EXECUTOR] Pozisyon hemen kapatıldı (OCO başarısız).")

                return {
                    'action': 'BUY',
                    'quantity': executed_qty,
                    'price': avg_fill_price,
                    'pnl': 0.0
                }

            except Exception as e:
                logger.error(f"[EXECUTOR] BUY error: {e}")
                return {
                    'action': 'ERROR',
                    'quantity': 0.0,
                    'price': 0.0,
                    'pnl': 0.0
                }

        # (2) SELL işlemi
        elif action.upper() == 'SELL':
            asset_balance = self.get_balance(base_asset)
            if asset_balance <= 0:
                logger.warning(f"[EXECUTOR] {base_asset} bakiyesi yetersiz.")
                return {
                    'action': 'HOLD',
                    'quantity': 0.0,
                    'price': current_price,
                    'pnl': 0.0
                }

            try:
                order = self.client.create_order(
                    symbol=symbol,
                    side='SELL',
                    type='MARKET',
                    quantity=asset_balance
                )
                executed_qty = float(order['executedQty'])
                avg_fill_price = float(order['cummulativeQuoteQty']) / executed_qty
                logger.info(f"[BINANCE] SELL executed: {executed_qty} @ {avg_fill_price:.2f}")

                return {
                    'action': 'SELL',
                    'quantity': executed_qty,
                    'price': avg_fill_price,
                    'pnl': 0.0
                }

            except Exception as e:
                logger.error(f"[EXECUTOR] SELL error: {e}")
                return {
                    'action': 'ERROR',
                    'quantity': 0.0,
                    'price': 0.0,
                    'pnl': 0.0
                }

        # (3) Diğer durumlar için açık dönüş
        else:
            logger.info(f"[EXECUTOR] No action performed for {action}")
            return {
                'action': 'HOLD',
                'quantity': 0.0,
                'price': current_price,
                'pnl': 0.0
            }

        # Güvence: hiçbir koşulda None dönmesin
        return {
            'action': 'HOLD',
            'quantity': 0.0,
            'price': current_price if 'current_price' in locals() else 0.0,
            'pnl': 0.0
        }
