from config import settings
from core.logger import BotLogger

logger = BotLogger()

class RiskManager:
    """
    Provides stop-loss, take-profit and drawdown enforcement for trades.
    """
    def __init__(self, entry_price: float, quantity: float):
        self.entry_price = entry_price
        self.quantity = quantity
        # compute SL and TP levels
        self.stop_loss_price = round(entry_price * (1 - settings.STOP_LOSS_RATIO), 8)
        self.take_profit_price = round(entry_price * (1 + settings.TAKE_PROFIT_RATIO), 8)

    def create_oco_params(self) -> dict:
        """
        Returns parameters for Binance OCO order.
        """
        return {
            'stopPrice': str(self.stop_loss_price),
            'stopLimitPrice': str(round(self.stop_loss_price * 0.999, 8)),
            'price': str(self.take_profit_price)
        }

    def check_drawdown(self, current_price: float, current_balance: float, peak_balance: float) -> bool:
        """
        Checks whether drawdown exceeds MAX_DRAWDOWN_PCT and signals exit if so.
        Returns True if action should be forced to SELL.
        """
        drawdown = (peak_balance - current_balance) / peak_balance if peak_balance else 0.0
        if drawdown > settings.MAX_DRAWDOWN_PCT:
            logger.log(f"[RISK] Drawdown {drawdown:.2%} exceeds limit; forcing SELL.", level="WARNING")
            return True
        return False
