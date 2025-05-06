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
        # Compute SL and TP levels based on configuration
        self.stop_loss_price = round(
            entry_price * (1 - settings.STOP_LOSS_RATIO),
            settings.PRICE_DECIMALS if hasattr(settings, 'PRICE_DECIMALS') else 8
        )
        self.take_profit_price = round(
            entry_price * (1 + settings.TAKE_PROFIT_RATIO),
            settings.PRICE_DECIMALS if hasattr(settings, 'PRICE_DECIMALS') else 8
        )

    def create_oco_params(self) -> dict:
        """
        Returns a dict of parameters for placing a Binance OCO (One-Cancels-the-Other) order.
        Includes stop-loss, stop-limit, and take-profit prices.
        """
        stop_limit_price = round(
            self.stop_loss_price * (1 - settings.STOP_LIMIT_BUFFER),
            settings.PRICE_DECIMALS if hasattr(settings, 'PRICE_DECIMALS') else 8
        )
        return {
            'stopPrice': str(self.stop_loss_price),
            'stopLimitPrice': str(stop_limit_price),
            'price': str(self.take_profit_price)
        }

    def check_drawdown(self, current_balance: float, peak_balance: float) -> bool:
        """
        Checks whether drawdown exceeds MAX_DRAWDOWN_PCT and signals exit if so.
        Returns True if action should be forced to SELL due to excessive drawdown.
        """
        if peak_balance <= 0:
            return False
        drawdown_pct = (peak_balance - current_balance) / peak_balance
        if drawdown_pct > settings.MAX_DRAWDOWN_PCT:
            logger.warning(
                f"[RISK] Drawdown {drawdown_pct:.2%} exceeds limit ({settings.MAX_DRAWDOWN_PCT:.2%}); forcing SELL."
            )
            return True
        return False
