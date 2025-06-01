from config import settings
from core.logger import BotLogger

logger = BotLogger()

class RiskManager:
    """
    Sadece stop-loss yönetimi sağlar. Kaldıraç ve take-profit içermez.
    """
    def __init__(self, entry_price: float):
        self.entry_price = entry_price
        self.stop_loss_price = round(
            entry_price * (1 - settings.STOP_LOSS_RATIO),
            settings.PRICE_DECIMALS if hasattr(settings, 'PRICE_DECIMALS') else 8
        )
        logger.info(f"RiskManager: Stop-loss seviyesi {self.stop_loss_price} olarak ayarlandı.")

    def get_stop_loss_price(self) -> float:
        """
        Stop-loss fiyatını döndürür.
        """
        return self.stop_loss_price

    def is_stop_loss_triggered(self, current_price: float) -> bool:
        """
        Fiyat stop-loss seviyesinin altına düştü mü kontrol eder.
        """
        triggered = current_price <= self.stop_loss_price
        if triggered:
            logger.warning(f"RiskManager: Stop-loss tetiklendi! ({current_price} <= {self.stop_loss_price})")
        return triggered
